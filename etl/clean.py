import pycountry
import pandas as pd
from typing import Set, Dict, Optional

# Manual exception dictionary for non-standard country names / codes across sources
COUNTRY_NAME_OVERRIDES: Dict[str, str] = {
    "Viet Nam": "VNM",
    "Vietnam": "VNM",
    "United States of America": "USA",
    "United States": "USA",
    "United Kingdom": "GBR",
    "Russian Federation": "RUS",
    "Russia": "RUS",
    "Iran (Islamic Republic of)": "IRN",
    "Bolivia (Plurinational State of)": "BOL",
    "Venezuela (Bolivarian Republic of)": "VEN",
    "Syrian Arab Republic": "SYR",
    "Tanzania, United Republic of": "TZA",
    "Democratic Republic of the Congo": "COD",
    "Congo, Dem. Rep.": "COD",
    "Congo, Rep.": "COG",
    "Korea, Rep.": "KOR",
    "South Korea": "KOR",
    "Korea, Dem. People's Rep.": "PRK",
    "North Korea": "PRK",
    "Czechia": "CZE",
    "Czech Republic": "CZE",
}


def get_valid_iso3_codes() -> Set[str]:
    """Return all valid 3-letter ISO alpha_3 country codes."""
    return {c.alpha_3 for c in pycountry.countries}


def resolve_country_iso3(name_or_code: str) -> Optional[str]:
    """
    Resolve a country string (name, ISO2, or ISO3) into a standardized ISO3 code.
    Returns None if the entity is an aggregate or unresolvable.
    """
    if not name_or_code or not isinstance(name_or_code, str):
        return None

    cleaned = name_or_code.strip()

    # Direct 3-letter match
    if len(cleaned) == 3:
        code_upper = cleaned.upper()
        if pycountry.countries.get(alpha_3=code_upper):
            return code_upper

    # Check override dictionary
    if cleaned in COUNTRY_NAME_OVERRIDES:
        return COUNTRY_NAME_OVERRIDES[cleaned]

    # Try pycountry by ISO2
    if len(cleaned) == 2:
        c = pycountry.countries.get(alpha_2=cleaned.upper())
        if c:
            return c.alpha_3

    # Try pycountry fuzzy search
    try:
        match = pycountry.countries.search_fuzzy(cleaned)
        if match:
            return match[0].alpha_3
    except LookupError:
        pass

    return None


def clean_observations(
    df: pd.DataFrame,
    valid_country_codes: Optional[Set[str]] = None
) -> pd.DataFrame:
    """
    Clean and validate normalized observation DataFrame:
    - Verifies 3-letter ISO code against country dimension
    - Removes non-finite or empty values
    - Strips whitespace
    - Ensures valid year range (1950 - 2030)
    - Deduplicates on [country_iso3, indicator_code, year, sex, age_group]
    """
    if df.empty:
        return df

    cleaned = df.copy()

    if "age_group" not in cleaned.columns:
        cleaned["age_group"] = "ALL"
    if "sex" not in cleaned.columns:
        cleaned["sex"] = "BTSX"

    # Normalize ISO3
    cleaned["country_iso3"] = cleaned["country_iso3"].astype(str).str.strip().str.upper()

    # Filter by valid country list if provided
    if valid_country_codes is not None:
        cleaned = cleaned[cleaned["country_iso3"].isin(valid_country_codes)]

    # Clean numeric value
    cleaned["value"] = pd.to_numeric(cleaned["value"], errors="coerce")
    cleaned = cleaned.dropna(subset=["value", "country_iso3", "year"])

    # Clean year
    cleaned["year"] = cleaned["year"].astype(int)
    cleaned = cleaned[(cleaned["year"] >= 1950) & (cleaned["year"] <= 2030)]

    # Deduplicate keeping the latest
    cleaned = cleaned.drop_duplicates(
        subset=["country_iso3", "indicator_code", "year", "sex", "age_group"],
        keep="last"
    )

    return cleaned
