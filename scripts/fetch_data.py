"""
Fetch Zillow ZHVI (Home Values) and ZORI (Rent) data for metro areas.

Data sources:
- ZHVI: https://www.zillow.com/research/data/ (Metro & U.S. > ZHVI All Homes)
- ZORI: https://www.zillow.com/research/data/ (Rentals > ZORI All Homes + Multifamily)
"""

import os
import requests
from pathlib import Path

# Zillow data URLs (Metro level, seasonally adjusted)
ZILLOW_URLS = {
    # ZHVI All Homes (SFR + Condo) - Metro level
    "zhvi_metro": "https://files.zillowstatic.com/research/public_csvs/zhvi/Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv",

    # ZORI All Homes + Multifamily - Metro level
    "zori_metro": "https://files.zillowstatic.com/research/public_csvs/zori/Metro_zori_uc_sfrcondomfr_sm_sa_month.csv",

    # ZHVI at Zip level for drill-down
    "zhvi_zip": "https://files.zillowstatic.com/research/public_csvs/zhvi/Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv",

    # ZORI at Zip level for drill-down
    "zori_zip": "https://files.zillowstatic.com/research/public_csvs/zori/Zip_zori_uc_sfrcondomfr_sm_sa_month.csv",
}

def get_data_dir() -> Path:
    """Get the data directory path."""
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data" / "raw"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir

def download_file(url: str, filename: str) -> Path:
    """Download a file from URL and save to data directory."""
    data_dir = get_data_dir()
    filepath = data_dir / filename

    print(f"Downloading {filename}...")
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    filepath.write_bytes(response.content)
    print(f"  Saved to {filepath} ({len(response.content) / 1024 / 1024:.1f} MB)")

    return filepath

def fetch_zillow_data():
    """Download all Zillow data files."""
    print("Fetching Zillow data...\n")

    files_downloaded = {}

    for name, url in ZILLOW_URLS.items():
        try:
            filepath = download_file(url, f"{name}.csv")
            files_downloaded[name] = filepath
        except requests.RequestException as e:
            print(f"  ERROR downloading {name}: {e}")

    print(f"\nDownloaded {len(files_downloaded)} files.")
    return files_downloaded

if __name__ == "__main__":
    fetch_zillow_data()
