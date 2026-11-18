"""FastAPI dependency factories wiring services to request-scoped resources."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.observation_repository import ObservationRepository
from app.repositories.period_average_repository import PeriodAverageRepository
from app.services.etl_service import EtlService
from app.services.observation_service import ObservationService
from app.services.period_average_service import PeriodAverageService


def get_observation_service(
    session: Session = Depends(get_db),
) -> ObservationService:
    """Build a request-scoped ObservationService backed by SQLAlchemy."""
    return ObservationService(ObservationRepository(session))


def get_period_average_service(
    session: Session = Depends(get_db),
) -> PeriodAverageService:
    """Build a request-scoped PeriodAverageService backed by SQLAlchemy."""
    return PeriodAverageService(PeriodAverageRepository(session))


def get_etl_service() -> EtlService:
    """Build the ETL service handling extract and load web actions."""
    return EtlService()

