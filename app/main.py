"""FastAPI application factory assembling static assets and controllers."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.controllers import (
    api_controller,
    calculator_controller,
    etl_controller,
    observation_controller,
    period_average_page_controller,
)
from app.controllers.api import (
    API_DOCS_URL,
    API_OPENAPI_URL,
    period_average_api,
    reference_data_api,
)


def create_app() -> FastAPI:
    """Create and configure the FastAPI web application."""
    application = FastAPI(
        title="Global Health Data Platform & Life Expectancy Calculator",
        description=(
            "Global Health Data Platform and Chronic Disease / Lifestyle Longevity "
            "Calculator using WHO, World Bank, and Our World in Data."
        ),
        version="2.0.0",
        openapi_url=API_OPENAPI_URL,
        docs_url=API_DOCS_URL,
        redoc_url=None,
    )

    application.mount("/static", StaticFiles(directory="app/static"), name="static")

    application.include_router(calculator_controller.router)
    application.include_router(observation_controller.router)
    application.include_router(etl_controller.router)
    application.include_router(period_average_page_controller.router)
    application.include_router(reference_data_api.router)
    application.include_router(period_average_api.router)
    application.include_router(api_controller.router)
    return application


app = create_app()
