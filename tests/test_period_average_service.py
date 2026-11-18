"""Unit tests for PeriodAverageService using an in-memory fake repository."""

from decimal import Decimal

import pytest

from app.domain import IndicatorInfo, PeriodAverage, PeriodAverageQuery
from app.models import Sex
from app.services.period_average_service import (
    InvalidQueryError,
    MAX_COUNTRIES,
    PeriodAverageService,
    UnknownIndicatorError,
)


class FakePeriodAverageRepository:
    def __init__(
        self,
        indicator: IndicatorInfo | None = None,
        rows: list[PeriodAverage] | None = None,
    ) -> None:
        self.indicator = indicator
        self.rows = rows or []
        self.last_query: PeriodAverageQuery | None = None
        self.last_sex: Sex | None = None

    def find_indicator(self, code: str) -> IndicatorInfo | None:
        if self.indicator and self.indicator.code == code:
            return self.indicator
        return None

    def average_by_period(
        self, query: PeriodAverageQuery, *, sex: Sex | None = None
    ) -> list[PeriodAverage]:
        self.last_query = query
        self.last_sex = sex
        return list(self.rows)


def test_periods_and_half_up_rounding_and_missing_gaps():
    repo = FakePeriodAverageRepository(
        indicator=IndicatorInfo("WHOSIS_000001", "Life expectancy", "years"),
        rows=[
            PeriodAverage("FRA", "France", 2000, Decimal("79.485"), 5),
            PeriodAverage("FRA", "France", 2010, Decimal("81.005"), 3),
            PeriodAverage("ROU", "Romania", 2000, Decimal("71.014"), 5),
        ],
    )
    service = PeriodAverageService(repo)
    query = PeriodAverageQuery(
        indicator_code="WHOSIS_000001",
        country_iso3s=("FRA", "ROU"),
        first_year=2000,
        last_year=2013,
        period_years=5,
    )

    report = service.get_report(query)

    assert [p.label for p in report.periods] == [
        "2000\u20132004",
        "2005\u20132009",
        "2010\u20132013",
    ]
    assert report.series[0].country_iso3 == "FRA"
    assert report.series[0].averages == [
        Decimal("79.49"),
        None,
        Decimal("81.01"),
    ]
    assert report.series[1].country_iso3 == "ROU"
    assert report.series[1].averages == [Decimal("71.01"), None, None]
    assert repo.last_sex == Sex.BOTH


def test_unknown_indicator_raises():
    service = PeriodAverageService(FakePeriodAverageRepository(indicator=None))
    query = PeriodAverageQuery("MISSING", ("ROU",), 2000, 2023, 5)

    with pytest.raises(UnknownIndicatorError):
        service.get_report(query)


@pytest.mark.parametrize(
    "query",
    [
        PeriodAverageQuery("WHOSIS_000001", ("ROU",), 2000, 2023, 0),
        PeriodAverageQuery("WHOSIS_000001", ("ROU",), 2020, 2010, 5),
        PeriodAverageQuery(
            "WHOSIS_000001",
            tuple(f"C{i:02d}" for i in range(MAX_COUNTRIES + 1)),
            2000,
            2023,
            5,
        ),
    ],
)
def test_invalid_query_raises(query: PeriodAverageQuery):
    service = PeriodAverageService(
        FakePeriodAverageRepository(
            indicator=IndicatorInfo("WHOSIS_000001", "Life expectancy", "years")
        )
    )
    with pytest.raises(InvalidQueryError):
        service.get_report(query)
