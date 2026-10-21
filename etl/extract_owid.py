import os
from pathlib import Path
import pandas as pd
import requests

CACHE_DIR = Path("data/raw")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

OWID_URLS = {
    "OWID_LIFE_EXP": "https://ourworldindata.org/grapher/life-expectancy.csv?v=1&csvType=full&useColumnShortNames=true",
    "OWID_SMOKING_PREV": "https://ourworldindata.org/grapher/share-of-adults-who-smoke.csv",
}


def extract_owid_dataset(dataset_key: str, use_cache: bool = True) -> pd.DataFrame:
    """
    Download and cache Our World in Data CSV dataset.
    Returns normalized DataFrame: [country_iso3, indicator_code, year, sex, value]
    """
    if dataset_key not in OWID_URLS:
        raise ValueError(f"Unknown OWID dataset: {dataset_key}")

    url = OWID_URLS[dataset_key]
    cache_file = CACHE_DIR / f"owid_{dataset_key.lower()}.csv"

    if not (use_cache and cache_file.exists()):
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(resp.text)

    df_raw = pd.read_csv(cache_file)

    # Standard OWID columns: Entity, Code, Year, and indicator value
    # Filter out rows where Code is NaN (regions like World, Africa, etc.)
    df_raw = df_raw.dropna(subset=["Code"])
    # Filter 3-letter codes
    df_raw = df_raw[df_raw["Code"].str.len() == 3]

    val_cols = [c for c in df_raw.columns if c not in ["Entity", "Code", "Year"]]
    if not val_cols:
        return pd.DataFrame(columns=["country_iso3", "indicator_code", "year", "sex", "value"])

    val_col = val_cols[0]
    df_normalized = pd.DataFrame({
        "country_iso3": df_raw["Code"].str.strip().str.upper(),
        "indicator_code": dataset_key,
        "year": df_raw["Year"].astype(int),
        "sex": "BTSX",
        "value": pd.to_numeric(df_raw[val_col], errors="coerce"),
    }).dropna(subset=["value"])

    return df_normalized
