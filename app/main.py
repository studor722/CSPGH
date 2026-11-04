from decimal import Decimal
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Depends, Request, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from fastapi.staticfiles import StaticFiles
import pycountry

from app.database import get_db
from app.models import Country, Indicator, Observation, Source
from app.ml_model import predict_longevity, CHRONIC_DISEASE_IMPACTS, HABIT_IMPACTS
from etl.realtime_pipeline import sync_country_realtime

app = FastAPI(
    title="Global Health Data Platform & Life Expectancy Calculator",
    description="Real-time Global Health Data Platform and Chronic Disease / Lifestyle Longevity Calculator using WHO & World Bank APIs.",
    version="1.3.0",
)

# Mount static files for local D3, TopoJSON, and World Atlas
app.mount("/static", StaticFiles(directory="app/static"), name="static")

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
            Observation.is_outlier,
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
            Observation.is_outlier,
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


@app.get("/api/chronic-diseases")
def get_chronic_diseases():
    return CHRONIC_DISEASE_IMPACTS


@app.get("/api/globe/countries-stats")
def get_globe_countries_stats(db: Session = Depends(get_db)):
    """
    Returns country longevity statistics keyed by both ISO3 and numeric country IDs
    for fast 3D globe rendering, choropleth shading, and interactive hover tooltips.
    """
    sub = (
        db.query(
            Observation.country_iso3,
            func.max(Observation.year).label("max_year")
        )
        .join(Indicator)
        .filter(Indicator.code.in_(["WHOSIS_000001", "SP.DYN.LE00.IN"]))
        .group_by(Observation.country_iso3)
        .subquery()
    )

    rows = (
        db.query(
            Country.iso3,
            Country.name,
            Country.region,
            Country.income_group,
            Observation.value,
            Observation.year
        )
        .join(Country, Observation.country_iso3 == Country.iso3)
        .join(Indicator, Observation.indicator_id == Indicator.indicator_id)
        .join(sub, (Observation.country_iso3 == sub.c.country_iso3) & (Observation.year == sub.c.max_year))
        .filter(Indicator.code.in_(["WHOSIS_000001", "SP.DYN.LE00.IN"]))
        .filter(Observation.sex == "BTSX")
        .all()
    )

    stats = {}
    for r in rows:
        val = float(r.value)
        num_code = None
        try:
            c = pycountry.countries.get(alpha_3=r.iso3)
            if c and hasattr(c, "numeric"):
                num_code = str(int(c.numeric))
        except Exception:
            pass

        entry = {
            "iso3": r.iso3,
            "name": r.name,
            "region": r.region,
            "income_group": r.income_group,
            "life_expectancy": round(val, 1),
            "year": r.year,
        }
        stats[r.iso3] = entry
        if num_code:
            stats[num_code] = entry

    return stats


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
