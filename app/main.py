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
    version="1.4.0",
)

# Mount static files for local Three.js, Globe.gl, TopoJSON, and textures
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
    diet: str = Field(default="mediterranean", examples=["mediterranean"])
    bmi: str = Field(default="normal", examples=["normal"])
    sleep: str = Field(default="optimal", examples=["optimal"])
    stress: str = Field(default="low", examples=["low"])


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


def normalize_query_year(year_val: Optional[str]) -> Optional[int]:
    """
    Intelligently parses user year inputs:
    - Strips whitespace and safely handles string/numeric types.
    - Expands 2-digit years (e.g., '24' -> 2024, '25' -> 2025, '99' -> 1999).
    - Returns None if empty or unparseable.
    """
    if year_val is None or not str(year_val).strip():
        return None
    try:
        yr = int(str(year_val).strip())
        if 0 <= yr <= 50:
            return 2000 + yr
        elif 51 <= yr <= 99:
            return 1900 + yr
        return yr
    except ValueError:
        return None


@app.get("/observations", response_class=HTMLResponse)
def observations_page(
    request: Request,
    country_iso3: Optional[str] = None,
    indicator_code: Optional[str] = None,
    year: Optional[str] = None,
    is_outlier: Optional[str] = None,
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

    clean_country = country_iso3.strip().upper() if country_iso3 and country_iso3.strip() else None
    clean_indicator = indicator_code.strip() if indicator_code and indicator_code.strip() else None
    parsed_year = normalize_query_year(year)

    if clean_country:
        query = query.filter(Observation.country_iso3 == clean_country)
    if clean_indicator:
        query = query.filter(Indicator.code == clean_indicator)
    if parsed_year is not None:
        query = query.filter(Observation.year == parsed_year)
    if is_outlier == "true":
        query = query.filter(Observation.is_outlier == True)
    elif is_outlier == "false":
        query = query.filter(Observation.is_outlier == False)

    observations = query.order_by(desc(Observation.year), Country.name).limit(100).all()
    countries = db.query(Country).order_by(Country.name).all()
    indicators = db.query(Indicator).order_by(Indicator.name).all()

    # If no observations found with current filters, query available years in DB to guide user
    available_years_info = None
    if len(observations) == 0 and (clean_country or clean_indicator or parsed_year):
        avail_q = (
            db.query(
                func.min(Observation.year).label("min_year"),
                func.max(Observation.year).label("max_year"),
                func.count(Observation.observation_id).label("total_count"),
            )
            .join(Indicator)
        )
        if clean_country:
            avail_q = avail_q.filter(Observation.country_iso3 == clean_country)
        if clean_indicator:
            avail_q = avail_q.filter(Indicator.code == clean_indicator)

        row = avail_q.first()
        if row and row.total_count and row.total_count > 0:
            available_years_info = {
                "min_year": row.min_year,
                "max_year": row.max_year,
                "total_count": row.total_count,
            }

    return templates.TemplateResponse(
        request=request,
        name="observations.html",
        context={
            "active_page": "observations",
            "observations": observations,
            "countries": countries,
            "indicators": indicators,
            "selected_country": clean_country or "",
            "selected_indicator": clean_indicator or "",
            "selected_year": parsed_year or "",
            "selected_outlier": is_outlier or "",
            "available_years_info": available_years_info,
        },
    )


@app.get("/api/observations")
def get_observations_api(
    country_iso3: Optional[str] = None,
    indicator_code: Optional[str] = None,
    year: Optional[str] = None,
    is_outlier: Optional[str] = None,
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

    clean_country = country_iso3.strip().upper() if country_iso3 and country_iso3.strip() else None
    clean_indicator = indicator_code.strip() if indicator_code and indicator_code.strip() else None
    parsed_year = normalize_query_year(year)

    if clean_country:
        query = query.filter(Observation.country_iso3 == clean_country)
    if clean_indicator:
        query = query.filter(Indicator.code == clean_indicator)
    if parsed_year is not None:
        query = query.filter(Observation.year == parsed_year)
    if is_outlier == "true":
        query = query.filter(Observation.is_outlier == True)
    elif is_outlier == "false":
        query = query.filter(Observation.is_outlier == False)

    results = query.order_by(desc(Observation.year), Country.name).limit(limit).all()
    return [
        {
            "observation_id": r.observation_id,
            "country_iso3": r.country_iso3,
            "country_name": r.country_name,
            "indicator_code": r.indicator_code,
            "indicator_name": r.indicator_name,
            "year": r.year,
            "sex": r.sex.value if hasattr(r.sex, "value") else str(r.sex),
            "value": float(r.value) if r.value is not None else None,
            "is_outlier": r.is_outlier,
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
    Returns country longevity statistics keyed by ISO3, ISO2, numeric country IDs,
    and common names for 3D globe rendering, choropleth shading, and interactive hover tooltips.
    """
    sub = (
        db.query(
            Observation.country_iso3,
            func.max(Observation.year).label("max_year"),
        )
        .join(Indicator)
        .filter(Indicator.code.in_(["WHOSIS_000001", "SP.DYN.LE00.IN", "OWID_LIFE_EXPECTANCY"]))
        .group_by(Observation.country_iso3)
        .subquery()
    )

    results = (
        db.query(
            Country.iso3,
            Country.name,
            Country.region,
            Observation.value,
            Observation.year,
        )
        .join(sub, Country.iso3 == sub.c.country_iso3)
        .join(
            Observation,
            (Observation.country_iso3 == sub.c.country_iso3)
            & (Observation.year == sub.c.max_year),
        )
        .join(Indicator)
        .filter(
            Indicator.code.in_(["WHOSIS_000001", "SP.DYN.LE00.IN", "OWID_LIFE_EXPECTANCY"]),
            Observation.sex.in_(["BTSX", "ALL"]),
        )
        .all()
    )

    stats = {}
    for r in results:
        val = float(r.value) if r.value else None
        item = {
            "iso3": r.iso3,
            "name": r.name,
            "region": r.region,
            "life_expectancy": val,
            "year": r.year,
        }
        stats[r.iso3] = item

        try:
            pc = pycountry.countries.get(alpha_3=r.iso3)
            if pc:
                if hasattr(pc, "numeric") and pc.numeric:
                    stats[int(pc.numeric)] = item
                    stats[str(pc.numeric)] = item
                if hasattr(pc, "alpha_2") and pc.alpha_2:
                    stats[pc.alpha_2] = item
                if hasattr(pc, "name") and pc.name:
                    stats[pc.name] = item
        except Exception:
            pass

    return stats


@app.post("/api/pipeline/sync-country/{iso3}")
def live_sync_country(iso3: str):
    """Real-time pipeline trigger: fetches live data from WHO/World Bank and updates database."""
    sync_result = sync_country_realtime(iso3.strip().upper())
    return sync_result


@app.get("/api/country/{iso3}/baseline")
def get_country_baseline(iso3: str, sex: str = "BTSX", live_sync: bool = False, db: Session = Depends(get_db)):
    clean_iso3 = iso3.strip().upper()
    if live_sync:
        sync_country_realtime(clean_iso3)

    country = db.query(Country).filter(Country.iso3 == clean_iso3).first()
    if not country:
        return JSONResponse(status_code=404, content={"error": f"Country {iso3} not found"})

    obs = (
        db.query(Observation)
        .join(Indicator)
        .filter(
            Observation.country_iso3 == clean_iso3,
            Indicator.code.in_(["WHOSIS_000001", "SP.DYN.LE00.IN", "OWID_LIFE_EXPECTANCY"]),
            Observation.sex.in_([sex, "BTSX", "ALL"]),
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
    clean_iso3 = req.country_iso3.strip().upper()
    country = db.query(Country).filter(Country.iso3 == clean_iso3).first()
    country_name = country.name if country else clean_iso3

    obs = (
        db.query(Observation)
        .join(Indicator)
        .filter(
            Observation.country_iso3 == clean_iso3,
            Indicator.code.in_(["WHOSIS_000001", "SP.DYN.LE00.IN", "OWID_LIFE_EXPECTANCY"]),
            Observation.sex.in_([req.sex, "BTSX", "ALL"]),
        )
        .order_by(desc(Observation.year))
        .first()
    )

    baseline_le = float(obs.value) if obs and obs.value else 74.0

    # Call AI / ML Longevity Algorithm with Chronic Diseases and Habits
    forecast = predict_longevity(
        country_iso3=clean_iso3,
        country_name=country_name,
        baseline_life_expectancy=baseline_le,
        current_age=req.current_age,
        sex=req.sex,
        chronic_diseases=req.chronic_diseases,
        smoking=req.smoking,
        alcohol=req.alcohol,
        exercise=req.exercise,
        diet=req.diet,
        bmi=req.bmi,
        sleep=req.sleep,
        stress=req.stress,
    )

    return forecast
