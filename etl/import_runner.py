"""Shared transform-and-load runner used by per-source ETL modules."""

from dataclasses import dataclass
import logging
from pathlib import Path
import sys
from typing import Callable

import pandas as pd
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
    upsert_countries,
    upsert_observations,
)
from etl.raw_files import read_source_url
from etl.step_result import StepResult, StepStatus

logger = logging.getLogger(__name__)

TransformIndicatorFn = Callable[[Path, str], pd.DataFrame]
TransformCountriesFn = Callable[[Path], pd.DataFrame]


@dataclass(frozen=True, slots=True)
class SourceSpec:
    """Metadata describing an upstream data provider and its raw landing directory."""

    name: str
    url: str
    raw_dir: Path


@dataclass(frozen=True, slots=True)
class IndicatorSpec:
    """Metadata mapping an internal indicator code to its upstream ID and cache file."""

    code: str
    remote_id: str
    name: str
    unit: str
    raw_filename: str


def _import_indicator(
    session: Session,
    source: SourceSpec,
    source_id: int,
    spec: IndicatorSpec,
    valid_iso3: set[str],
    transform_file: TransformIndicatorFn,
) -> StepResult:
    path = source.raw_dir / spec.raw_filename
    if not path.exists():
        return StepResult(
            source=source.name,
            item=spec.code,
            status=StepStatus.SKIPPED,
            detail=f"missing {path.name}",
        )

    try:
        raw = transform_file(path, spec.code)
        cleaned = clean_observations(raw, valid_iso3)
        indicator_id = get_or_create_indicator(
            session, spec.code, spec.name, spec.unit, source_id
        )
        loaded = upsert_observations(session, cleaned, indicator_id)
        log_import(session, source.name, spec.code, read_source_url(path), loaded)
        session.commit()
    except (ValueError, OSError, SQLAlchemyError) as exc:
        session.rollback()
        logger.warning("%s %s failed: %s", source.name, spec.code, exc)
        return StepResult.from_error(source.name, spec.code, exc)

    return StepResult(
        source=source.name,
        item=spec.code,
        status=StepStatus.OK,
        detail=f"{loaded} rows loaded",
    )


def import_for_loaded_countries(
    source: SourceSpec,
    indicators: tuple[IndicatorSpec, ...],
    transform_file: TransformIndicatorFn,
    *,
    missing_countries_hint: str,
) -> list[StepResult]:
    """Transform and load indicators for a source after countries already exist."""
    results: list[StepResult] = []
    with Session(get_engine()) as session:
        valid_iso3 = set(session.scalars(select(Country.iso3)))
        if not valid_iso3:
            return [
                StepResult(
                    source=source.name,
                    item="countries",
                    status=StepStatus.FAILED,
                    detail=missing_countries_hint,
                )
            ]

        source_id = get_or_create_source(session, source.name, source.url)
        session.commit()

        for spec in indicators:
            results.append(
                _import_indicator(
                    session, source, source_id, spec, valid_iso3, transform_file
                )
            )
    return results


def import_worldbank_source(
    source: SourceSpec,
    indicators: tuple[IndicatorSpec, ...],
    transform_countries: TransformCountriesFn,
    transform_indicator: TransformIndicatorFn,
    *,
    countries_filename: str = "countries.json",
) -> list[StepResult]:
    """Load the World Bank country catalog first, then its configured indicators."""
    countries_path = source.raw_dir / countries_filename
    if not countries_path.exists():
        return [
            StepResult(
                source=source.name,
                item="countries",
                status=StepStatus.FAILED,
                detail=f"missing {countries_path}; run extract first",
            )
        ]

    results: list[StepResult] = []
    with Session(get_engine()) as session:
        try:
            countries_df = transform_countries(countries_path)
            upsert_countries(session, countries_df)
            session.commit()
            results.append(
                StepResult(
                    source=source.name,
                    item="countries",
                    status=StepStatus.OK,
                    detail=f"{len(countries_df)} countries loaded",
                )
            )
        except (ValueError, OSError, SQLAlchemyError) as exc:
            session.rollback()
            logger.warning("%s countries failed: %s", source.name, exc)
            return [StepResult.from_error(source.name, "countries", exc)]

        valid_iso3 = set(session.scalars(select(Country.iso3)))
        source_id = get_or_create_source(session, source.name, source.url)
        session.commit()

        for spec in indicators:
            results.append(
                _import_indicator(
                    session, source, source_id, spec, valid_iso3, transform_indicator
                )
            )
    return results


def report_and_exit_on_failure(results: list[StepResult]) -> None:
    """Print CLI step summaries and exit non-zero if any step failed."""
    for result in results:
        print(
            f"[{result.status.value.upper():<7}] {result.source} / {result.item}: {result.detail}"
        )
    if any(result.status == StepStatus.FAILED for result in results):
        sys.exit(1)

