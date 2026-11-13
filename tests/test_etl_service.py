"""Unit tests for EtlService fault isolation and StepResult collection."""

from pathlib import Path

from sqlalchemy.exc import OperationalError

from app.services.etl_service import EtlService, ExtractJob, ImportJob
from etl.extract_who import WhoApiError
from etl.step_result import StepResult, StepStatus


def test_extract_all_isolates_failures_and_continues():
    def _ok_job():
        return Path("/tmp/countries.json"), "https://example.org/countries.json"

    def _failing_job():
        raise WhoApiError("WHO timeout")

    service = EtlService(
        extract_jobs=(
            ExtractJob("World Bank", "countries", _ok_job),
            ExtractJob("WHO", "WHOSIS_000001", _failing_job),
            ExtractJob("Our World in Data", "OWID_LIFE_EXPECTANCY", _ok_job),
        ),
        import_jobs=(),
    )

    results = service.extract_all()
    assert len(results) == 3
    assert results[0].status == StepStatus.OK
    assert results[0].detail == "saved countries.json"
    assert results[1].status == StepStatus.FAILED
    assert "WHO timeout" in results[1].detail
    assert results[2].status == StepStatus.OK


def test_transform_and_load_all_collects_results_and_catches_db_errors():
    def _wb_import():
        return [
            StepResult("World Bank", "countries", StepStatus.OK, "190 countries loaded"),
            StepResult("World Bank", "NY.GDP.PCAP.CD", StepStatus.SKIPPED, "missing file"),
        ]

    def _broken_import():
        raise OperationalError("SELECT 1", {}, Exception("connection lost"))

    service = EtlService(
        extract_jobs=(),
        import_jobs=(
            ImportJob("World Bank", _wb_import),
            ImportJob("WHO", _broken_import),
        ),
    )

    results = service.transform_and_load_all()
    assert len(results) == 3
    assert results[0].ok is True
    assert results[1].skipped is True
    assert results[2].status == StepStatus.FAILED
    assert results[2].source == "WHO"

