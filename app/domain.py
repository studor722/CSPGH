"""Domain value objects shared across repository, service, and presentation layers."""

from dataclasses import dataclass
from decimal import Decimal

from app.models import Sex


@dataclass(frozen=True, slots=True)
class Option:
    """Selectable option rendered in HTML filter controls."""

    value: str
    label: str
    group: str | None = None


@dataclass(frozen=True, slots=True)
class FilterIssue:
    """Semantic conflict or mismatch detected in filter criteria."""

    message: str
    fix_param: str
    fix_label: str


@dataclass(frozen=True, slots=True)
class FilterOptions:
    """Dropdown options available for filtering warehouse observations."""

    countries: list[Option]
    indicators: list[Option]
    regions: list[Option]


@dataclass(frozen=True, slots=True)
class ObservationCriteria:
    """Filter criteria accepted when querying observations."""

    country_iso3: str | None = None
    indicator_code: str | None = None
    region: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    sex: Sex | None = None
    is_outlier: bool | None = None

    @property
    def has_any_filter(self) -> bool:
        return any(
            value is not None
            for value in (
                self.country_iso3,
                self.indicator_code,
                self.region,
                self.year_from,
                self.year_to,
                self.sex,
                self.is_outlier,
            )
        )


@dataclass(frozen=True, slots=True)
class ObservationListItem:
    """Read-only observation row joined with country and indicator metadata."""

    observation_id: int
    country_name: str
    country_iso3: str
    region: str
    indicator_code: str
    indicator_name: str
    unit: str
    year: int
    sex: Sex
    value: Decimal | None
    is_outlier: bool


@dataclass(frozen=True, slots=True)
class YearBounds:
    """Year coverage summary for matching non-year filters."""

    min_year: int
    max_year: int
    total_count: int


@dataclass(frozen=True, slots=True)
class CountrySummary:
    """Read-only country metadata for selectors and JSON API responses."""

    iso3: str
    iso2: str | None
    name: str
    region: str | None
    income_group: str | None


@dataclass(frozen=True, slots=True)
class IndicatorSummary:
    """Read-only indicator metadata for JSON API responses."""

    indicator_id: int
    code: str
    name: str
    unit: str | None
    source_id: int


@dataclass(frozen=True, slots=True)
class CountryBaseline:
    """Country metadata paired with its latest baseline life expectancy."""

    iso3: str
    name: str
    region: str | None
    income_group: str | None
    life_expectancy: float
    reference_year: int


@dataclass(frozen=True, slots=True)
class GlobeCountryStat:
    """Latest baseline life expectancy snapshot used by the 3D globe."""

    iso3: str
    name: str
    region: str | None
    life_expectancy: float | None
    year: int


@dataclass(frozen=True, slots=True)
class IndicatorInfo:
    """Public indicator metadata used by period-average and indicator endpoints."""

    code: str
    name: str
    unit: str


@dataclass(frozen=True, slots=True)
class PeriodAverageQuery:
    """Validated query parameters for computing per-period country averages."""

    indicator_code: str
    country_iso3s: tuple[str, ...]
    first_year: int
    last_year: int
    period_years: int
    sex: Sex = Sex.BOTH


@dataclass(frozen=True, slots=True)
class Period:
    """A contiguous range of years [start, end] with a display label."""

    start: int
    end: int
    label: str


@dataclass(frozen=True, slots=True)
class PeriodAverage:
    """One aggregated country-period average row returned by the repository."""

    country_iso3: str
    country_name: str
    period_start: int
    average: Decimal | None
    observation_count: int = 0


@dataclass(frozen=True, slots=True)
class CountrySeries:
    """Ordered per-period averages for one country aligned to report periods."""

    country_iso3: str
    country_name: str
    averages: list[Decimal | None]


@dataclass(frozen=True, slots=True)
class PeriodAverageReport:
    """Complete per-period averages report for an indicator across countries."""

    indicator: IndicatorInfo
    periods: list[Period]
    series: list[CountrySeries]


