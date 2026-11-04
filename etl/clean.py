import logging
from typing import NamedTuple

import pandas as pd

from app.models import Sex

logger = logging.getLogger(__name__)

_OUTPUT_COLUMNS = [
    "country_iso3",
    "indicator_code",
    "year",
    "sex",
    "value",
    "is_outlier",
]
_KEY_COLUMNS = ["country_iso3", "indicator_code", "year", "sex"]

# WHO GHO uses "SEX_BTSX" etc.; derived from the model so the two cannot drift.
_SEX_MAP = {f"SEX_{sex.value}": sex.value for sex in Sex}
_VALID_SEX = {sex.value for sex in Sex}


class _Bounds(NamedTuple):
    """Plausible value range; ``high`` is inclusive, ``low`` if ``low_inclusive``."""

    low: float
    high: float
    low_inclusive: bool = True


# Per-indicator plausibility bounds. Values outside them are dropped before
# reaching the database. A life expectancy or GDP per capita of exactly 0 is
# not a real measurement, so those lower bounds are exclusive.
_INDICATOR_BOUNDS = {
    "SH.XPD.CHEX.GD.ZS": _Bounds(0, 100),
    "SH.IMM.MEAS": _Bounds(0, 100),
    "SP.DYN.IMRT.IN": _Bounds(0, 1000),
    "NY.GDP.PCAP.CD": _Bounds(0, 500_000, low_inclusive=False),
    "WHOSIS_000001": _Bounds(0, 120, low_inclusive=False),
    "WHOSIS_000002": _Bounds(0, 120, low_inclusive=False),
    "OWID_LIFE_EXPECTANCY": _Bounds(0, 120, low_inclusive=False),
    "M_Est_tob_curr_std": _Bounds(0, 100),
    "SA_0000001400": _Bounds(0, 100),
    "NCD_BMI_30A": _Bounds(0, 100),
    "SH.PRV.SMOK": _Bounds(0, 100),
}


def _drop(cleaned: pd.DataFrame, mask: pd.Series, reason: str) -> pd.DataFrame:
    """Drop the rows where ``mask`` is true, logging how many and why."""
    dropped = int(mask.sum())
    if dropped:
        logger.info("dropped %d observation rows: %s", dropped, reason)
    return cleaned[~mask]


def _out_of_bounds(cleaned: pd.DataFrame) -> pd.Series:
    mask = pd.Series(False, index=cleaned.index)
    for code, bounds in _INDICATOR_BOUNDS.items():
        val = cleaned["value"]
        too_low = val < bounds.low if bounds.low_inclusive else val <= bounds.low
        mask |= (cleaned["indicator_code"] == code) & (too_low | (val > bounds.high))
    return mask


def clean_observations(
    normalized: pd.DataFrame,
    valid_iso3: set[str],
    *,
    year_window: tuple[int, int] = (2000, 2024),
) -> pd.DataFrame:
    """
    Cleans raw normalized observations applying validation, range filtering,
    type casting, deduplication, and IQR outlier detection.
    """
    if normalized.empty:
        return pd.DataFrame(columns=_OUTPUT_COLUMNS)

    cleaned = normalized.copy()

    # 1. Standardize and filter countries
    cleaned["country_iso3"] = (
        cleaned["country_iso3"].astype("string").str.strip().str.upper()
    )
    cleaned = _drop(
        cleaned,
        ~cleaned["country_iso3"].isin(valid_iso3).fillna(False).astype(bool),
        "not a known country (aggregate, region or missing code)",
    )

    # 2. Type conversions and missing value dropping
    cleaned["year"] = pd.to_numeric(cleaned["year"], errors="coerce")
    cleaned["value"] = pd.to_numeric(cleaned["value"], errors="coerce")
    cleaned = _drop(
        cleaned,
        cleaned["year"].isna() | cleaned["value"].isna(),
        "missing or non-numeric year/value",
    )

    # 3. Whole year validation
    cleaned = _drop(cleaned, cleaned["year"] % 1 != 0, "year is not a whole number")
    cleaned["year"] = cleaned["year"].astype(int)

    # 4. Year window filtering
    year_low, year_high = year_window
    cleaned = _drop(
        cleaned,
        (cleaned["year"] < year_low) | (cleaned["year"] > year_high),
        f"year outside {year_low}-{year_high}",
    )

    # 5. Harmonize sex categories
    cleaned["sex"] = cleaned["sex"].fillna(Sex.BOTH.value).replace(_SEX_MAP)
    cleaned = _drop(cleaned, ~cleaned["sex"].isin(_VALID_SEX), "unknown sex code")

    # 6. Plausibility bounds
    cleaned = _drop(cleaned, _out_of_bounds(cleaned), "value outside plausible bounds")

    # 7. Deduplication on natural key
    cleaned = _drop(
        cleaned,
        cleaned.duplicated(subset=_KEY_COLUMNS, keep="last"),
        "duplicate (country, indicator, year, sex); kept the last",
    )

    # 8. Task 2.2: IQR Outlier Flagging
    cleaned["is_outlier"] = False
    for code in cleaned["indicator_code"].unique():
        mask_code = cleaned["indicator_code"] == code
        vals = cleaned.loc[mask_code, "value"]
        if len(vals) >= 4:
            q1 = float(vals.quantile(0.25))
            q3 = float(vals.quantile(0.75))
            iqr = q3 - q1
            low_b = q1 - 1.5 * iqr
            high_b = q3 + 1.5 * iqr
            outlier_mask = mask_code & ((cleaned["value"] < low_b) | (cleaned["value"] > high_b))
            cleaned.loc[outlier_mask, "is_outlier"] = True
            n_outliers = int(outlier_mask.sum())
            if n_outliers:
                logger.info(
                    "flagged %d IQR outlier rows for %s (Q1=%.2f, Q3=%.2f, IQR=%.2f, bounds=[%.2f, %.2f])",
                    n_outliers,
                    code,
                    q1,
                    q3,
                    iqr,
                    low_b,
                    high_b,
                )

    return cleaned[_OUTPUT_COLUMNS]
