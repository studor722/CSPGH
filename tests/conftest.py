"""Shared fixtures providing an isolated PostgreSQL schema and overridden FastAPI client."""

from collections.abc import Iterator
from decimal import Decimal
import uuid

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.database import get_db, get_engine
from app.dependencies import get_etl_service
from app.main import create_app
from app.models import Base, Country, Indicator, Observation, Sex, Source


def _seed_sample_data(session: Session) -> None:
    who = Source(name="WHO", url="https://www.who.int/data/gho")
    wb = Source(name="World Bank", url="https://data.worldbank.org/")
    session.add_all([who, wb])
    session.flush()

    countries = [
        Country(
            iso3="ROU",
            iso2="RO",
            name="Romania",
            region="Europe & Central Asia",
            income_group="High income",
        ),
        Country(
            iso3="FRA",
            iso2="FR",
            name="France",
            region="Europe & Central Asia",
            income_group="High income",
        ),
        Country(
            iso3="KEN",
            iso2="KE",
            name="Kenya",
            region="Sub-Saharan Africa",
            income_group="Lower middle income",
        ),
        Country(
            iso3="JPN",
            iso2="JP",
            name="Japan",
            region="East Asia & Pacific",
            income_group="High income",
        ),
    ]
    session.add_all(countries)
    session.flush()

    le = Indicator(
        code="WHOSIS_000001",
        name="Life expectancy at birth",
        unit="years",
        source_id=who.source_id,
    )
    tob = Indicator(
        code="M_Est_tob_curr_std",
        name="Age-standardized tobacco use prevalence",
        unit="%",
        source_id=who.source_id,
    )
    gdp = Indicator(
        code="NY.GDP.PCAP.CD",
        name="GDP per capita",
        unit="current US$",
        source_id=wb.source_id,
    )
    session.add_all([le, tob, gdp])
    session.flush()

    rows = [
        Observation(
            country_iso3="ROU",
            indicator_id=le.indicator_id,
            year=2022,
            sex=Sex.BOTH,
            value=Decimal("75.60"),
            is_outlier=False,
        ),
        Observation(
            country_iso3="ROU",
            indicator_id=le.indicator_id,
            year=2022,
            sex=Sex.MALE,
            value=Decimal("72.10"),
            is_outlier=False,
        ),
        Observation(
            country_iso3="ROU",
            indicator_id=le.indicator_id,
            year=2022,
            sex=Sex.FEMALE,
            value=Decimal("79.20"),
            is_outlier=False,
        ),
        Observation(
            country_iso3="ROU",
            indicator_id=tob.indicator_id,
            year=2021,
            sex=Sex.MALE,
            value=Decimal("37.40"),
            is_outlier=False,
        ),
        Observation(
            country_iso3="FRA",
            indicator_id=le.indicator_id,
            year=2022,
            sex=Sex.FEMALE,
            value=Decimal("85.30"),
            is_outlier=False,
        ),
        Observation(
            country_iso3="FRA",
            indicator_id=gdp.indicator_id,
            year=2021,
            sex=Sex.BOTH,
            value=Decimal("43658.90"),
            is_outlier=False,
        ),
        Observation(
            country_iso3="KEN",
            indicator_id=le.indicator_id,
            year=2020,
            sex=Sex.BOTH,
            value=Decimal("61.40"),
            is_outlier=False,
        ),
        Observation(
            country_iso3="KEN",
            indicator_id=tob.indicator_id,
            year=2020,
            sex=Sex.MALE,
            value=Decimal("18.20"),
            is_outlier=False,
        ),
        Observation(
            country_iso3="JPN",
            indicator_id=le.indicator_id,
            year=2022,
            sex=Sex.BOTH,
            value=Decimal("84.50"),
            is_outlier=False,
        ),
        Observation(
            country_iso3="JPN",
            indicator_id=gdp.indicator_id,
            year=2020,
            sex=Sex.BOTH,
            value=Decimal("999999.00"),
            is_outlier=True,
        ),
    ]
    session.add_all(rows)
    session.commit()


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Create a temporary PostgreSQL schema seeded with synthetic test rows."""
    schema = f"test_{uuid.uuid4().hex[:12]}"
    base_engine = get_engine()

    with base_engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))

    scoped_engine = base_engine.execution_options(schema_translate_map={None: schema})
    Base.metadata.create_all(scoped_engine)
    TestingSession = sessionmaker(bind=scoped_engine, autoflush=False)
    session = TestingSession()

    try:
        _seed_sample_data(session)
        yield session
    finally:
        session.close()
        scoped_engine.dispose()
        with base_engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


class _FailFastEtlService:
    """Guardrail stub ensuring web controller tests inject an explicit ETL fake."""

    def extract_all(self):
        raise AssertionError("extract_all called without explicit test override")

    def transform_and_load_all(self):
        raise AssertionError("transform_and_load_all called without explicit test override")


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    """Return a FastAPI TestClient wired to the isolated temporary DB schema."""
    application = create_app()

    def _override_db() -> Iterator[Session]:
        yield db_session

    application.dependency_overrides[get_db] = _override_db
    application.dependency_overrides[get_etl_service] = _FailFastEtlService
    try:
        with TestClient(application) as test_client:
            yield test_client
    finally:
        application.dependency_overrides.clear()

