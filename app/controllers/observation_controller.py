"""Server-side rendered HTML controller for warehouse observations."""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.controllers.form_fields import (
    blank_to_none,
    to_bool_or_none,
    to_int_or_none,
    to_sex_or_none,
)
from app.dependencies import get_observation_service
from app.domain import ObservationCriteria
from app.models import Sex
from app.services.observation_service import ObservationService

router = APIRouter(tags=["observations"])
templates = Jinja2Templates(directory="app/templates")

SEX_CHOICES: tuple[tuple[str, str], ...] = (
    (Sex.BOTH.value, "Both sexes"),
    (Sex.FEMALE.value, "Female"),
    (Sex.MALE.value, "Male"),
)


def observation_criteria(
    country: str | None = None,
    indicator: str | None = None,
    region: str | None = None,
    year_from: str | None = None,
    year_to: str | None = None,
    sex: str | None = None,
    is_outlier: str | None = None,
) -> ObservationCriteria:
    """Bind raw HTML query parameters into domain ObservationCriteria."""
    cleaned_country = blank_to_none(country)
    return ObservationCriteria(
        country_iso3=cleaned_country.upper() if cleaned_country else None,
        indicator_code=blank_to_none(indicator),
        region=blank_to_none(region),
        year_from=to_int_or_none(year_from),
        year_to=to_int_or_none(year_to),
        sex=to_sex_or_none(sex),
        is_outlier=to_bool_or_none(is_outlier),
    )


def _page_url(request: Request, page: int) -> str:
    updated = request.url.include_query_params(page=page)
    return f"{updated.path}?{updated.query}"


def _without_param_url(request: Request, param: str) -> str:
    updated = request.url.remove_query_params([param, "page"])
    return f"{updated.path}?{updated.query}" if updated.query else updated.path


@router.get("/observations", response_class=HTMLResponse)
def list_observations(
    request: Request,
    criteria: ObservationCriteria = Depends(observation_criteria),
    page: int = Query(default=1, ge=1),
    service: ObservationService = Depends(get_observation_service),
):
    """Render the server-side paginated observations warehouse view."""
    observations = service.list_observations(criteria, page=page)
    options = service.filter_options()
    raw_issues = service.validate_criteria(
        criteria, total_items=observations.total_items
    )
    filter_issues = [
        {
            "message": issue.message,
            "fix_url": _without_param_url(request, issue.fix_param),
            "fix_label": issue.fix_label,
        }
        for issue in raw_issues
    ]
    year_bounds = (
        service.available_year_bounds(criteria)
        if observations.total_items == 0 and criteria.has_any_filter and not filter_issues
        else None
    )

    return templates.TemplateResponse(
        request=request,
        name="observations.html",
        context={
            "active_page": "observations",
            "observations": observations,
            "criteria": criteria,
            "options": options,
            "sex_choices": SEX_CHOICES,
            "filter_issues": filter_issues,
            "year_bounds": year_bounds,
            "previous_url": (
                _page_url(request, page - 1) if observations.has_previous else None
            ),
            "next_url": (
                _page_url(request, page + 1) if observations.has_next else None
            ),
        },
    )

