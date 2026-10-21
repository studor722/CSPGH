import json
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import requests

CACHE_DIR = Path("data/raw")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

WB_BASE_URL = "https://api.worldbank.org/v2"

WB_INDICATORS = {
    "SP.DYN.LE00.IN": "Life expectancy at birth, total (years)",
    "SH.PRV.SMOK": "Prevalence of current tobacco use (% of adults)",
    "SH.XPD.CHEX.GD.ZS": "Current health expenditure (% of GDP)",
    "NY.GDP.PCAP.CD": "GDP per capita (current US$)",
}


def extract_worldbank_countries(use_cache: bool = True) -> pd.DataFrame:
    """
    Extract sovereign country metadata from the World Bank API.
    Returns DataFrame: [iso3, iso2, name, region, income_group]
    """
    cache_file = CACHE_DIR / "worldbank_countries.json"
    raw_data = None

    if use_cache and cache_file.exists():
        with open(cache_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    else:
        url = f"{WB_BASE_URL}/country?format=json&per_page=400"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        raw_data = resp.json()
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(raw_data, f)

    countries = []
    if len(raw_data) > 1 and isinstance(raw_data[1], list):
        for c in raw_data[1]:
            # Filter out aggregate regions (World, Latin America, etc.)
            region_name = c.get("region", {}).get("value", "")
            if region_name == "Aggregates" or not c.get("id"):
                continue

            countries.append({
                "iso3": c.get("id", "").strip().upper(),
                "iso2": c.get("iso2Code", "").strip().upper(),
                "name": c.get("name", "").strip(),
                "region": region_name,
                "income_group": c.get("incomeLevel", {}).get("value", ""),
            })

    return pd.DataFrame(countries)


def extract_worldbank_indicator(
    indicator_code: str,
    date_range: str = "2000:2023",
    use_cache: bool = True
) -> pd.DataFrame:
    """
    Extract indicator timeseries from World Bank Indicators API v2.
    Returns normalized DataFrame: [country_iso3, indicator_code, year, sex, value]
    """
    cache_file = CACHE_DIR / f"wb_{indicator_code}.json"
    raw_data = None

    if use_cache and cache_file.exists():
        with open(cache_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    else:
        url = f"{WB_BASE_URL}/country/all/indicator/{indicator_code}?format=json&date={date_range}&per_page=15000"
        resp = requests.get(url, timeout=45)
        resp.raise_for_status()
        raw_data = resp.json()
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(raw_data, f)

    rows = []
    if len(raw_data) > 1 and isinstance(raw_data[1], list):
        for item in raw_data[1]:
            c_iso3 = item.get("countryiso3code")
            val = item.get("value")
            year = item.get("date")

            if not c_iso3 or val is None or not year:
                continue

            rows.append({
                "country_iso3": c_iso3.strip().upper(),
                "indicator_code": indicator_code,
                "year": int(year),
                "sex": "BTSX",
                "value": float(val),
            })

    return pd.DataFrame(rows)
