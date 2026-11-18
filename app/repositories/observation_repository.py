"""Data access repository for warehouse observations, countries, and indicators."""

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.domain import (
    CountryBaseline,
    CountrySummary,
    GlobeCountryStat,
    IndicatorSummary,
    ObservationCriteria,
    ObservationListItem,
    Option,
    YearBounds,
)
from app.models import Country, Indicator, Observation, Sex

_LIFE_EXPECTANCY_CODES = (
    "WHOSIS_000001",
    "SP.DYN.LE00.IN",
    "OWID_LIFE_EXPECTANCY",
)

# Deterministic tie-breaker guarantees OFFSET/LIMIT pagination never drops or duplicates rows.
_STABLE_ORDER = (
    Observation.year.desc(),
    Country.name,
    Indicator.name,
    Observation.sex,
    Observation.observation_id,
)


class ObservationRepository:
    """Read-only queries over observations, countries, and indicators."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find(
        self,
        criteria: ObservationCriteria,
        *,
        limit: int,
        offset: int = 0,
    ) -> list[ObservationListItem]:
        stmt = (
            self._matching_observations(criteria)
            .order_by(*_STABLE_ORDER)
            .limit(limit)
            .offset(offset)
        )
        rows = self._session.execute(stmt).all()
        return [
            ObservationListItem(
                observation_id=row.observation_id,
                country_name=row.country_name,
                country_iso3=row.country_iso3,
                region=row.region or "",
                indicator_code=row.indicator_code,
                indicator_name=row.indicator_name,
                unit=row.unit or "",
                year=row.year,
                sex=row.sex,
                value=row.value,
                is_outlier=bool(row.is_outlier),
            )
            for row in rows
        ]

    def count(self, criteria: ObservationCriteria) -> int:
        conditions = _conditions(criteria)
        stmt = (
            select(func.count(Observation.observation_id))
            .select_from(Observation)
            .join(Country, Observation.country_iso3 == Country.iso3)
            .join(Indicator, Observation.indicator_id == Indicator.indicator_id)
            .where(*conditions)
        )
        return int(self._session.scalar(stmt) or 0)

    def available_year_bounds(
        self, criteria: ObservationCriteria
    ) -> YearBounds | None:
        scope = ObservationCriteria(
            country_iso3=criteria.country_iso3,
            indicator_code=criteria.indicator_code,
            region=criteria.region,
            sex=criteria.sex,
            is_outlier=criteria.is_outlier,
        )
        conditions = _conditions(scope)
        stmt = (
            select(
                func.min(Observation.year).label("min_year"),
                func.max(Observation.year).label("max_year"),
                func.count(Observation.observation_id).label("total_count"),
            )
            .select_from(Observation)
            .join(Country, Observation.country_iso3 == Country.iso3)
            .join(Indicator, Observation.indicator_id == Indicator.indicator_id)
            .where(*conditions)
        )
        row = self._session.execute(stmt).first()
        if row is None or not row.total_count:
            return None
        return YearBounds(
            min_year=int(row.min_year),
            max_year=int(row.max_year),
            total_count=int(row.total_count),
        )

    def list_countries(self) -> list[Option]:
        stmt = select(Country.iso3, Country.name, Country.region).order_by(
            Country.name, Country.iso3
        )
        rows = self._session.execute(stmt).all()
        return [
            Option(
                value=row.iso3,
                label=f"{row.name} ({row.iso3})",
                group=row.region or "Other",
            )
            for row in rows
        ]

    def get_country(self, iso3: str) -> CountrySummary | None:
        clean_iso3 = iso3.strip().upper()
        row = self._session.scalar(select(Country).where(Country.iso3 == clean_iso3))
        if row is None:
            return None
        return CountrySummary(
            iso3=row.iso3,
            iso2=row.iso2,
            name=row.name,
            region=row.region,
            income_group=row.income_group,
        )

    def available_sex_codes(self, criteria: ObservationCriteria) -> list[Sex]:
        scope = ObservationCriteria(
            country_iso3=criteria.country_iso3,
            indicator_code=criteria.indicator_code,
            region=criteria.region,
            year_from=criteria.year_from,
            year_to=criteria.year_to,
            is_outlier=criteria.is_outlier,
        )
        conditions = _conditions(scope)
        stmt = (
            select(Observation.sex)
            .select_from(Observation)
            .join(Country, Observation.country_iso3 == Country.iso3)
            .join(Indicator, Observation.indicator_id == Indicator.indicator_id)
            .where(*conditions)
            .distinct()
            .order_by(Observation.sex)
        )
        return list(self._session.scalars(stmt).all())

    def list_indicators(self) -> list[Option]:
        stmt = select(Indicator.code, Indicator.name).order_by(
            Indicator.name, Indicator.code
        )
        rows = self._session.execute(stmt).all()
        return [
            Option(value=row.code, label=f"{row.name} ({row.code})")
            for row in rows
        ]

    def list_regions(self) -> list[Option]:
        stmt = (
            select(Country.region)
            .where(Country.region.is_not(None), Country.region != "")
            .distinct()
            .order_by(Country.region)
        )
        regions = self._session.scalars(stmt).all()
        return [Option(value=region, label=region) for region in regions]

    def list_country_records(
        self, region: str | None = None
    ) -> list[CountrySummary]:
        stmt = select(Country)
        if region is not None:
            stmt = stmt.where(Country.region == region)
        stmt = stmt.order_by(Country.name, Country.iso3)
        rows = self._session.scalars(stmt).all()
        return [
            CountrySummary(
                iso3=row.iso3,
                iso2=row.iso2,
                name=row.name,
                region=row.region,
                income_group=row.income_group,
            )
            for row in rows
        ]

    def list_indicator_records(self) -> list[IndicatorSummary]:
        stmt = select(Indicator).order_by(Indicator.name, Indicator.code)
        rows = self._session.scalars(stmt).all()
        return [
            IndicatorSummary(
                indicator_id=row.indicator_id,
                code=row.code,
                name=row.name,
                unit=row.unit,
                source_id=row.source_id,
            )
            for row in rows
        ]

    def get_country_baseline(
        self, iso3: str, sex: str = "BTSX"
    ) -> CountryBaseline | None:
        clean_iso3 = iso3.strip().upper()
        country = self._session.scalar(
            select(Country).where(Country.iso3 == clean_iso3)
        )
        if country is None:
            return None

        stmt = (
            select(Observation.value, Observation.year)
            .join(Indicator, Observation.indicator_id == Indicator.indicator_id)
            .where(
                Observation.country_iso3 == clean_iso3,
                Indicator.code.in_(_LIFE_EXPECTANCY_CODES),
                Observation.sex.in_([sex, "BTSX", "ALL"]),
            )
            .order_by(Observation.year.desc())
            .limit(1)
        )
        row = self._session.execute(stmt).first()
        baseline_val = float(row.value) if row is not None and row.value is not None else 74.0
        reference_year = int(row.year) if row is not None else 2019
        return CountryBaseline(
            iso3=country.iso3,
            name=country.name,
            region=country.region,
            income_group=country.income_group,
            life_expectancy=baseline_val,
            reference_year=reference_year,
        )

    def list_globe_life_expectancy_stats(self) -> list[GlobeCountryStat]:
        sub = (
            select(
                Observation.country_iso3,
                func.max(Observation.year).label("max_year"),
            )
            .join(Indicator, Observation.indicator_id == Indicator.indicator_id)
            .where(Indicator.code.in_(_LIFE_EXPECTANCY_CODES))
            .group_by(Observation.country_iso3)
            .subquery()
        )
        stmt = (
            select(
                Country.iso3,
                Country.name,
                Country.region,
                Observation.value,
                Observation.year,
            )
            .join(sub, Country.iso3 == sub.c.country_iso3)
            .join(
                Observation,
                (Observation.country_iso3 == sub.c.country_iso3)
                & (Observation.year == sub.c.max_year),
            )
            .join(Indicator, Observation.indicator_id == Indicator.indicator_id)
            .where(
                Indicator.code.in_(_LIFE_EXPECTANCY_CODES),
                Observation.sex.in_(["BTSX", "ALL"]),
            )
        )
        rows = self._session.execute(stmt).all()
        return [
            GlobeCountryStat(
                iso3=row.iso3,
                name=row.name,
                region=row.region,
                life_expectancy=float(row.value) if row.value else None,
                year=int(row.year),
            )
            for row in rows
        ]

    def _matching_observations(self, criteria: ObservationCriteria):
        return (
            select(
                Observation.observation_id,
                Country.name.label("country_name"),
                Observation.country_iso3,
                Country.region,
                Indicator.code.label("indicator_code"),
                Indicator.name.label("indicator_name"),
                Indicator.unit,
                Observation.year,
                Observation.sex,
                Observation.value,
                Observation.is_outlier,
            )
            .select_from(Observation)
            .join(Country, Observation.country_iso3 == Country.iso3)
            .join(Indicator, Observation.indicator_id == Indicator.indicator_id)
            .where(*_conditions(criteria))
        )


def _conditions(criteria: ObservationCriteria) -> list[ColumnElement[bool]]:
    clauses: list[ColumnElement[bool]] = []
    if criteria.country_iso3 is not None:
        clauses.append(Observation.country_iso3 == criteria.country_iso3)
    if criteria.indicator_code is not None:
        clauses.append(Indicator.code == criteria.indicator_code)
    if criteria.region is not None:
        clauses.append(Country.region == criteria.region)
    if criteria.year_from is not None:
        clauses.append(Observation.year >= criteria.year_from)
    if criteria.year_to is not None:
        clauses.append(Observation.year <= criteria.year_to)
    if criteria.sex is not None:
        clauses.append(Observation.sex == criteria.sex)
    if criteria.is_outlier is not None:
        clauses.append(Observation.is_outlier == criteria.is_outlier)
    return clauses

