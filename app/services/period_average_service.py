"""Service layer for computing per-period indicator averages across countries."""

from decimal import Decimal, ROUND_HALF_UP

from app.domain import (
    CountrySeries,
    IndicatorInfo,
    Period,
    PeriodAverage,
    PeriodAverageQuery,
    PeriodAverageReport,
)
from app.models import Sex
from app.repositories.period_average_repository import PeriodAverageRepository

MAX_COUNTRIES = 20
DEFAULT_FIRST_YEAR = 2000
DEFAULT_LAST_YEAR = 2023
DEFAULT_PERIOD_YEARS = 5
AVERAGED_SEX = Sex.BOTH

_TWO_DECIMALS = Decimal("0.01")


class UnknownIndicatorError(Exception):
    """Raised when a requested indicator code does not exist."""


class InvalidQueryError(Exception):
    """Raised when period-average query parameters violate domain rules."""


def _validate(query: PeriodAverageQuery) -> None:
    if query.period_years < 1:
        raise InvalidQueryError("period_years must be at least 1")
    if query.first_year > query.last_year:
        raise InvalidQueryError(
            f"first_year {query.first_year} is after last_year {query.last_year}"
        )
    if len(query.country_iso3s) > MAX_COUNTRIES:
        raise InvalidQueryError(
            f"at most {MAX_COUNTRIES} countries may be requested"
        )


def _periods(query: PeriodAverageQuery) -> list[Period]:
    periods: list[Period] = []
    start = query.first_year
    while start <= query.last_year:
        end = min(start + query.period_years - 1, query.last_year)
        label = str(start) if start == end else f"{start}\u2013{end}"
        periods.append(Period(start=start, end=end, label=label))
        start += query.period_years
    return periods


def _round_half_up(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(_TWO_DECIMALS, rounding=ROUND_HALF_UP)


def _series(
    periods: list[Period], averages: list[PeriodAverage]
) -> list[CountrySeries]:
    grouped: dict[tuple[str, str], dict[int, Decimal | None]] = {}
    for row in averages:
        key = (row.country_iso3, row.country_name)
        by_period = grouped.setdefault(key, {})
        by_period[row.period_start] = _round_half_up(row.average)

    return [
        CountrySeries(
            country_iso3=iso3,
            country_name=name,
            averages=[by_period.get(period.start) for period in periods],
        )
        for (iso3, name), by_period in grouped.items()
    ]


class PeriodAverageService:
    """Validates period-average queries and builds aligned country series."""

    def __init__(self, repository: PeriodAverageRepository) -> None:
        self._repository = repository

    def get_indicator(self, code: str) -> IndicatorInfo:
        """Return indicator metadata or raise UnknownIndicatorError."""
        indicator = self._repository.find_indicator(code)
        if indicator is None:
            raise UnknownIndicatorError(f"unknown indicator {code!r}")
        return indicator

    def get_report(self, query: PeriodAverageQuery) -> PeriodAverageReport:
        """Validate the query, fetch period aggregates, and align series."""
        _validate(query)
        indicator = self.get_indicator(query.indicator_code)
        periods = _periods(query)
        averages = self._repository.average_by_period(query, sex=query.sex)
        return PeriodAverageReport(
            indicator=indicator,
            periods=periods,
            series=_series(periods, averages),
        )
