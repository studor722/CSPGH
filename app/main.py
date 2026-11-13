"""FastAPI application factory assembling static assets and controllers."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.controllers import (
    api_controller,
    calculator_controller,
    etl_controller,
    observation_controller,
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
    )

    application.mount("/static", StaticFiles(directory="app/static"), name="static")

    application.include_router(calculator_controller.router)
    application.include_router(observation_controller.router)
    application.include_router(etl_controller.router)
    application.include_router(api_controller.router)
    return application


app = create_app()
