"""Unit tests for ObservationService pagination and validation logic."""

from decimal import Decimal
import pytest

from app.domain import (
    CountrySummary,
    ObservationCriteria,
    ObservationListItem,
    Option,
)
from app.models import Sex
from app.services.observation_service import ObservationPage, ObservationService


class _FakeObservationRepository:
    def __init__(self, items: list[ObservationListItem]) -> None:
        self._items = items
        self.calls: list[tuple[ObservationCriteria, int, int]] = []

    def find(
        self, criteria: ObservationCriteria, *, limit: int, offset: int = 0
    ) -> list[ObservationListItem]:
        self.calls.append((criteria, limit, offset))
        return self._items[offset : offset + limit]

    def count(self, criteria: ObservationCriteria) -> int:
        return len(self._items)

    def list_countries(self) -> list[Option]:
        return [Option("ROU", "Romania (ROU)")]

    def list_indicators(self) -> list[Option]:
        return [Option("WHOSIS_000001", "Life expectancy at birth (WHOSIS_000001)")]

    def list_regions(self) -> list[Option]:
        return [Option("Europe & Central Asia", "Europe & Central Asia")]

    def get_country(self, iso3: str) -> CountrySummary | None:
        if iso3 == "ROU":
            return CountrySummary(
                iso3="ROU",
                iso2="RO",
                name="Romania",
                region="Europe & Central Asia",
                income_group="High income",
            )
        return None

    def available_sex_codes(self, criteria: ObservationCriteria) -> list[Sex]:
        return [Sex.BOTH]


def _make_items(count: int) -> list[ObservationListItem]:
    return [
        ObservationListItem(
            observation_id=i + 1,
            country_name="Romania",
            country_iso3="ROU",
            region="Europe & Central Asia",
            indicator_code="WHOSIS_000001",
            indicator_name="Life expectancy at birth",
            unit="years",
            year=2022 - (i % 5),
            sex=Sex.BOTH,
            value=Decimal("75.00"),
            is_outlier=False,
        )
        for i in range(count)
    ]


def test_pagination_math_and_offsets():
    repo = _FakeObservationRepository(_make_items(7))
    service = ObservationService(repo, page_size=3)
    criteria = ObservationCriteria(region="Europe & Central Asia")

    page1 = service.list_observations(criteria, page=1)
    assert len(page1.items) == 3
    assert page1.total_items == 7
    assert page1.total_pages == 3
    assert page1.has_previous is False
    assert page1.has_next is True

    page3 = service.list_observations(criteria, page=3)
    assert len(page3.items) == 1
    assert page3.has_previous is True
    assert page3.has_next is False
    assert repo.calls == [(criteria, 3, 0), (criteria, 3, 6)]


def test_empty_page_reports_at_least_one_page():
    page = ObservationPage(items=[], number=1, size=25, total_items=0)
    assert page.total_pages == 1
    assert page.has_previous is False
    assert page.has_next is False


def test_invalid_page_or_page_size_rejected():
    repo = _FakeObservationRepository([])
    with pytest.raises(ValueError):
        ObservationService(repo, page_size=0)

    service = ObservationService(repo, page_size=10)
    with pytest.raises(ValueError):
        service.list_observations(ObservationCriteria(), page=0)


def test_filter_options_combines_repository_lists():
    repo = _FakeObservationRepository([])
    service = ObservationService(repo)
    options = service.filter_options()
    assert len(options.countries) == 1
    assert len(options.indicators) == 1
    assert len(options.regions) == 1


def test_validate_criteria_detects_country_region_and_year_conflicts():
    repo = _FakeObservationRepository([])
    service = ObservationService(repo)

    issues = service.validate_criteria(
        ObservationCriteria(
            country_iso3="ROU",
            region="North America",
            year_from=2024,
            year_to=2015,
        ),
        total_items=0,
    )
    assert len(issues) == 2
    assert "Europe & Central Asia" in issues[0].message
    assert issues[0].fix_param == "region"
    assert "cannot be after Year To" in issues[1].message
    assert issues[1].fix_param == "year_to"

    sex_issues = service.validate_criteria(
        ObservationCriteria(country_iso3="ROU", sex=Sex.MALE),
        total_items=0,
    )
    assert len(sex_issues) == 1
    assert "BTSX" in sex_issues[0].message
    assert sex_issues[0].fix_param == "sex"

