"""Controller tests for /api/indicators/{code}/period-averages."""

from decimal import Decimal

from fastapi.testclient import TestClient
import pytest

from app.dependencies import get_period_average_service
from app.domain import (
    CountrySeries,
    IndicatorInfo,
    Period,
    PeriodAverageQuery,
    PeriodAverageReport,
)
from app.services.period_average_service import (
    InvalidQueryError,
    UnknownIndicatorError,
)

URL = "/api/indicators/WHOSIS_000001/period-averages?country=ROU&country=FRA"


class FakePeriodAverageService:
    def __init__(
        self,
        report: PeriodAverageReport | None = None,
        error: Exception | None = None,
    ) -> None:
        self.report = report
        self.error = error
        self.last_query: PeriodAverageQuery | None = None

    def get_report(self, query: PeriodAverageQuery) -> PeriodAverageReport:
        self.last_query = query
        if self.error is not None:
            raise self.error
        assert self.report is not None
        return self.report


def _use(client: TestClient, fake: FakePeriodAverageService) -> None:
    client.app.dependency_overrides[get_period_average_service] = lambda: fake


@pytest.fixture(autouse=True)
def _clear_override(client: TestClient):
    yield
    client.app.dependency_overrides.pop(get_period_average_service, None)


def test_averages_arrive_as_json_numbers_and_deduplicate_countries(client: TestClient):
    fake = FakePeriodAverageService(
        report=PeriodAverageReport(
            indicator=IndicatorInfo("WHOSIS_000001", "Life expectancy", "years"),
            periods=[
                Period(2000, 2004, "2000\u20132004"),
                Period(2005, 2009, "2005\u20132009"),
            ],
            series=[
                CountrySeries("ROU", "Romania", [Decimal("71.01"), None]),
            ],
        )
    )
    _use(client, fake)

    response = client.get(
        "/api/indicators/WHOSIS_000001/period-averages?country=rou&country=ROU&sex=MLE"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["series"][0]["averages"] == [71.01, None]
    assert isinstance(body["series"][0]["averages"][0], float)
    assert fake.last_query is not None
    assert fake.last_query.country_iso3s == ("ROU",)
    assert fake.last_query.sex.value == "MLE"


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (UnknownIndicatorError("unknown indicator 'WHOSIS_000001'"), 404),
        (InvalidQueryError("first_year 2010 is after last_year 2009"), 422),
    ],
)
def test_service_errors_become_http_errors(
    client: TestClient, error: Exception, status_code: int
):
    _use(client, FakePeriodAverageService(error=error))

    response = client.get(URL)
    assert response.status_code == status_code
    assert response.json() == {"detail": str(error)}


def test_full_stack_period_averages_on_seed_data(client: TestClient):
    response = client.get(
        "/api/indicators/WHOSIS_000001/period-averages?country=ROU&first_year=2020&last_year=2023&period_years=5"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["indicator"]["code"] == "WHOSIS_000001"
    assert body["periods"] == [{"start": 2020, "end": 2023, "label": "2020\u20132023"}]
    assert body["series"] == [
        {"country_iso3": "ROU", "country_name": "Romania", "averages": [75.6]}
    ]
