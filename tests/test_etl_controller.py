"""HTTP tests for SSR /actions/extract and /actions/load ETL controllers."""

from app.dependencies import get_etl_service
from etl.step_result import StepResult, StepStatus


class _StubEtlService:
    def extract_all(self) -> list[StepResult]:
        return [
            StepResult("World Bank", "countries", StepStatus.OK, "saved countries.json"),
            StepResult("WHO", "WHOSIS_000001", StepStatus.FAILED, "timeout"),
        ]

    def transform_and_load_all(self) -> list[StepResult]:
        return [
            StepResult("World Bank", "countries", StepStatus.OK, "190 countries loaded"),
            StepResult("WHO", "WHOSIS_000001", StepStatus.SKIPPED, "missing file"),
        ]


def test_extract_action_renders_step_results_table(client):
    client.app.dependency_overrides[get_etl_service] = _StubEtlService

    response = client.post("/actions/extract")
    assert response.status_code == 200
    assert "Extract fresh data from sources" in response.text
    assert "1 ok" in response.text
    assert "1 failed" in response.text
    assert "saved countries.json" in response.text
    assert "timeout" in response.text
    assert 'href="/observations"' in response.text


def test_load_action_renders_step_results_table(client):
    client.app.dependency_overrides[get_etl_service] = _StubEtlService

    response = client.post("/actions/load")
    assert response.status_code == 200
    assert "Transform &amp; load data from local JSON/CSV files" in response.text
    assert "1 ok" in response.text
    assert "1 skipped" in response.text
    assert "190 countries loaded" in response.text
    assert "missing file" in response.text

