from decimal import Decimal
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Depends, Request, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.database import get_db
from app.models import Country, Indicator, Observation, Source
from app.ml_model import predict_longevity, CHRONIC_DISEASE_IMPACTS, HABIT_IMPACTS
from etl.realtime_pipeline import sync_country_realtime

app = FastAPI(
    title="Vitalis - Global Health & Longevity Platform",
    description="Real-time Global Health Data Platform and Chronic Disease / Lifestyle Longevity Calculator using WHO & World Bank APIs.",
    version="1.2.0",
)

templates = Jinja2Templates(directory="app/templates")


class CalculatorRequest(BaseModel):
    country_iso3: str = Field(default="USA", examples=["USA"])
    current_age: int = Field(default=28, ge=1, le=110)
    sex: str = Field(default="BTSX", examples=["BTSX"])
    chronic_diseases: List[str] = Field(default_factory=list, examples=[["cardiovascular", "hypertension"]])
    smoking: str = Field(default="never", examples=["never"])
    alcohol: str = Field(default="none", examples=["none"])
    exercise: str = Field(default="active", examples=["active"])
    bmi: str = Field(default="normal", examples=["normal"])
    sleep: str = Field(default="optimal", examples=["optimal"])


@app.get("/", response_class=RedirectResponse)
def root():
    return RedirectResponse(url="/calculator")


@app.get("/calculator", response_class=HTMLResponse)
def calculator_page(request: Request, db: Session = Depends(get_db)):
    countries = db.query(Country).order_by(Country.name).all()
    return templates.TemplateResponse(
        request=request,
        name="calculator.html",
        context={
            "active_page": "calculator",
            "countries": countries,
            "chronic_diseases": CHRONIC_DISEASE_IMPACTS,
        },
    )


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


@app.get("/api/countries")
def get_countries(db: Session = Depends(get_db)):
    return db.query(Country).order_by(Country.name).all()


@app.get("/api/chronic-diseases")
def get_chronic_diseases():
    return CHRONIC_DISEASE_IMPACTS


@app.post("/api/pipeline/sync-country/{iso3}")
def live_sync_country(iso3: str):
    """Real-time pipeline trigger: fetches live data from WHO/World Bank and updates database."""
    sync_result = sync_country_realtime(iso3)
    return sync_result


@app.get("/api/country/{iso3}/baseline")
def get_country_baseline(iso3: str, sex: str = "BTSX", live_sync: bool = False, db: Session = Depends(get_db)):
    if live_sync:
        sync_country_realtime(iso3)

    country = db.query(Country).filter(Country.iso3 == iso3.upper()).first()
    if not country:
        return JSONResponse(status_code=404, content={"error": f"Country {iso3} not found"})

    obs = (
        db.query(Observation)
        .join(Indicator)
        .filter(
            Observation.country_iso3 == country.iso3,
            Indicator.code.in_(["WHOSIS_000001", "SP.DYN.LE00.IN"]),
            Observation.sex.in_([sex, "BTSX"]),
        )
        .order_by(desc(Observation.year))
        .first()
    )

    baseline_val = float(obs.value) if obs and obs.value else 74.0

    return {
        "iso3": country.iso3,
        "name": country.name,
        "region": country.region,
        "income_group": country.income_group,
        "life_expectancy": baseline_val,
        "reference_year": obs.year if obs else 2019,
        "source": "PostgreSQL Data Warehouse (Verified)",
    }


@app.post("/api/calculator/evaluate")
def evaluate_life_expectancy(req: CalculatorRequest, db: Session = Depends(get_db)):
    country = db.query(Country).filter(Country.iso3 == req.country_iso3.upper()).first()
    country_name = country.name if country else req.country_iso3

    obs = (
        db.query(Observation)
        .join(Indicator)
        .filter(
            Observation.country_iso3 == req.country_iso3.upper(),
            Indicator.code.in_(["WHOSIS_000001", "SP.DYN.LE00.IN"]),
            Observation.sex.in_([req.sex, "BTSX"]),
        )
        .order_by(desc(Observation.year))
        .first()
    )

    baseline_le = float(obs.value) if obs and obs.value else 74.0

    # Call AI / ML Longevity Algorithm with Chronic Diseases and Habits
    forecast = predict_longevity(
        country_iso3=req.country_iso3,
        country_name=country_name,
        baseline_life_expectancy=baseline_le,
        current_age=req.current_age,
        sex=req.sex,
        chronic_diseases=req.chronic_diseases,
        smoking=req.smoking,
        alcohol=req.alcohol,
        exercise=req.exercise,
        bmi=req.bmi,
        sleep=req.sleep,
    )

    return forecast
