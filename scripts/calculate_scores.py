"""
Calculate rental yields and composite scores for metro areas.

Gross Rental Yield = (Annual Rent / Median Home Price) * 100
"""

import pandas as pd
from pathlib import Path
import json

def get_paths():
    """Get paths to data files."""
    script_dir = Path(__file__).parent
    raw_dir = script_dir.parent / "data" / "raw"
    output_dir = script_dir.parent / "data"
    return raw_dir, output_dir

def load_zillow_data():
    """Load ZHVI and ZORI metro-level data."""
    raw_dir, _ = get_paths()

    # Load home values (ZHVI)
    zhvi = pd.read_csv(raw_dir / "zhvi_metro.csv")

    # Load rent values (ZORI)
    zori = pd.read_csv(raw_dir / "zori_metro.csv")

    return zhvi, zori

def get_latest_value(df: pd.DataFrame, date_col: str = None) -> pd.Series:
    """Get the most recent non-null value for each row."""
    # Find date columns (format: YYYY-MM-DD)
    date_cols = [c for c in df.columns if c.count('-') == 2 and len(c) == 10]
    date_cols = sorted(date_cols, reverse=True)  # Most recent first

    if date_col and date_col in date_cols:
        return df[date_col]

    # Get most recent available value
    latest_col = date_cols[0]
    return df[latest_col]

def get_value_12m_ago(df: pd.DataFrame) -> pd.Series:
    """Get value from 12 months ago for YoY calculations."""
    date_cols = [c for c in df.columns if c.count('-') == 2 and len(c) == 10]
    date_cols = sorted(date_cols, reverse=True)

    # Get column from ~12 months ago
    if len(date_cols) >= 13:
        return df[date_cols[12]]
    return None

def calculate_gross_yield(median_price: float, monthly_rent: float) -> float:
    """Calculate gross rental yield as percentage."""
    if pd.isna(median_price) or pd.isna(monthly_rent) or median_price <= 0:
        return None
    annual_rent = monthly_rent * 12
    return (annual_rent / median_price) * 100

def process_metros():
    """Process metro data and calculate yields."""
    print("Loading Zillow data...")
    zhvi, zori = load_zillow_data()

    # Filter to only metro areas (exclude country-level)
    zhvi = zhvi[zhvi['RegionType'] == 'msa'].copy()
    zori = zori[zori['RegionType'] == 'msa'].copy()

    print(f"Found {len(zhvi)} metros with home value data")
    print(f"Found {len(zori)} metros with rent data")

    # Get latest values
    zhvi['median_price'] = get_latest_value(zhvi)
    zori['monthly_rent'] = get_latest_value(zori)

    # Get values from 12 months ago for YoY
    zhvi['price_12m_ago'] = get_value_12m_ago(zhvi)
    zori['rent_12m_ago'] = get_value_12m_ago(zori)

    # Merge on RegionID
    merged = zhvi[['RegionID', 'RegionName', 'StateName', 'SizeRank', 'median_price', 'price_12m_ago']].merge(
        zori[['RegionID', 'monthly_rent', 'rent_12m_ago']],
        on='RegionID',
        how='inner'
    )

    print(f"Merged: {len(merged)} metros with both home value and rent data")

    # Calculate metrics
    merged['gross_yield'] = merged.apply(
        lambda r: calculate_gross_yield(r['median_price'], r['monthly_rent']),
        axis=1
    )

    # Calculate YoY rent growth
    merged['rent_growth_yoy'] = (
        (merged['monthly_rent'] - merged['rent_12m_ago']) / merged['rent_12m_ago'] * 100
    )

    # Calculate YoY price growth
    merged['price_growth_yoy'] = (
        (merged['median_price'] - merged['price_12m_ago']) / merged['price_12m_ago'] * 100
    )

    # Filter out rows with missing data
    valid = merged.dropna(subset=['gross_yield', 'median_price', 'monthly_rent'])
    print(f"Valid metros with complete data: {len(valid)}")

    return valid

def generate_metros_json(df: pd.DataFrame):
    """Generate metros.json output file."""
    _, output_dir = get_paths()

    # Prepare output data
    metros = []
    for _, row in df.iterrows():
        metro = {
            'region_id': int(row['RegionID']),
            'name': row['RegionName'],
            'state': row['StateName'] if pd.notna(row['StateName']) else None,
            'size_rank': int(row['SizeRank']),
            'median_price': round(row['median_price'], 0),
            'monthly_rent': round(row['monthly_rent'], 0),
            'annual_rent': round(row['monthly_rent'] * 12, 0),
            'gross_yield': round(row['gross_yield'], 2),
            'rent_growth_yoy': round(row['rent_growth_yoy'], 2) if pd.notna(row['rent_growth_yoy']) else None,
            'price_growth_yoy': round(row['price_growth_yoy'], 2) if pd.notna(row['price_growth_yoy']) else None,
        }
        metros.append(metro)

    # Sort by gross yield descending
    metros = sorted(metros, key=lambda x: x['gross_yield'], reverse=True)

    # Add rank
    for i, metro in enumerate(metros):
        metro['yield_rank'] = i + 1

    # Save to JSON
    output_file = output_dir / "metros.json"
    with open(output_file, 'w') as f:
        json.dump({
            'generated': pd.Timestamp.now().isoformat(),
            'count': len(metros),
            'metros': metros
        }, f, indent=2)

    print(f"\nSaved {len(metros)} metros to {output_file}")

    return metros

def print_summary(metros: list):
    """Print summary statistics."""
    print("\n" + "=" * 60)
    print("TOP 20 METROS BY GROSS RENTAL YIELD")
    print("=" * 60)
    print(f"{'Rank':<5} {'Metro':<40} {'Price':>12} {'Rent':>8} {'Yield':>7}")
    print("-" * 60)

    for metro in metros[:20]:
        print(
            f"{metro['yield_rank']:<5} "
            f"{metro['name'][:38]:<40} "
            f"${metro['median_price']:>10,.0f} "
            f"${metro['monthly_rent']:>6,.0f} "
            f"{metro['gross_yield']:>6.2f}%"
        )

    # Filter for affordable markets
    affordable = [m for m in metros if m['median_price'] < 300000]
    print(f"\n{len(affordable)} metros under $300k median price")

    # High yield markets
    high_yield = [m for m in metros if m['gross_yield'] >= 8]
    print(f"{len(high_yield)} metros with 8%+ gross yield")

    # Both
    both = [m for m in metros if m['median_price'] < 300000 and m['gross_yield'] >= 8]
    print(f"{len(both)} metros under $300k WITH 8%+ gross yield")

if __name__ == "__main__":
    df = process_metros()
    metros = generate_metros_json(df)
    print_summary(metros)
