"""REST API controller for per-period indicator averages."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.controllers.api.schemas import PeriodAveragesResponse
from app.dependencies import get_period_average_service
from app.domain import PeriodAverageQuery
from app.models import Sex
from app.services.period_average_service import (
    AVERAGED_SEX,
    DEFAULT_FIRST_YEAR,
    DEFAULT_LAST_YEAR,
    DEFAULT_PERIOD_YEARS,
    InvalidQueryError,
    PeriodAverageService,
    UnknownIndicatorError,
)

router = APIRouter(prefix="/api", tags=["period averages"])


def period_average_query(
    indicator_code: str,
    country: Annotated[
        list[str] | None,
        Query(description="ISO3 code; repeat it for more countries"),
    ] = None,
    first_year: int = DEFAULT_FIRST_YEAR,
    last_year: int = DEFAULT_LAST_YEAR,
    period_years: Annotated[int, Query(ge=1)] = DEFAULT_PERIOD_YEARS,
    sex: Sex = AVERAGED_SEX,
) -> PeriodAverageQuery:
    """Bind and normalize REST query parameters into a PeriodAverageQuery."""
    cleaned = tuple(
        dict.fromkeys(
            c.strip().upper()
            for c in (country or ())
            if c.strip()
        )
    )
    return PeriodAverageQuery(
        indicator_code=indicator_code,
        country_iso3s=cleaned,
        first_year=first_year,
        last_year=last_year,
        period_years=period_years,
        sex=sex,
    )


@router.get("/indicators/{indicator_code}/period-averages")
def get_period_averages(
    query: Annotated[PeriodAverageQuery, Depends(period_average_query)],
    service: Annotated[
        PeriodAverageService, Depends(get_period_average_service)
    ],
) -> PeriodAveragesResponse:
    """Return per-period indicator averages for the requested countries."""
    try:
        report = service.get_report(query)
    except UnknownIndicatorError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    except InvalidQueryError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)
        ) from error
    return PeriodAveragesResponse.from_domain(report)
