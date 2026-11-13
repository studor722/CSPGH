"""Integration tests for ObservationRepository against an isolated Postgres schema."""

from app.domain import ObservationCriteria
from app.models import Sex
from app.repositories.observation_repository import ObservationRepository


def test_find_all_and_deterministic_pagination(db_session):
    repo = ObservationRepository(db_session)
    total = repo.count(ObservationCriteria())
    assert total == 10

    page1 = repo.find(ObservationCriteria(), limit=4, offset=0)
    page2 = repo.find(ObservationCriteria(), limit=4, offset=4)
    page3 = repo.find(ObservationCriteria(), limit=4, offset=8)

    ids = [item.observation_id for item in (*page1, *page2, *page3)]
    assert len(ids) == total
    assert len(set(ids)) == total


def test_filter_by_country_indicator_region_years_and_outlier(db_session):
    repo = ObservationRepository(db_session)

    europe_rows = repo.find(
        ObservationCriteria(region="Europe & Central Asia"), limit=50
    )
    assert len(europe_rows) == 6
    assert {r.country_iso3 for r in europe_rows} == {"ROU", "FRA"}

    ranged = repo.find(
        ObservationCriteria(country_iso3="ROU", year_from=2022, year_to=2022), limit=50
    )
    assert len(ranged) == 3
    assert all(r.year == 2022 for r in ranged)

    tobacco = repo.find(
        ObservationCriteria(indicator_code="M_Est_tob_curr_std"), limit=50
    )
    assert len(tobacco) == 2
    assert {r.country_iso3 for r in tobacco} == {"ROU", "KEN"}

    outliers = repo.find(ObservationCriteria(is_outlier=True), limit=50)
    assert len(outliers) == 1
    assert outliers[0].country_iso3 == "JPN"


def test_filter_by_sex(db_session):
    repo = ObservationRepository(db_session)

    male_rows = repo.find(ObservationCriteria(sex=Sex.MALE), limit=50)
    assert len(male_rows) == 3
    assert all(r.sex == Sex.MALE for r in male_rows)

    female_rou = repo.find(
        ObservationCriteria(country_iso3="ROU", sex=Sex.FEMALE), limit=50
    )
    assert len(female_rou) == 1
    assert female_rou[0].sex == Sex.FEMALE
    assert float(female_rou[0].value) == 79.2


def test_list_filter_options_and_year_bounds(db_session):
    repo = ObservationRepository(db_session)

    countries = repo.list_countries()
    indicators = repo.list_indicators()
    regions = repo.list_regions()

    assert [c.value for c in countries] == ["FRA", "JPN", "KEN", "ROU"]
    assert {i.value for i in indicators} == {
        "WHOSIS_000001",
        "M_Est_tob_curr_std",
        "NY.GDP.PCAP.CD",
    }
    assert [r.value for r in regions] == [
        "East Asia & Pacific",
        "Europe & Central Asia",
        "Sub-Saharan Africa",
    ]

    bounds = repo.available_year_bounds(
        ObservationCriteria(country_iso3="KEN", year_from=2024)
    )
    assert bounds is not None
    assert bounds.min_year == 2020
    assert bounds.max_year == 2020
    assert bounds.total_count == 2

