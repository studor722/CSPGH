from decimal import Decimal
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Depends, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.database import get_db
from app.models import Country, Indicator, Observation, Source

app = FastAPI(
    title="Vitalis - Global Health & Longevity Data Platform",
    description="Global Health Data Platform and Lifestyle Life Expectancy Calculator using WHO, World Bank & OWID data.",
    version="1.0.0",
)

templates = Jinja2Templates(directory="app/templates")

# Epidemiological impact coefficients (years of life expectancy gain / loss)
# Benchmarked against Doll et al. BMJ 2004, Wood et al. Lancet 2018, Moore et al. PLOS Med 2012
HABIT_IMPACTS = {
    "smoking": {
        "never": 0.0,
        "former": -1.5,
        "light": -4.5,
        "moderate": -7.0,
        "heavy": -10.0,
    },
    "alcohol": {
        "none": 0.0,
        "moderate": -0.5,
        "heavy": -2.0,
        "excessive": -5.0,
    },
    "exercise": {
        "sedentary": -2.5,
        "light": 0.0,
        "active": 3.8,
        "high": 4.5,
    },
    "bmi": {
        "underweight": -2.0,
        "normal": 0.0,
        "overweight": -1.2,
        "obese": -4.0,
    },
}


class CalculatorRequest(BaseModel):
    country_iso3: str = Field(default="USA", examples=["USA"])
    current_age: int = Field(default=28, ge=1, le=110)
    sex: str = Field(default="BTSX", examples=["BTSX"])
    smoking: str = Field(default="never", examples=["never"])
    alcohol: str = Field(default="none", examples=["none"])
    exercise: str = Field(default="active", examples=["active"])
    bmi: str = Field(default="normal", examples=["normal"])


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


@app.get("/api/country/{iso3}/baseline")
def get_country_baseline(iso3: str, sex: str = "BTSX", db: Session = Depends(get_db)):
    country = db.query(Country).filter(Country.iso3 == iso3.upper()).first()
    if not country:
        return {"error": "Country not found"}

    # Query latest Life Expectancy from WHO (WHOSIS_000001) or WB (SP.DYN.LE00.IN)
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
    }


@app.post("/api/calculator/evaluate")
def evaluate_life_expectancy(req: CalculatorRequest, db: Session = Depends(get_db)):
    # 1. Fetch country baseline
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

    # 2. Compute individual habit deltas
    smoking_delta = HABIT_IMPACTS["smoking"].get(req.smoking.lower(), 0.0)
    alcohol_delta = HABIT_IMPACTS["alcohol"].get(req.alcohol.lower(), 0.0)
    exercise_delta = HABIT_IMPACTS["exercise"].get(req.exercise.lower(), 0.0)
    bmi_delta = HABIT_IMPACTS["bmi"].get(req.bmi.lower(), 0.0)

    net_delta = smoking_delta + alcohol_delta + exercise_delta + bmi_delta

    predicted_le = baseline_le + net_delta
    # A person cannot have predicted lifespan lower than their current age + buffer
    if predicted_le < (req.current_age + 1.0):
        predicted_le = float(req.current_age + 1.0)

    years_remaining = max(0.5, predicted_le - req.current_age)

    return {
        "country_iso3": req.country_iso3.upper(),
        "country_name": country_name,
        "current_age": req.current_age,
        "sex": req.sex,
        "baseline_life_expectancy": round(baseline_le, 2),
        "net_habit_impact": round(net_delta, 2),
        "predicted_life_expectancy": round(predicted_le, 2),
        "years_remaining": round(years_remaining, 2),
        "factors": {
            "smoking": round(smoking_delta, 2),
            "alcohol": round(alcohol_delta, 2),
            "exercise": round(exercise_delta, 2),
            "bmi": round(bmi_delta, 2),
        },
        "scientific_citations": [
            "Doll R, et al. Mortality in relation to smoking: 50 years' observations on male British doctors. BMJ 2004.",
            "Wood AM, et al. Risk thresholds for alcohol consumption: combined analysis of individual-participant data for 599,912 current drinkers. The Lancet 2018.",
            "Moore SC, et al. Leisure time physical activity of moderate to vigorous intensity and mortality: a pooled analysis of 650,000 adults. PLOS Medicine 2012.",
            "Prospective Studies Collaboration. Body-mass index and cause-specific mortality in 900,000 adults. The Lancet 2009.",
        ],
    }
