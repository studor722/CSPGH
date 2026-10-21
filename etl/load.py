from typing import Dict, Optional
import pandas as pd
from sqlalchemy import text
from app.database import engine, SessionLocal
from app.models import Source, Country, Indicator, Observation, ImportLog


def load_sources() -> Dict[str, int]:
    """
    Ensure core sources exist and return dict mapping source name to source_id.
    """
    default_sources = [
        {"name": "WHO GHO", "url": "https://ghoapi.azureedge.net/api"},
        {"name": "World Bank", "url": "https://api.worldbank.org/v2"},
        {"name": "Our World in Data", "url": "https://ourworldindata.org"},
    ]

    source_map = {}
    with SessionLocal() as db:
        for s in default_sources:
            existing = db.query(Source).filter(Source.name == s["name"]).first()
            if not existing:
                src_obj = Source(name=s["name"], url=s["url"])
                db.add(src_obj)
                db.commit()
                db.refresh(src_obj)
                source_map[s["name"]] = src_obj.source_id
            else:
                source_map[s["name"]] = existing.source_id

    return source_map


def load_countries(df_countries: pd.DataFrame) -> int:
    """
    Upsert countries into country dimension table.
    """
    if df_countries.empty:
        return 0

    inserted_count = 0
    upsert_sql = text("""
        INSERT INTO country (iso3, iso2, name, region, income_group)
        VALUES (:iso3, :iso2, :name, :region, :income_group)
        ON CONFLICT (iso3) DO UPDATE SET
            iso2 = EXCLUDED.iso2,
            name = EXCLUDED.name,
            region = EXCLUDED.region,
            income_group = EXCLUDED.income_group;
    """)

    with engine.begin() as conn:
        records = df_countries.to_dict(orient="records")
        conn.execute(upsert_sql, records)
        inserted_count = len(records)

    return inserted_count


def get_or_create_indicator(
    code: str, name: str, unit: Optional[str], source_id: int
) -> int:
    """
    Get or create indicator record and return indicator_id.
    """
    with SessionLocal() as db:
        ind = db.query(Indicator).filter(Indicator.code == code).first()
        if not ind:
            ind = Indicator(code=code, name=name, unit=unit, source_id=source_id)
            db.add(ind)
            db.commit()
            db.refresh(ind)
        return ind.indicator_id


def load_observations(
    df: pd.DataFrame,
    indicator_id: int,
    source_name: str,
    indicator_code: str,
    source_url: str
) -> int:
    """
    Load observation rows with ON CONFLICT upsert, and write an audit record to import_log.
    """
    if df.empty:
        return 0

    if "age_group" not in df.columns:
        df["age_group"] = "ALL"
    if "sex" not in df.columns:
        df["sex"] = "BTSX"

    upsert_sql = text("""
        INSERT INTO observation (country_iso3, indicator_id, year, sex, age_group, value)
        VALUES (:country_iso3, :indicator_id, :year, :sex, :age_group, :value)
        ON CONFLICT ON CONSTRAINT uq_observation DO UPDATE SET
            value = EXCLUDED.value,
            imported_at = now();
    """)

    params = []
    for _, row in df.iterrows():
        params.append({
            "country_iso3": str(row["country_iso3"]),
            "indicator_id": indicator_id,
            "year": int(row["year"]),
            "sex": str(row["sex"]),
            "age_group": str(row["age_group"]),
            "value": float(row["value"]),
        })

    with engine.begin() as conn:
        conn.execute(upsert_sql, params)
        # Log into import_log table
        conn.execute(
            text("""
                INSERT INTO import_log (source_name, indicator_code, url, rows_loaded)
                VALUES (:source_name, :indicator_code, :url, :rows_loaded);
            """),
            {
                "source_name": source_name,
                "indicator_code": indicator_code,
                "url": source_url,
                "rows_loaded": len(params),
            }
        )

    return len(params)
