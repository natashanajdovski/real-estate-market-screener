"""
Build complete dataset for real estate market screener.

Combines data from:
- Zillow ZHVI (home values) and ZORI (rent)
- Census Bureau (population growth)
- BLS QCEW (job growth)
- Census ACS (vacancy rates)
- FAA Hub airports (for proximity)
- Manual landlord-friendliness scores
- FBI Crime Data (state-level violent crime rates)
"""

import pandas as pd
import numpy as np
import json
import os
import re
import requests
from pathlib import Path
from math import radians, cos, sin, asin, sqrt

# ----- Configuration -----
WEIGHTS = {
    'gross_yield': 0.30,
    'population_growth': 0.20,
    'job_growth': 0.15,
    'rent_growth': 0.15,
    'landlord_score': 0.10,
    'vacancy_rate': 0.10,  # Inverse - lower is better
}

# ----- Utility Functions -----

def get_paths():
    """Get paths to data directories."""
    script_dir = Path(__file__).parent
    project_dir = script_dir.parent
    return {
        'raw': project_dir / 'data' / 'raw',
        'output': project_dir / 'data',
        'scripts': script_dir,
    }

def haversine(lon1, lat1, lon2, lat2):
    """Calculate great circle distance between two points in miles."""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 3956  # Radius of earth in miles
    return c * r

def normalize_metro_name(name):
    """Normalize metro name for matching."""
    # Remove common suffixes
    name = re.sub(r',?\s*(MSA|Metro Area|Metropolitan Statistical Area|Micro Area|Micropolitan Statistical Area)$', '', name, flags=re.I)
    # Remove state suffix for matching
    name = re.sub(r',\s*[A-Z]{2}(-[A-Z]{2})*$', '', name)
    return name.strip()

def extract_state_from_metro(name):
    """Extract state code(s) from metro name."""
    match = re.search(r',\s*([A-Z]{2}(?:-[A-Z]{2})*)(?:\s|$|,)', name)
    if match:
        states = match.group(1).split('-')
        return states[0]  # Return primary state
    return None

# ----- Data Loading Functions -----

def load_zillow_data():
    """Load and process Zillow metro-level data."""
    paths = get_paths()

    # Load ZHVI (home values)
    zhvi = pd.read_csv(paths['raw'] / 'zhvi_metro.csv')
    zhvi = zhvi[zhvi['RegionType'] == 'msa'].copy()

    # Load ZORI (rents)
    zori = pd.read_csv(paths['raw'] / 'zori_metro.csv')
    zori = zori[zori['RegionType'] == 'msa'].copy()

    # Get date columns
    zhvi_date_cols = sorted([c for c in zhvi.columns if re.match(r'\d{4}-\d{2}-\d{2}', c)], reverse=True)
    zori_date_cols = sorted([c for c in zori.columns if re.match(r'\d{4}-\d{2}-\d{2}', c)], reverse=True)

    # Get latest and 12-month-ago values
    zhvi['median_price'] = zhvi[zhvi_date_cols[0]]
    zhvi['price_12m_ago'] = zhvi[zhvi_date_cols[12]] if len(zhvi_date_cols) > 12 else None

    zori['monthly_rent'] = zori[zori_date_cols[0]]
    zori['rent_12m_ago'] = zori[zori_date_cols[12]] if len(zori_date_cols) > 12 else None

    # Merge
    df = zhvi[['RegionID', 'RegionName', 'StateName', 'SizeRank', 'median_price', 'price_12m_ago']].merge(
        zori[['RegionID', 'monthly_rent', 'rent_12m_ago']],
        on='RegionID',
        how='inner'
    )

    # Calculate metrics
    df['gross_yield'] = (df['monthly_rent'] * 12 / df['median_price']) * 100
    df['rent_growth_yoy'] = ((df['monthly_rent'] - df['rent_12m_ago']) / df['rent_12m_ago']) * 100
    df['price_growth_yoy'] = ((df['median_price'] - df['price_12m_ago']) / df['price_12m_ago']) * 100

    # Extract state code
    df['state_code'] = df['RegionName'].apply(extract_state_from_metro)

    print(f"Loaded Zillow data: {len(df)} metros with both price and rent data")
    return df

def load_census_population():
    """Load Census population data."""
    paths = get_paths()

    pop = pd.read_csv(paths['raw'] / 'census_cbsa_pop.csv', encoding='latin-1')

    # Filter to metro-level (LSAD = Metropolitan Statistical Area)
    pop = pop[pop['LSAD'] == 'Metropolitan Statistical Area'].copy()

    # Calculate YoY population growth (2023 to 2024)
    pop['pop_growth_yoy'] = ((pop['POPESTIMATE2024'] - pop['POPESTIMATE2023']) / pop['POPESTIMATE2023']) * 100

    # Clean name for matching
    pop['metro_name_clean'] = pop['NAME'].apply(normalize_metro_name)

    print(f"Loaded Census population data: {len(pop)} metros")
    return pop[['CBSA', 'NAME', 'metro_name_clean', 'POPESTIMATE2024', 'pop_growth_yoy']]

def load_bls_employment():
    """Load BLS QCEW employment data."""
    paths = get_paths()

    qcew_2024_dir = paths['raw'] / 'qcew_2024_msa'

    records = []
    for filepath in qcew_2024_dir.glob('*.csv'):
        try:
            df = pd.read_csv(filepath)
            # Get total private employment (own_code=5, industry_code=10, agglvl_code=41)
            row = df[(df['own_code'] == 5) & (df['industry_code'] == '10') & (df['agglvl_code'] == 41)]
            if len(row) > 0:
                row = row.iloc[0]
                records.append({
                    'area_fips': row['area_fips'],
                    'area_title': row['area_title'],
                    'employment_2024': row['annual_avg_emplvl'],
                    'job_growth_yoy': row['oty_annual_avg_emplvl_pct_chg'],
                })
        except Exception as e:
            continue

    emp = pd.DataFrame(records)
    emp['metro_name_clean'] = emp['area_title'].apply(normalize_metro_name)

    print(f"Loaded BLS employment data: {len(emp)} metros")
    return emp

def load_census_vacancy():
    """Load Census ACS vacancy data via API."""
    print("Fetching Census ACS vacancy data...")

    url = "https://api.census.gov/data/2023/acs/acs1"
    params = {
        'get': 'NAME,B25002_001E,B25002_003E',
        'for': 'metropolitan statistical area/micropolitan statistical area:*'
    }

    response = requests.get(url, params=params, timeout=60)
    data = response.json()

    # Convert to DataFrame
    df = pd.DataFrame(data[1:], columns=data[0])
    df['B25002_001E'] = pd.to_numeric(df['B25002_001E'])
    df['B25002_003E'] = pd.to_numeric(df['B25002_003E'])

    # Calculate vacancy rate
    df['vacancy_rate'] = (df['B25002_003E'] / df['B25002_001E']) * 100
    df['metro_name_clean'] = df['NAME'].apply(normalize_metro_name)

    print(f"Loaded Census vacancy data: {len(df)} areas")
    return df[['NAME', 'metro_name_clean', 'vacancy_rate', 'B25002_001E']]

def load_airports():
    """Load FAA hub airports."""
    paths = get_paths()

    with open(paths['output'] / 'faa_hubs.json') as f:
        hubs = json.load(f)

    airports = []
    for hub in hubs['large_hubs'] + hubs['medium_hubs']:
        airports.append({
            'iata': hub['iata'],
            'name': hub['name'],
            'lat': hub['lat'],
            'lon': hub['lon'],
            'hub_type': 'large' if hub in hubs['large_hubs'] else 'medium'
        })

    print(f"Loaded {len(airports)} FAA hub airports")
    return airports

def load_landlord_scores():
    """Load landlord-friendliness scores."""
    paths = get_paths()

    with open(paths['output'] / 'landlord_scores.json') as f:
        data = json.load(f)

    scores = {state: info['score'] for state, info in data['scores'].items()}
    print(f"Loaded landlord scores for {len(scores)} states")
    return scores

def load_crime_rates():
    """Load FBI crime rates by state."""
    paths = get_paths()

    crime_file = paths['output'] / 'crime_rates.json'
    if not crime_file.exists():
        print("Crime rates file not found - run fetch_crime_data.py first")
        return {}

    with open(crime_file) as f:
        data = json.load(f)

    rates = data.get('rates', {})
    print(f"Loaded crime rates for {len(rates)} states")
    return rates

# ----- Metro Coordinate Lookup -----

def get_metro_coordinates():
    """Get approximate coordinates for metros based on airport data and common cities."""
    # This maps major metros to their approximate center coordinates
    # We'll use this for airport proximity calculation
    metro_coords = {
        'New York-Newark-Jersey City': (40.7128, -74.0060),
        'Los Angeles-Long Beach-Anaheim': (34.0522, -118.2437),
        'Chicago-Naperville-Elgin': (41.8781, -87.6298),
        'Dallas-Fort Worth-Arlington': (32.7767, -96.7970),
        'Houston-The Woodlands-Sugar Land': (29.7604, -95.3698),
        'Washington-Arlington-Alexandria': (38.9072, -77.0369),
        'Miami-Fort Lauderdale-Pompano Beach': (25.7617, -80.1918),
        'Philadelphia-Camden-Wilmington': (39.9526, -75.1652),
        'Atlanta-Sandy Springs-Alpharetta': (33.7490, -84.3880),
        'Boston-Cambridge-Newton': (42.3601, -71.0589),
        'Phoenix-Mesa-Chandler': (33.4484, -112.0740),
        'San Francisco-Oakland-Berkeley': (37.7749, -122.4194),
        'Riverside-San Bernardino-Ontario': (33.9533, -117.3962),
        'Detroit-Warren-Dearborn': (42.3314, -83.0458),
        'Seattle-Tacoma-Bellevue': (47.6062, -122.3321),
        'Minneapolis-St. Paul-Bloomington': (44.9778, -93.2650),
        'San Diego-Chula Vista-Carlsbad': (32.7157, -117.1611),
        'Tampa-St. Petersburg-Clearwater': (27.9506, -82.4572),
        'Denver-Aurora-Lakewood': (39.7392, -104.9903),
        'St. Louis': (38.6270, -90.1994),
        'Baltimore-Columbia-Towson': (39.2904, -76.6122),
        'Orlando-Kissimmee-Sanford': (28.5383, -81.3792),
        'Charlotte-Concord-Gastonia': (35.2271, -80.8431),
        'San Antonio-New Braunfels': (29.4241, -98.4936),
        'Portland-Vancouver-Hillsboro': (45.5152, -122.6784),
        'Pittsburgh': (40.4406, -79.9959),
        'Sacramento-Roseville-Folsom': (38.5816, -121.4944),
        'Austin-Round Rock-Georgetown': (30.2672, -97.7431),
        'Las Vegas-Henderson-Paradise': (36.1699, -115.1398),
        'Cincinnati': (39.1031, -84.5120),
        'Kansas City': (39.0997, -94.5786),
        'Columbus': (39.9612, -82.9988),
        'Cleveland-Elyria': (41.4993, -81.6944),
        'Indianapolis-Carmel-Anderson': (39.7684, -86.1581),
        'Nashville-Davidson--Murfreesboro--Franklin': (36.1627, -86.7816),
        'Jacksonville': (30.3322, -81.6557),
        'Memphis': (35.1495, -90.0490),
        'Oklahoma City': (35.4676, -97.5164),
        'Raleigh-Cary': (35.7796, -78.6382),
        'Louisville/Jefferson County': (38.2527, -85.7585),
        'Richmond': (37.5407, -77.4360),
        'Salt Lake City': (40.7608, -111.8910),
        'Birmingham-Hoover': (33.5186, -86.8104),
        'Grand Rapids-Kentwood': (42.9634, -85.6681),
        'Tucson': (32.2226, -110.9747),
        'Buffalo-Cheektowaga': (42.8864, -78.8784),
        'Rochester': (43.1566, -77.6088),
        'Tulsa': (36.1540, -95.9928),
        'Urban Honolulu': (21.3069, -157.8583),
        'Omaha-Council Bluffs': (41.2565, -95.9345),
        'Albuquerque': (35.0844, -106.6504),
        'Winter Park': (28.6000, -81.3392),
        'Kissimmee': (28.2920, -81.4076),
        'Cleveland': (41.4993, -81.6944),
        'Akron': (41.0814, -81.5190),
        'Toledo': (41.6528, -83.5379),
        'Youngstown-Warren-Boardman': (41.0998, -80.6495),
        'Dayton-Kettering': (39.7589, -84.1916),
        'Lakeland': (28.0395, -81.9498),
        'Winter Haven': (28.0225, -81.7329),
        'Lakeland-Winter Haven': (28.0395, -81.9498),
        'Deltona-Daytona Beach-Ormond Beach': (29.1872, -81.0487),
        'Palm Bay-Melbourne-Titusville': (28.0836, -80.6081),
        'Cape Coral-Fort Myers': (26.5629, -81.9495),
        'North Port-Sarasota-Bradenton': (27.3364, -82.5307),
        'Pensacola-Ferry Pass-Brent': (30.4213, -87.2169),
        'Tallahassee': (30.4383, -84.2807),
    }
    return metro_coords

def estimate_metro_coordinates(metro_name, state_code):
    """Estimate metro coordinates from name matching or state capital fallback."""
    coords = get_metro_coordinates()

    # Try exact match first
    for known_metro, coord in coords.items():
        if known_metro.lower() in metro_name.lower() or metro_name.lower() in known_metro.lower():
            return coord

    # Try city name extraction
    city = metro_name.split(',')[0].split('-')[0].strip()
    for known_metro, coord in coords.items():
        if city.lower() in known_metro.lower():
            return coord

    # Fallback: use state capital coordinates (rough approximation)
    state_capitals = {
        'AL': (32.377, -86.300), 'AK': (58.302, -134.420), 'AZ': (33.448, -112.074),
        'AR': (34.746, -92.290), 'CA': (38.576, -121.494), 'CO': (39.739, -104.990),
        'CT': (41.764, -72.683), 'DE': (39.157, -75.519), 'FL': (30.438, -84.281),
        'GA': (33.749, -84.388), 'HI': (21.307, -157.858), 'ID': (43.618, -116.215),
        'IL': (39.798, -89.654), 'IN': (39.768, -86.158), 'IA': (41.591, -93.604),
        'KS': (39.048, -95.678), 'KY': (38.187, -84.875), 'LA': (30.457, -91.187),
        'ME': (44.307, -69.782), 'MD': (38.979, -76.490), 'MA': (42.358, -71.064),
        'MI': (42.733, -84.555), 'MN': (44.955, -93.102), 'MS': (32.303, -90.182),
        'MO': (38.579, -92.173), 'MT': (46.585, -112.018), 'NE': (40.808, -96.700),
        'NV': (39.164, -119.766), 'NH': (43.206, -71.538), 'NJ': (40.221, -74.756),
        'NM': (35.682, -105.940), 'NY': (42.653, -73.757), 'NC': (35.780, -78.639),
        'ND': (46.820, -100.783), 'OH': (39.962, -82.999), 'OK': (35.492, -97.503),
        'OR': (44.938, -123.030), 'PA': (40.264, -76.884), 'RI': (41.824, -71.412),
        'SC': (34.000, -81.033), 'SD': (44.368, -100.336), 'TN': (36.166, -86.784),
        'TX': (30.275, -97.740), 'UT': (40.777, -111.888), 'VT': (44.260, -72.576),
        'VA': (37.538, -77.434), 'WA': (47.035, -122.905), 'WV': (38.336, -81.612),
        'WI': (43.074, -89.384), 'WY': (41.140, -104.820),
    }

    if state_code and state_code in state_capitals:
        return state_capitals[state_code]

    return None

def calculate_nearest_airport(metro_coords, airports):
    """Calculate distance to nearest FAA hub airport."""
    if metro_coords is None:
        return None, None

    min_dist = float('inf')
    nearest = None

    for airport in airports:
        dist = haversine(metro_coords[1], metro_coords[0], airport['lon'], airport['lat'])
        if dist < min_dist:
            min_dist = dist
            nearest = airport

    return nearest['iata'] if nearest else None, round(min_dist, 1) if min_dist != float('inf') else None

# ----- Score Calculation -----

def calculate_composite_score(row, all_data):
    """Calculate weighted composite score (0-100)."""
    scores = {}

    # Gross yield (higher is better, cap at 12% for normalization)
    if pd.notna(row.get('gross_yield')):
        scores['gross_yield'] = min(row['gross_yield'] / 12 * 100, 100)

    # Population growth (higher is better, normalize around -1% to 3%)
    if pd.notna(row.get('pop_growth_yoy')):
        scores['population_growth'] = max(0, min(100, (row['pop_growth_yoy'] + 1) / 4 * 100))

    # Job growth (higher is better, normalize around -2% to 5%)
    if pd.notna(row.get('job_growth_yoy')):
        scores['job_growth'] = max(0, min(100, (row['job_growth_yoy'] + 2) / 7 * 100))

    # Rent growth (higher is better, normalize around -2% to 8%)
    if pd.notna(row.get('rent_growth_yoy')):
        scores['rent_growth'] = max(0, min(100, (row['rent_growth_yoy'] + 2) / 10 * 100))

    # Landlord score (already 1-10, convert to 0-100)
    if pd.notna(row.get('landlord_score')):
        scores['landlord_score'] = row['landlord_score'] * 10

    # Vacancy rate (lower is better, normalize 0-20%)
    if pd.notna(row.get('vacancy_rate')):
        scores['vacancy_rate'] = max(0, 100 - (row['vacancy_rate'] / 20 * 100))

    # Calculate weighted average using available scores
    total_weight = 0
    weighted_sum = 0

    for metric, weight in WEIGHTS.items():
        if metric in scores:
            weighted_sum += scores[metric] * weight
            total_weight += weight

    if total_weight > 0:
        return round(weighted_sum / total_weight * (total_weight / sum(WEIGHTS.values())), 1)
    return None

def determine_market_type(row):
    """Determine market type tag based on criteria."""
    high_yield = row.get('gross_yield', 0) >= 8
    growth = (row.get('pop_growth_yoy', 0) >= 1.5) and (row.get('job_growth_yoy', 0) >= 1)

    if high_yield and growth:
        return 'Both'
    elif high_yield:
        return 'High Yield'
    elif growth:
        return 'Growth'
    return None

# ----- Main Build Function -----

def build_dataset():
    """Build complete metro dataset."""
    print("\n" + "="*60)
    print("BUILDING REAL ESTATE MARKET SCREENER DATASET")
    print("="*60 + "\n")

    # Load all data sources
    zillow = load_zillow_data()
    census_pop = load_census_population()
    bls_emp = load_bls_employment()
    census_vac = load_census_vacancy()
    airports = load_airports()
    landlord_scores = load_landlord_scores()
    crime_rates = load_crime_rates()

    # Start with Zillow as base (has most complete metro coverage)
    df = zillow.copy()
    df['metro_name_clean'] = df['RegionName'].apply(normalize_metro_name)

    # Deduplicate auxiliary data before merging
    census_pop_dedup = census_pop.drop_duplicates(subset=['metro_name_clean'], keep='first')
    bls_emp_dedup = bls_emp.drop_duplicates(subset=['metro_name_clean'], keep='first')
    census_vac_dedup = census_vac.drop_duplicates(subset=['metro_name_clean'], keep='first')

    # Merge population data
    df = df.merge(
        census_pop_dedup[['metro_name_clean', 'POPESTIMATE2024', 'pop_growth_yoy']],
        on='metro_name_clean',
        how='left'
    )

    # Merge employment data
    df = df.merge(
        bls_emp_dedup[['metro_name_clean', 'job_growth_yoy']],
        on='metro_name_clean',
        how='left'
    )

    # Merge vacancy data
    df = df.merge(
        census_vac_dedup[['metro_name_clean', 'vacancy_rate']],
        on='metro_name_clean',
        how='left'
    )

    # Add landlord scores
    df['landlord_score'] = df['state_code'].map(landlord_scores)

    # Add crime rates (state-level violent crime per 100k)
    df['crime_rate'] = df['state_code'].map(crime_rates)

    # Calculate airport proximity
    print("\nCalculating airport proximity...")
    airport_data = []
    for _, row in df.iterrows():
        coords = estimate_metro_coordinates(row['RegionName'], row['state_code'])
        nearest_iata, distance = calculate_nearest_airport(coords, airports)
        airport_data.append({'nearest_airport': nearest_iata, 'airport_distance_miles': distance})

    airport_df = pd.DataFrame(airport_data)
    df = pd.concat([df.reset_index(drop=True), airport_df], axis=1)

    # Calculate composite scores
    print("Calculating composite scores...")
    df['composite_score'] = df.apply(lambda row: calculate_composite_score(row, df), axis=1)

    # Determine market type
    df['market_type'] = df.apply(determine_market_type, axis=1)

    # Filter to valid records (must have price, rent, and composite score)
    valid = df.dropna(subset=['median_price', 'monthly_rent', 'composite_score'])

    print(f"\nFinal dataset: {len(valid)} metros with complete data")

    return valid

def export_json(df):
    """Export dataset to JSON format for frontend."""
    paths = get_paths()

    # Sort by composite score
    df = df.sort_values('composite_score', ascending=False).reset_index(drop=True)

    metros = []
    for rank, (_, row) in enumerate(df.iterrows(), 1):
        metro = {
            'rank': rank,
            'region_id': int(row['RegionID']),
            'name': row['RegionName'],
            'state': row['state_code'],
            'composite_score': row['composite_score'],
            'market_type': row['market_type'],
            'median_price': round(row['median_price']),
            'monthly_rent': round(row['monthly_rent']),
            'gross_yield': round(row['gross_yield'], 2),
            'rent_growth_yoy': round(row['rent_growth_yoy'], 2) if pd.notna(row['rent_growth_yoy']) else None,
            'pop_growth_yoy': round(row['pop_growth_yoy'], 2) if pd.notna(row['pop_growth_yoy']) else None,
            'job_growth_yoy': round(row['job_growth_yoy'], 2) if pd.notna(row['job_growth_yoy']) else None,
            'vacancy_rate': round(row['vacancy_rate'], 2) if pd.notna(row['vacancy_rate']) else None,
            'landlord_score': int(row['landlord_score']) if pd.notna(row['landlord_score']) else None,
            'nearest_airport': row['nearest_airport'],
            'airport_distance_miles': row['airport_distance_miles'],
            'population': int(row['POPESTIMATE2024']) if pd.notna(row.get('POPESTIMATE2024')) else None,
            'crime_rate': round(row['crime_rate'], 1) if pd.notna(row.get('crime_rate')) else None,
        }
        metros.append(metro)

    output = {
        'generated': pd.Timestamp.now().isoformat(),
        'count': len(metros),
        'weights': WEIGHTS,
        'metros': metros,
    }

    output_file = paths['output'] / 'metros.json'
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nExported {len(metros)} metros to {output_file}")

    # Also export airports for frontend
    airports = load_airports()
    airports_file = paths['output'] / 'airports.json'
    with open(airports_file, 'w') as f:
        json.dump(airports, f, indent=2)

    print(f"Exported {len(airports)} airports to {airports_file}")

    return output

def print_summary(data):
    """Print summary statistics."""
    metros = data['metros']

    print("\n" + "="*80)
    print("TOP 25 METROS BY COMPOSITE SCORE")
    print("="*80)
    print(f"{'Rank':<5} {'Metro':<40} {'Score':>6} {'Type':<12} {'Price':>10} {'Yield':>7} {'Airport':>8}")
    print("-"*80)

    for metro in metros[:25]:
        print(
            f"{metro['rank']:<5} "
            f"{metro['name'][:38]:<40} "
            f"{metro['composite_score']:>6.1f} "
            f"{(metro['market_type'] or '-'):<12} "
            f"${metro['median_price']:>8,} "
            f"{metro['gross_yield']:>6.2f}% "
            f"{metro['nearest_airport'] or 'N/A':>8}"
        )

    # Summary stats
    affordable = [m for m in metros if m['median_price'] < 300000]
    near_airport = [m for m in metros if m['airport_distance_miles'] and m['airport_distance_miles'] <= 30]
    high_yield = [m for m in metros if m['gross_yield'] >= 8]
    growth = [m for m in metros if m['market_type'] in ['Growth', 'Both']]

    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    print(f"Total metros: {len(metros)}")
    print(f"Affordable (<$300k): {len(affordable)}")
    print(f"Near major airport (<=30mi): {len(near_airport)}")
    print(f"High yield (>=8%): {len(high_yield)}")
    print(f"Growth markets: {len(growth)}")

    # Intersection
    sweet_spot = [m for m in metros
                  if m['median_price'] < 300000
                  and m['airport_distance_miles'] and m['airport_distance_miles'] <= 30
                  and m['gross_yield'] >= 5]
    print(f"\n** Sweet spot (<$300k, <30mi airport, >5% yield): {len(sweet_spot)} metros **")

    if sweet_spot:
        print("\nTop 10 'Sweet Spot' metros:")
        for i, m in enumerate(sweet_spot[:10], 1):
            print(f"  {i}. {m['name']} - Score: {m['composite_score']}, Yield: {m['gross_yield']}%, Airport: {m['nearest_airport']} ({m['airport_distance_miles']}mi)")

if __name__ == "__main__":
    df = build_dataset()
    data = export_json(df)
    print_summary(data)
