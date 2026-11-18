"""Integration tests for PeriodAverageRepository against temporary PostgreSQL schema."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import PeriodAverageQuery
from app.models import Indicator, Observation, Sex
from app.repositories.period_average_repository import PeriodAverageRepository


def test_find_indicator_returns_info_or_none(db_session: Session):
    repo = PeriodAverageRepository(db_session)

    info = repo.find_indicator("WHOSIS_000001")
    assert info is not None
    assert info.code == "WHOSIS_000001"
    assert info.unit == "years"

    assert repo.find_indicator("NON_EXISTENT") is None


def test_average_by_period_buckets_in_postgres(db_session: Session):
    le_id = db_session.scalar(
        select(Indicator.indicator_id).where(Indicator.code == "WHOSIS_000001")
    )
    assert le_id is not None

    db_session.add_all(
        [
            Observation(
                country_iso3="ROU",
                indicator_id=le_id,
                year=2020,
                sex=Sex.BOTH,
                value=Decimal("74.00"),
                is_outlier=False,
            ),
            Observation(
                country_iso3="ROU",
                indicator_id=le_id,
                year=2021,
                sex=Sex.BOTH,
                value=Decimal("76.00"),
                is_outlier=False,
            ),
        ]
    )
    db_session.flush()

    repo = PeriodAverageRepository(db_session)
    query = PeriodAverageQuery(
        indicator_code="WHOSIS_000001",
        country_iso3s=("ROU", "FRA"),
        first_year=2020,
        last_year=2023,
        period_years=2,
        sex=Sex.BOTH,
    )
    rows = repo.average_by_period(query)

    # Seeded ROU has 2022=75.60; added 2020=74.00 & 2021=76.00 -> [2020-2021]=75.00, [2022-2023]=75.60
    rou_rows = [r for r in rows if r.country_iso3 == "ROU"]
    assert [(r.period_start, round(r.average, 2), r.observation_count) for r in rou_rows] == [
        (2020, Decimal("75.00"), 2),
        (2022, Decimal("75.60"), 1),
    ]

    # Sex.MALE should only pick up ROU 2022 male=72.10, not Sex.BOTH
    male_rows = repo.average_by_period(query, sex=Sex.MALE)
    assert [(r.country_iso3, r.period_start, round(r.average, 2)) for r in male_rows] == [
        ("ROU", 2022, Decimal("72.10"))
    ]
