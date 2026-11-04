import logging
from datetime import datetime
from typing import Dict, Any, Optional
import requests
from sqlalchemy import text
from app.database import engine, SessionLocal
from app.models import Country, Indicator, Source, Observation, ImportLog

logger = logging.getLogger("RealTimeETL")


def sync_country_realtime(country_iso3: str) -> Dict[str, Any]:
    """
    Real-Time Data Pipeline:
    1. Queries external APIs (World Bank v2 & WHO GHO) on-the-fly for a specific country.
    2. Parses raw JSON responses and handles schema variations.
    3. Normalizes and validates data types (ISO3, year, numeric values).
    4. Upserts fresh records into the PostgreSQL observation table.
    5. Returns formatted real-time metrics.
    """
    iso3_clean = country_iso3.strip().upper()
    logger.info(f"Triggering real-time ETL sync for country {iso3_clean}...")

    results = {
        "country_iso3": iso3_clean,
        "synced_at": datetime.now().isoformat(),
        "indicators_synced": 0,
        "life_expectancy": None,
        "reference_year": None,
        "source": None,
    }

    # 1. Fetch live World Bank Life Expectancy (SP.DYN.LE00.IN)
    wb_url = f"https://api.worldbank.org/v2/country/{iso3_clean}/indicator/SP.DYN.LE00.IN?format=json&date=2015:2024&per_page=10"
    try:
        resp = requests.get(wb_url, timeout=12)
        if resp.status_code == 200:
            payload = resp.json()
            if len(payload) > 1 and isinstance(payload[1], list):
                # Find most recent non-null entry
                for entry in payload[1]:
                    val = entry.get("value")
                    yr = entry.get("date")
                    if val is not None and yr is not None:
                        results["life_expectancy"] = float(val)
                        results["reference_year"] = int(yr)
                        results["source"] = "World Bank API v2 (Live)"
                        _upsert_single_observation(
                            country_iso3=iso3_clean,
                            indicator_code="SP.DYN.LE00.IN",
                            indicator_name="Life expectancy at birth, total (World Bank)",
                            unit="years",
                            source_name="World Bank",
                            year=int(yr),
                            sex="BTSX",
                            value=float(val),
                            url=wb_url,
                        )
                        results["indicators_synced"] += 1
                        break
    except Exception as e:
        logger.warning(f"World Bank real-time fetch failed for {iso3_clean}: {e}")

    # 2. If World Bank had no recent value, fetch live from WHO GHO
    if results["life_expectancy"] is None:
        who_url = f"https://ghoapi.azureedge.net/api/WHOSIS_000001?$filter=SpatialDim eq '{iso3_clean}' and Dim1 eq 'SEX_BTSX'&$top=5"
        try:
            resp = requests.get(who_url, timeout=12)
            if resp.status_code == 200:
                data = resp.json().get("value", [])
                if data:
                    # Sort by TimeDim descending
                    data_sorted = sorted(data, key=lambda x: x.get("TimeDim", 0), reverse=True)
                    latest = data_sorted[0]
                    val = latest.get("NumericValue")
                    yr = latest.get("TimeDim")
                    if val is not None:
                        results["life_expectancy"] = float(val)
                        results["reference_year"] = int(yr)
                        results["source"] = "WHO GHO OData API (Live)"
                        _upsert_single_observation(
                            country_iso3=iso3_clean,
                            indicator_code="WHOSIS_000001",
                            indicator_name="Life expectancy at birth (years)",
                            unit="years",
                            source_name="WHO GHO",
                            year=int(yr),
                            sex="BTSX",
                            value=float(val),
                            url=who_url,
                        )
                        results["indicators_synced"] += 1
        except Exception as e:
            logger.warning(f"WHO GHO real-time fetch failed for {iso3_clean}: {e}")

    return results


def _upsert_single_observation(
    country_iso3: str,
    indicator_code: str,
    indicator_name: str,
    unit: str,
    source_name: str,
    year: int,
    sex: str,
    value: float,
    url: str,
):
    """Upsert helper for live pipeline stream."""
    with SessionLocal() as db:
        # Ensure source
        src = db.query(Source).filter(Source.name == source_name).first()
        if not src:
            src = Source(name=source_name, url=url)
            db.add(src)
            db.commit()
            db.refresh(src)

        # Ensure indicator
        ind = db.query(Indicator).filter(Indicator.code == indicator_code).first()
        if not ind:
            ind = Indicator(code=indicator_code, name=indicator_name, unit=unit, source_id=src.source_id)
            db.add(ind)
            db.commit()
            db.refresh(ind)
        ind_id = ind.indicator_id

    upsert_sql = text("""
        INSERT INTO observation (country_iso3, indicator_id, year, sex, age_group, value)
        VALUES (:c_iso3, :ind_id, :yr, :sex, 'ALL', :val)
        ON CONFLICT ON CONSTRAINT uq_observation DO UPDATE SET
            value = EXCLUDED.value,
            imported_at = now();
    """)

    audit_sql = text("""
        INSERT INTO import_log (source_name, indicator_code, url, rows_loaded)
        VALUES (:src_name, :ind_code, :url, 1);
    """)

    with engine.begin() as conn:
        conn.execute(upsert_sql, {
            "c_iso3": country_iso3,
            "ind_id": ind_id,
            "yr": year,
            "sex": sex,
            "val": value,
        })
        conn.execute(audit_sql, {
            "src_name": source_name,
            "ind_code": indicator_code,
            "url": url,
        })
