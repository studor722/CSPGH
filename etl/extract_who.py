import json
import os
from pathlib import Path
from typing import Optional
import pandas as pd
import requests

CACHE_DIR = Path("data/raw")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

WHO_BASE_URL = "https://ghoapi.azureedge.net/api"

# Default indicator codes relevant to life expectancy and lifestyle factors
WHO_INDICATORS = {
    "WHOSIS_000001": "Life expectancy at birth (years)",
    "WHOSIS_000002": "Healthy life expectancy (HALE) at birth (years)",
    "WHOSIS_000015": "Life expectancy at age 60 (years)",
    "M_Est_tob_curr_std": "Age-standardized prevalence of current tobacco use (%)",
    "SA_0000001400": "Alcohol per capita (15+) consumption (litres pure alcohol)",
    "NCD_BMI_30A": "Obesity among adults, BMI >= 30 (age-standardized %) (%)",
}


def extract_who_indicator(
    indicator_code: str, use_cache: bool = True
) -> pd.DataFrame:
    """
    Extract indicator data from WHO Global Health Observatory OData API.
    Returns normalized DataFrame with columns:
    [country_iso3, indicator_code, year, sex, value]
    """
    cache_file = CACHE_DIR / f"who_{indicator_code}.json"

    raw_data = None
    if use_cache and cache_file.exists():
        with open(cache_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    else:
        url = f"{WHO_BASE_URL}/{indicator_code}"
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            raw_data = resp.json()
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(raw_data, f)
        except Exception as e:
            if cache_file.exists():
                print(f"Warning: Failed to fetch {url} ({e}), falling back to cached file.")
                with open(cache_file, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
            else:
                raise e

    records = raw_data.get("value", [])
    rows = []
    for rec in records:
        # SpatialDimType: must be COUNTRY to exclude aggregates
        if rec.get("SpatialDimType") != "COUNTRY":
            continue

        country_iso3 = rec.get("SpatialDim")
        year = rec.get("TimeDim")
        val = rec.get("NumericValue")

        if not country_iso3 or year is None or val is None:
            continue

        # Map Dim1 sex dimension (SEX_BTSX, SEX_MLE, SEX_FMLE)
        dim1 = rec.get("Dim1") or "SEX_BTSX"
        sex = "BTSX"
        if "MLE" in dim1 and "FMLE" not in dim1:
            sex = "MLE"
        elif "FMLE" in dim1:
            sex = "FMLE"

        rows.append({
            "country_iso3": country_iso3.strip().upper(),
            "indicator_code": indicator_code,
            "year": int(year),
            "sex": sex,
            "value": float(val),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["country_iso3", "indicator_code", "year", "sex", "value"])
    return df
