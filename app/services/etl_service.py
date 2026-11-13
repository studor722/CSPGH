"""Service layer orchestrating on-demand extract and transform+load actions."""

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Callable

import requests
from sqlalchemy.exc import SQLAlchemyError

from etl import import_owid, import_who, import_worldbank
from etl.extract_owid import download_owid_chart
from etl.extract_who import WhoApiError, download_who_indicator
from etl.extract_worldbank import (
    WorldBankApiError,
    download_worldbank_countries,
    download_worldbank_indicator,
)
from etl.realtime_pipeline import sync_country_realtime
from etl.step_result import StepResult, StepStatus

logger = logging.getLogger(__name__)

EXTRACT_ERRORS = (
    WhoApiError,
    WorldBankApiError,
    requests.RequestException,
    ValueError,
    OSError,
)
IMPORT_ERRORS = (SQLAlchemyError, ValueError, OSError)


@dataclass(frozen=True, slots=True)
class ExtractJob:
    """Single upstream download action returning `(raw_path, source_url)`."""

    source: str
    item: str
    run: Callable[[], tuple[Path, str]]


@dataclass(frozen=True, slots=True)
class ImportJob:
    """Single source transform-and-load action returning step results."""

    source: str
    run: Callable[[], list[StepResult]]


def _build_default_extract_jobs() -> tuple[ExtractJob, ...]:
    jobs: list[ExtractJob] = [
        ExtractJob(
            import_worldbank.SOURCE.name,
            "countries",
            download_worldbank_countries,
        )
    ]
    for spec in import_worldbank.INDICATORS:
        jobs.append(
            ExtractJob(
                import_worldbank.SOURCE.name,
                spec.code,
                lambda remote_id=spec.remote_id: download_worldbank_indicator(
                    remote_id
                ),
            )
        )
    for spec in import_who.INDICATORS:
        jobs.append(
            ExtractJob(
                import_who.SOURCE.name,
                spec.code,
                lambda remote_id=spec.remote_id: download_who_indicator(remote_id),
            )
        )
    for spec in import_owid.INDICATORS:
        jobs.append(
            ExtractJob(
                import_owid.SOURCE.name,
                spec.code,
                lambda remote_id=spec.remote_id: download_owid_chart(remote_id),
            )
        )
    return tuple(jobs)


DEFAULT_IMPORT_JOBS: tuple[ImportJob, ...] = (
    ImportJob(import_worldbank.SOURCE.name, import_worldbank.import_all),
    ImportJob(import_who.SOURCE.name, import_who.import_all),
    ImportJob(import_owid.SOURCE.name, import_owid.import_all),
)


class EtlService:
    """Runs extract and transform+load jobs and collects typed step results."""

    def __init__(
        self,
        extract_jobs: tuple[ExtractJob, ...] | None = None,
        import_jobs: tuple[ImportJob, ...] = DEFAULT_IMPORT_JOBS,
    ) -> None:
        self._extract_jobs = (
            extract_jobs
            if extract_jobs is not None
            else _build_default_extract_jobs()
        )
        self._import_jobs = import_jobs

    def extract_all(self) -> list[StepResult]:
        results: list[StepResult] = []
        for job in self._extract_jobs:
            try:
                path, _url = job.run()
            except EXTRACT_ERRORS as exc:
                logger.warning("extract %s %s failed: %s", job.source, job.item, exc)
                results.append(StepResult.from_error(job.source, job.item, exc))
            else:
                results.append(
                    StepResult(
                        source=job.source,
                        item=job.item,
                        status=StepStatus.OK,
                        detail=f"saved {path.name}",
                    )
                )
        return results

    def transform_and_load_all(self) -> list[StepResult]:
        results: list[StepResult] = []
        for job in self._import_jobs:
            try:
                results.extend(job.run())
            except IMPORT_ERRORS as exc:
                logger.warning("import %s failed: %s", job.source, exc)
                results.append(StepResult.from_error(job.source, "all", exc))
        return results

    def sync_country(self, iso3: str) -> dict[str, Any]:
        """Trigger a single-country real-time upstream sync."""
        return sync_country_realtime(iso3.strip().upper())

