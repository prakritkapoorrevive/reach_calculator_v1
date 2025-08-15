# ZIP Finder App

This app finds ZIP codes within a radius of a given origin ZIP, merges population data, and calculates reach estimates based on advertising deals.

## Setup

1. Clone the repo:
```bash
git clone <your_repo_url>
cd zip_finder_app
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run locally:
```bash
streamlit run app.py
```

## Data Files
- `census_data_cleaned.csv` → Population & demographics by ZIP
- `zip_data_trimmed.csv` → ZIP + lat/lng coordinates
- `deals_data_cleaned.csv` → Deal reach & budget info
