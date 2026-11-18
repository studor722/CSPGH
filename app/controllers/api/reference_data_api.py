"""REST API controller for regions, countries, and indicators lookup endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.controllers.api.schemas import (
    CountryResponse,
    IndicatorDetailResponse,
    IndicatorResponse,
)
from app.dependencies import get_observation_service, get_period_average_service
from app.services.observation_service import ObservationService
from app.services.period_average_service import (
    PeriodAverageService,
    UnknownIndicatorError,
)

router = APIRouter(prefix="/api", tags=["reference data"])

ObsService = Annotated[ObservationService, Depends(get_observation_service)]
AvgService = Annotated[PeriodAverageService, Depends(get_period_average_service)]


@router.get("/regions")
def list_regions(service: ObsService) -> list[str]:
    """Return sorted region names."""
    return [r.value for r in service.list_regions()]


@router.get("/countries")
def list_countries(
    service: ObsService,
    region: str | None = None,
) -> list[CountryResponse]:
    """Return countries (iso3, name), optionally filtered by region."""
    return [
        CountryResponse.from_domain(c)
        for c in service.list_countries(region)
    ]


@router.get("/indicators")
def list_indicators(service: ObsService) -> list[IndicatorResponse]:
    """Return all available indicators (code, name)."""
    return [
        IndicatorResponse.from_domain(i)
        for i in service.list_indicators()
    ]


@router.get("/indicators/{indicator_code}")
def get_indicator(
    indicator_code: str,
    service: AvgService,
) -> IndicatorDetailResponse:
    """Return metadata (code, name, unit) for a single indicator."""
    try:
        indicator = service.get_indicator(indicator_code)
    except UnknownIndicatorError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    return IndicatorDetailResponse.from_domain(indicator)
