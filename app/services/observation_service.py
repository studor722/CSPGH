"""Service layer for warehouse observations, filter options, and baselines."""

from app.domain import (
    CountryBaseline,
    CountrySummary,
    FilterIssue,
    FilterOptions,
    GlobeCountryStat,
    IndicatorSummary,
    ObservationCriteria,
    ObservationListItem,
    YearBounds,
)
from app.models import Sex
from app.repositories.observation_repository import ObservationRepository
from dataclasses import dataclass

DEFAULT_PAGE_SIZE = 25


@dataclass(frozen=True, slots=True)
class ObservationPage:
    """Paginated slice of warehouse observations returned to a view."""

    items: list[ObservationListItem]
    number: int
    size: int
    total_items: int

    @property
    def total_pages(self) -> int:
        return max(1, (self.total_items + self.size - 1) // self.size)

    @property
    def has_previous(self) -> bool:
        return self.number > 1

    @property
    def has_next(self) -> bool:
        return self.number < self.total_pages


class ObservationService:
    """Orchestrates paginated observation queries and read-only catalog lookups."""

    def __init__(
        self,
        repository: ObservationRepository,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> None:
        if page_size < 1:
            raise ValueError(f"page_size must be >= 1 (got {page_size})")
        self._repo = repository
        self._page_size = page_size

    def list_observations(
        self, criteria: ObservationCriteria, *, page: int = 1
    ) -> ObservationPage:
        if page < 1:
            raise ValueError(f"page must be >= 1 (got {page})")
        offset = (page - 1) * self._page_size
        items = self._repo.find(criteria, limit=self._page_size, offset=offset)
        total_items = self._repo.count(criteria)
        return ObservationPage(
            items=items,
            number=page,
            size=self._page_size,
            total_items=total_items,
        )

    def list_api_observations(
        self, criteria: ObservationCriteria, *, limit: int = 100
    ) -> list[ObservationListItem]:
        if limit < 1:
            raise ValueError(f"limit must be >= 1 (got {limit})")
        return self._repo.find(criteria, limit=limit, offset=0)

    def filter_options(self) -> FilterOptions:
        return FilterOptions(
            countries=self._repo.list_countries(),
            indicators=self._repo.list_indicators(),
            regions=self._repo.list_regions(),
        )

    def available_year_bounds(
        self, criteria: ObservationCriteria
    ) -> YearBounds | None:
        return self._repo.available_year_bounds(criteria)

    def validate_criteria(
        self, criteria: ObservationCriteria, *, total_items: int
    ) -> list[FilterIssue]:
        """Detect contradictory or impossible filter combinations."""
        issues: list[FilterIssue] = []

        if criteria.country_iso3 is not None and criteria.region is not None:
            country = self._repo.get_country(criteria.country_iso3)
            if (
                country is not None
                and country.region
                and country.region != criteria.region
            ):
                issues.append(
                    FilterIssue(
                        message=(
                            f"Contradictory filter: {country.name} ({country.iso3}) "
                            f"belongs to '{country.region}', not '{criteria.region}'."
                        ),
                        fix_param="region",
                        fix_label=f"Clear Region filter",
                    )
                )

        if (
            criteria.year_from is not None
            and criteria.year_to is not None
            and criteria.year_from > criteria.year_to
        ):
            issues.append(
                FilterIssue(
                    message=(
                        f"Invalid year range: Year From ({criteria.year_from}) "
                        f"cannot be after Year To ({criteria.year_to})."
                    ),
                    fix_param="year_to",
                    fix_label="Clear Year To",
                )
            )

        if total_items == 0 and not issues and criteria.sex is not None:
            available_sexes = self._repo.available_sex_codes(criteria)
            if available_sexes and criteria.sex not in available_sexes:
                codes = ", ".join(s.value for s in available_sexes)
                issues.append(
                    FilterIssue(
                        message=(
                            f"No observations use sex '{criteria.sex.value}' for these "
                            f"filters; available sex codes are: {codes}."
                        ),
                        fix_param="sex",
                        fix_label="Show all sexes",
                    )
                )

        return issues

    def list_countries(self, region: str | None = None) -> list[CountrySummary]:
        return self._repo.list_country_records(region=region)

    def list_regions(self) -> list[Option]:
        return self._repo.list_regions()

    def list_indicators(self) -> list[IndicatorSummary]:
        return self._repo.list_indicator_records()

    def get_country_baseline(
        self, iso3: str, sex: str = "BTSX"
    ) -> CountryBaseline | None:
        return self._repo.get_country_baseline(iso3, sex=sex)

    def list_globe_stats(self) -> list[GlobeCountryStat]:
        return self._repo.list_globe_life_expectancy_stats()
