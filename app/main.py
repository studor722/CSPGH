from typing import Optional, List
from fastapi import FastAPI, Depends, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import Country, Indicator, Observation, Source

app = FastAPI(
    title="Global Health Data Platform",
    description="Lab 1: Global Health Data Platform - Data Ingestion and Warehouse for Life Expectancy and Behavioral Risk Factors",
    version="1.0.0",
)

templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=RedirectResponse)
def root():
    return RedirectResponse(url="/observations")


@app.get("/observations", response_class=HTMLResponse)
def observations_page(
    request: Request,
    country_iso3: Optional[str] = None,
    indicator_code: Optional[str] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db),
):
    query = (
        db.query(
            Observation.country_iso3,
            Country.name.label("country_name"),
            Indicator.name.label("indicator_name"),
            Indicator.unit,
            Observation.year,
            Observation.sex,
            Observation.value,
        )
        .join(Country, Observation.country_iso3 == Country.iso3)
        .join(Indicator, Observation.indicator_id == Indicator.indicator_id)
    )

    if country_iso3:
        query = query.filter(Observation.country_iso3 == country_iso3)
    if indicator_code:
        query = query.filter(Indicator.code == indicator_code)
    if year:
        query = query.filter(Observation.year == year)

    observations = query.order_by(desc(Observation.year), Country.name).limit(100).all()
    countries = db.query(Country).order_by(Country.name).all()
    indicators = db.query(Indicator).order_by(Indicator.name).all()

    return templates.TemplateResponse(
        request=request,
        name="observations.html",
        context={
            "active_page": "observations",
            "observations": observations,
            "countries": countries,
            "indicators": indicators,
            "selected_country": country_iso3,
            "selected_indicator": indicator_code,
            "selected_year": year,
        },
    )


@app.get("/api/observations")
def get_observations_api(
    country_iso3: Optional[str] = None,
    indicator_code: Optional[str] = None,
    year: Optional[int] = None,
    limit: int = Query(default=100, le=1000),
    db: Session = Depends(get_db),
):
    query = (
        db.query(
            Observation.observation_id,
            Observation.country_iso3,
            Country.name.label("country_name"),
            Indicator.code.label("indicator_code"),
            Indicator.name.label("indicator_name"),
            Observation.year,
            Observation.sex,
            Observation.value,
        )
        .join(Country, Observation.country_iso3 == Country.iso3)
        .join(Indicator, Observation.indicator_id == Indicator.indicator_id)
    )

    if country_iso3:
        query = query.filter(Observation.country_iso3 == country_iso3)
    if indicator_code:
        query = query.filter(Indicator.code == indicator_code)
    if year:
        query = query.filter(Observation.year == year)

    results = query.order_by(desc(Observation.year)).limit(limit).all()
    return [
        {
            "observation_id": r.observation_id,
            "country_iso3": r.country_iso3,
            "country_name": r.country_name,
            "indicator_code": r.indicator_code,
            "indicator_name": r.indicator_name,
            "year": r.year,
            "sex": r.sex,
            "value": float(r.value) if r.value is not None else None,
        }
        for r in results
    ]


@app.get("/api/countries")
def get_countries_api(db: Session = Depends(get_db)):
    return db.query(Country).order_by(Country.name).all()


@app.get("/api/indicators")
def get_indicators_api(db: Session = Depends(get_db)):
    return db.query(Indicator).order_by(Indicator.name).all()
