# Real Estate Market Screener

A static web-based tool for ranking US metro areas for single-family rental investment.

## Overview

This screener helps identify markets with strong rental investment fundamentals by combining multiple data sources into a composite score. It filters for affordable markets near major airports with solid yield and growth characteristics.

## Quick Start

```bash
python -m http.server 8000
```

Then visit http://localhost:8000

---

## Data Sources

| Data | Source | Period | Notes |
|------|--------|--------|-------|
| Home Values (ZHVI) | [Zillow Research](https://www.zillow.com/research/data/) | Dec 2025 | Median home value for single-family residences |
| Rent Index (ZORI) | [Zillow Research](https://www.zillow.com/research/data/) | Dec 2025 | Typical market rent (40th-60th percentile of listings) |
| Population | [Census Bureau CBSA Estimates](https://www.census.gov/data/tables/time-series/demo/popest/2020s-total-metro-and-micro-statistical-areas.html) | 2023-2024 | Year-over-year change |
| Employment | [BLS QCEW](https://www.bls.gov/cew/) | 2024 Annual | Private sector employment |
| Vacancy Rates | [Census ACS Table B25002](https://data.census.gov/table?q=B25002) | 2023 | Housing unit vacancy |
| Crime Rates | [FBI Crime Data Explorer](https://cde.ucr.cjis.gov/) | 2023 | State-level violent crime per 100k |
| Airports | [FAA Hub Classifications](https://www.faa.gov/airports/planning_capacity/categories) | 2024 | Large and Medium hub airports only |
| Landlord Scores | Manual Research | 2024 | Based on eviction laws, rent control, tenant protections |

---

## Metrics Definitions

### Composite Score (0-100)

A weighted average of six factors, each normalized to a 0-100 scale:

| Factor | Weight | Description | Raw Range | Normalization |
|--------|--------|-------------|-----------|---------------|
| **Gross Yield** | 30% | Annual rental income / purchase price | 0-12%+ | 0-12% maps to 0-100 (capped at 100) |
| **Population Growth** | 20% | Year-over-year population change | -1% to +3% | Linear scale to 0-100 |
| **Job Growth** | 15% | Year-over-year private employment change | -2% to +5% | Linear scale to 0-100 |
| **Rent Growth** | 15% | Year-over-year ZORI change | -2% to +8% | Linear scale to 0-100 |
| **Landlord Score** | 10% | State-level landlord-friendliness (1-10) | 1-10 | Multiplied by 10 |
| **Vacancy Rate** | 10% | Housing unit vacancy percentage | 0-20% | **Inverted** (lower vacancy = higher score) |

### Individual Metrics

| Metric | Formula | Source |
|--------|---------|--------|
| **Median Price** | Direct from ZHVI | Zillow |
| **Monthly Rent** | Direct from ZORI | Zillow |
| **Gross Yield** | `(Monthly Rent × 12) / Median Price × 100` | Calculated |
| **Rent Growth YoY** | `(Current Rent - Rent 12mo ago) / Rent 12mo ago × 100` | Zillow |
| **Pop Growth YoY** | `(Pop 2024 - Pop 2023) / Pop 2023 × 100` | Census |
| **Job Growth YoY** | Year-over-year employment change | BLS QCEW |
| **Vacancy Rate** | `Vacant Units / Total Units × 100` | Census ACS |
| **Crime Rate** | Violent crimes per 100,000 population | FBI (state-level) |
| **Airport Distance** | Haversine distance from metro center to nearest hub | Calculated |

### Market Type Tags

| Tag | Criteria |
|-----|----------|
| **High Yield** | Gross yield >= 8% |
| **Growth** | Population growth >= 1.5% AND Job growth >= 1% |
| **Both** | Meets both High Yield and Growth criteria |
| *(none)* | Does not meet either threshold |

---

## Default Filters

| Filter | Default | Purpose |
|--------|---------|---------|
| Max Price | $300,000 | Budget constraint |
| Min Yield | 5% | Minimum acceptable gross yield |
| Max Airport Distance | 30 miles | Proximity to FAA hub airports |
| Market Type | All | No market type filter |
| States | All selected | No state exclusions |

---

## Features

- **672 US metro areas** ranked by composite score
- **Sortable columns** - Click any column header to sort
- **Real-time filtering** - Adjust sliders and see results immediately
- **Searchable state filter** - With select/deselect all buttons
- **Detail modal** - Click any row for full score breakdown with source links
- **Zillow links** - Direct links to listings filtered for 1950-1975 builds
- **CSV export** - Download filtered results

---

## Project Structure

```
real-estate-investment-analysis/
├── index.html              # Main web interface
├── styles.css              # Styling
├── app.js                  # Frontend logic
├── README.md               # This file
├── data/
│   ├── metros.json         # Generated metro dataset (672 metros)
│   ├── airports.json       # FAA hub airports list
│   ├── faa_hubs.json       # Airport coordinates (66 airports)
│   ├── landlord_scores.json # State landlord ratings (1-10)
│   ├── crime_rates.json    # FBI crime data by state
│   └── raw/                # Downloaded source data
│       ├── zhvi_metro.csv
│       ├── zori_metro.csv
│       ├── census_cbsa_pop.csv
│       └── qcew_2024_msa/
└── scripts/
    ├── fetch_data.py       # Download Zillow data
    ├── fetch_crime_data.py # Download FBI crime data
    ├── build_dataset.py    # Main data pipeline
    └── calculate_scores.py # Basic score calculations
```

---

## Refreshing Data

### Prerequisites

- Python 3.8+
- Required packages: `pandas`, `numpy`, `requests`

### Steps

```bash
# 1. Fetch Zillow data
python scripts/fetch_data.py

# 2. Fetch FBI crime data (API key in script)
python scripts/fetch_crime_data.py

# 3. Build the dataset
python scripts/build_dataset.py

# 4. Start local server
python -m http.server 8000
```

---

## Limitations

| Limitation | Details |
|------------|---------|
| **Gross yield ≠ Net yield** | Does not account for taxes, insurance, maintenance, vacancy, or management fees |
| **Crime data is state-level** | FBI API only provides state aggregates, not MSA-level data |
| **Airport distance is approximate** | Based on metro center coordinates, not actual driving distance |
| **Landlord scores are subjective** | Based on general legal environment research |
| **ZORI reflects market rents** | May not match achievable rents for specific properties |

---

## License

MIT
