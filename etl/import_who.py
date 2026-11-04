import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_engine
from app.models import Country
from etl.clean import clean_observations
from etl.load import (
    get_or_create_indicator,
    get_or_create_source,
    log_import,
    upsert_observations,
)
from etl.raw_files import read_source_url
from etl.transform_who import transform_who_file

logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "who"
SOURCE_NAME = "WHO"
SOURCE_URL = "https://www.who.int/data/gho"

INDICATORS = [
    # (code, name, unit, cache filename)
    (
        "WHOSIS_000001",
        "Life expectancy at birth",
        "years",
        "WHOSIS_000001_from2000.json",
    ),
    (
        "M_Est_tob_curr_std",
        "Age-standardized tobacco use prevalence",
        "%",
        "M_Est_tob_curr_std_from2000.json",
    ),
]


def import_all() -> list[dict]:
    results: list[dict] = []
    with Session(get_engine()) as session:
        valid_iso3 = set(session.scalars(select(Country.iso3)))
        if not valid_iso3:
            raise RuntimeError(
                "The country table is empty; run `python -m etl.import_worldbank` first."
            )

        source_id = get_or_create_source(session, SOURCE_NAME, SOURCE_URL)
        session.commit()

        for code, name, unit, filename in INDICATORS:
            path = RAW_DIR / filename
            if not path.exists():
                print(f"{code:<22} SKIP (missing {path.name})")
                continue

            try:
                raw = transform_who_file(path, code)
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
