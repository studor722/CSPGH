import logging
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_engine
from etl.clean import clean_observations
from etl.load import (
    get_or_create_indicator,
    get_or_create_source,
    log_import,
    upsert_countries,
    upsert_observations,
)
from etl.raw_files import read_source_url
from etl.transform_worldbank import (
    transform_worldbank_country_file,
    transform_worldbank_indicator_file,
)

logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "worldbank"
SOURCE_NAME = "World Bank"
SOURCE_URL = "https://data.worldbank.org/"

INDICATORS = [
    # (code, name, unit, cache filename)
    (
        "SH.XPD.CHEX.GD.ZS",
        "Current health expenditure",
        "% of GDP",
        "SH.XPD.CHEX.GD.ZS_2000-2023.json",
    ),
    (
        "NY.GDP.PCAP.CD",
        "GDP per capita",
        "current US$",
        "NY.GDP.PCAP.CD_2000-2023.json",
    ),
    (
        "SP.DYN.IMRT.IN",
        "Infant mortality rate",
        "per 1,000 live births",
        "SP.DYN.IMRT.IN_2000-2023.json",
    ),
    (
        "SH.IMM.MEAS",
        "Measles immunization",
        "% of children 12-23 months",
        "SH.IMM.MEAS_2000-2023.json",
    ),
]


def import_all() -> list[dict]:
    countries_path = RAW_DIR / "countries.json"
    if not countries_path.exists():
        raise RuntimeError(
            f"Missing {countries_path}; run etl.extract_worldbank.download_worldbank_countries() first"
        )

    results: list[dict] = []
    with Session(get_engine()) as session:
        countries = transform_worldbank_country_file(countries_path)
        upsert_countries(session, countries)
        session.commit()
        valid_iso3 = set(countries["iso3"])

        source_id = get_or_create_source(session, SOURCE_NAME, SOURCE_URL)
        session.commit()

        for code, name, unit, filename in INDICATORS:
            path = RAW_DIR / filename
            if not path.exists():
                print(f"{code:<22} SKIP (missing {path.name})")
                continue

            try:
                raw = transform_worldbank_indicator_file(path, code)
                cleaned = clean_observations(raw, valid_iso3)
                indicator_id = get_or_create_indicator(
                    session, code, name, unit, source_id
                )
                loaded = upsert_observations(session, cleaned, indicator_id)
                log_import(
                    session, SOURCE_NAME, code, read_source_url(path), loaded
                )
                session.commit()
                print(
                    f"{code:<22} raw={len(raw):>6} "
                    f"clean={len(cleaned):>6} loaded={loaded:>6}"
                )
                results.append(
                    {
                        "indicator_code": code,
                        "raw_count": len(raw),
                        "cleaned_count": len(cleaned),
                        "loaded_count": loaded,
                        "status": "success",
                    }
                )
            except (ValueError, OSError, SQLAlchemyError) as exc:
                session.rollback()
                logger.exception("%s: import failed", code)
                results.append(
                    {
                        "indicator_code": code,
                        "status": "error",
                        "message": f"{type(exc).__name__}: {exc}",
                    }
                )

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    res = import_all()
    failed = [r["indicator_code"] for r in res if r["status"] == "error"]
    if failed:
        raise SystemExit(f"{len(failed)} import(s) failed: {', '.join(failed)}")
