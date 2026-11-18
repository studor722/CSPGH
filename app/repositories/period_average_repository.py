"""Data access repository for per-period indicator averages."""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain import IndicatorInfo, PeriodAverage, PeriodAverageQuery
from app.models import Country, Indicator, Observation, Sex


class PeriodAverageRepository:
    """Aggregates observation values into fixed-length year periods in PostgreSQL."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_indicator(self, code: str) -> IndicatorInfo | None:
        """Look up indicator metadata by its unique code, or return None."""
        row = self._session.execute(
            select(Indicator.code, Indicator.name, Indicator.unit).where(
                Indicator.code == code
            )
        ).first()
        if row is None:
            return None
        return IndicatorInfo(
            code=row.code,
            name=row.name,
            unit=row.unit or "",
        )

    def average_by_period(
        self,
        query: PeriodAverageQuery,
        *,
        sex: Sex | None = None,
    ) -> list[PeriodAverage]:
        """Compute per-country, per-period averages directly in PostgreSQL."""
        if not query.country_iso3s:
            return []

        effective_sex = sex if sex is not None else query.sex
        period_start = (
            query.first_year
            + (Observation.year - query.first_year)
            // query.period_years
            * query.period_years
        )
        bucketed = (
            select(
                Observation.country_iso3,
                period_start.label("period_start"),
                Observation.value,
            )
            .join(Indicator, Observation.indicator_id == Indicator.indicator_id)
            .where(
                Indicator.code == query.indicator_code,
                Observation.country_iso3.in_(query.country_iso3s),
                Observation.year.between(query.first_year, query.last_year),
                Observation.sex == effective_sex,
                Observation.value.is_not(None),
            )
            .subquery()
        )
        averages = (
            select(
                Country.iso3.label("country_iso3"),
                Country.name.label("country_name"),
                bucketed.c.period_start,
                func.avg(bucketed.c.value).label("average"),
                func.count().label("observation_count"),
            )
            .join(Country, Country.iso3 == bucketed.c.country_iso3)
            .group_by(Country.iso3, Country.name, bucketed.c.period_start)
            .order_by(Country.name, bucketed.c.period_start)
        )
        rows = self._session.execute(averages).all()
        return [
            PeriodAverage(
                country_iso3=row.country_iso3,
                country_name=row.country_name,
                period_start=int(row.period_start),
                average=(
                    Decimal(str(row.average))
                    if row.average is not None
                    else None
                ),
                observation_count=int(row.observation_count),
            )
            for row in rows
        ]
