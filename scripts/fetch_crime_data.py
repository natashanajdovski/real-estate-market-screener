"""
Fetch crime data from FBI Crime Data API.

Note: The FBI API only provides state-level crime rates, not MSA-level.
We'll use state-level violent crime rates as a proxy for metro areas.

API Documentation: https://cde.ucr.cjis.gov/
"""

import requests
import json
import time
from pathlib import Path

API_KEY = "ftayf6L7YL8Hs1nbDFTF3RnfQFETXw3emv1Mq3Th"
BASE_URL = "https://api.usa.gov/crime/fbi/cde"

# All US states
STATES = [
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
]

def get_data_dir():
    """Get the data directory path."""
    script_dir = Path(__file__).parent
    return script_dir.parent / "data"

def fetch_state_crime_rate(state_abbr, crime_type="violent-crime", from_date="01-2023", to_date="12-2023"):
    """Fetch crime rate for a state."""
    url = f"{BASE_URL}/summarized/state/{state_abbr}/{crime_type}"
    params = {
        "from": from_date,
        "to": to_date,
        "API_KEY": API_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"  Error for {state_abbr}: {response.status_code}")
            return None
    except Exception as e:
        print(f"  Exception for {state_abbr}: {e}")
        return None

def calculate_annual_rate(data, state_abbr):
    """Calculate annual crime rate from monthly data."""
    if not data or 'offenses' not in data:
        return None

    rates = data.get('offenses', {}).get('rates', {})

    # Find the state's offense data
    state_key = None
    for key in rates.keys():
        if state_abbr in key.upper() or 'Offenses' in key:
            if 'United States' not in key:
                state_key = key
                break

    if not state_key:
        return None

    monthly_rates = rates.get(state_key, {})
    if not monthly_rates:
        return None

    # Calculate average annual rate (sum of monthly rates)
    # The rates are per 100,000 per month, so we sum them for annual
    annual_rate = sum(monthly_rates.values())

    return round(annual_rate, 1)

def fetch_all_state_crime_rates():
    """Fetch crime rates for all states."""
    print("Fetching state-level violent crime rates from FBI API...")
    print(f"Period: 2023 (Jan-Dec)\n")

    crime_rates = {}

    for i, state in enumerate(STATES):
        print(f"[{i+1}/{len(STATES)}] Fetching {state}...", end=" ")

        data = fetch_state_crime_rate(state)
        rate = calculate_annual_rate(data, state)

        if rate:
            crime_rates[state] = rate
            print(f"{rate} per 100k")
        else:
            print("No data")

        # Rate limit - be nice to the API
        time.sleep(0.3)

    return crime_rates

def save_crime_data(crime_rates):
    """Save crime rates to JSON file."""
    data_dir = get_data_dir()

    output = {
        "description": "State-level violent crime rates per 100,000 population (annual, 2023)",
        "source": "FBI Crime Data Explorer API",
        "source_url": "https://cde.ucr.cjis.gov/",
        "methodology": "Sum of monthly violent crime rates for Jan-Dec 2023",
        "note": "State-level rates used as proxy for metro areas within each state",
        "year": 2023,
        "rates": crime_rates
    }

    output_file = data_dir / "crime_rates.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved crime rates for {len(crime_rates)} states to {output_file}")

    # Print summary
    sorted_rates = sorted(crime_rates.items(), key=lambda x: x[1], reverse=True)
    print("\nTop 10 highest violent crime rates:")
    for state, rate in sorted_rates[:10]:
        print(f"  {state}: {rate} per 100k")

    print("\nTop 10 lowest violent crime rates:")
    for state, rate in sorted_rates[-10:]:
        print(f"  {state}: {rate} per 100k")

    return output

if __name__ == "__main__":
    crime_rates = fetch_all_state_crime_rates()
    save_crime_data(crime_rates)
