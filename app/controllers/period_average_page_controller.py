"""HTML shell controller for the client-side rendered period-averages page."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.controllers.api import API_DOCS_URL
from app.services.period_average_service import (
    DEFAULT_FIRST_YEAR,
    DEFAULT_LAST_YEAR,
)

router = APIRouter(include_in_schema=False, tags=["period averages page"])
templates = Jinja2Templates(directory="app/templates")

MAX_CHART_COUNTRIES = 8


@router.get("/period-averages", response_class=HTMLResponse)
def show_period_averages(request: Request) -> HTMLResponse:
    """Serve the empty HTML shell; JavaScript fetches all data from /api."""
    return templates.TemplateResponse(
        request=request,
        name="period_averages.html",
        context={
            "active_page": "period_averages",
            "first_year": DEFAULT_FIRST_YEAR,
            "last_year": DEFAULT_LAST_YEAR,
            "max_countries": MAX_CHART_COUNTRIES,
            "api_docs_url": API_DOCS_URL,
        },
    )
