"""HTML controller for root redirect and longevity calculator page."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import get_observation_service
from app.ml_model import CHRONIC_DISEASE_IMPACTS
from app.services.observation_service import ObservationService

router = APIRouter(include_in_schema=False, tags=["calculator"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=RedirectResponse)
def root():
    return RedirectResponse(url="/calculator")


@router.get("/calculator", response_class=HTMLResponse)
def calculator_page(
    request: Request,
    service: ObservationService = Depends(get_observation_service),
):
    countries = service.list_countries()
    return templates.TemplateResponse(
        request=request,
        name="calculator.html",
        context={
            "active_page": "calculator",
            "countries": countries,
            "chronic_diseases": CHRONIC_DISEASE_IMPACTS,
        },
    )

