"""JSON API controller for warehouse queries, 3D globe data, sync, and forecast evaluation."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import pycountry

from app.controllers.form_fields import (
    blank_to_none,
    to_bool_or_none,
    to_sex_or_none,
)
from app.dependencies import get_etl_service, get_observation_service
from app.domain import ObservationCriteria
from app.ml_model import CHRONIC_DISEASE_IMPACTS, predict_longevity
from app.services.etl_service import EtlService
from app.services.observation_service import ObservationService

router = APIRouter(prefix="/api", tags=["api"])


class CalculatorRequest(BaseModel):
    country_iso3: str = Field(default="USA", examples=["USA"])
    current_age: int = Field(default=28, ge=1, le=110)
    sex: str = Field(default="BTSX", examples=["BTSX"])
    chronic_diseases: List[str] = Field(
        default_factory=list, examples=[["cardiovascular", "hypertension"]]
    )
    smoking: str = Field(default="never", examples=["never"])
    alcohol: str = Field(default="none", examples=["none"])
    exercise: str = Field(default="active", examples=["active"])
    diet: str = Field(default="mediterranean", examples=["mediterranean"])
    bmi: str = Field(default="normal", examples=["normal"])
    sleep: str = Field(default="optimal", examples=["optimal"])
    stress: str = Field(default="low", examples=["low"])


def normalize_query_year(year_val: Optional[str]) -> Optional[int]:
    """Parse user year input, expanding 2-digit shorthand years to 4 digits."""
    if year_val is None or not str(year_val).strip():
        return None
    try:
        yr = int(str(year_val).strip())
        if 0 <= yr <= 50:
            return 2000 + yr
        if 51 <= yr <= 99:
            return 1900 + yr
        return yr
    except ValueError:
        return None


@router.get("/observations")
def get_observations_api(
    country_iso3: Optional[str] = None,
    indicator_code: Optional[str] = None,
    region: Optional[str] = None,
    year: Optional[str] = None,
    sex: Optional[str] = None,
    is_outlier: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    service: ObservationService = Depends(get_observation_service),
):
    cleaned_country = blank_to_none(country_iso3)
    parsed_year = normalize_query_year(year)
    criteria = ObservationCriteria(
        country_iso3=cleaned_country.upper() if cleaned_country else None,
        indicator_code=blank_to_none(indicator_code),
        region=blank_to_none(region),
        year_from=parsed_year,
        year_to=parsed_year,
        sex=to_sex_or_none(sex),
        is_outlier=to_bool_or_none(is_outlier),
    )
    results = service.list_api_observations(criteria, limit=limit)
    return [
        {
            "observation_id": r.observation_id,
            "country_iso3": r.country_iso3,
            "country_name": r.country_name,
            "region": r.region,
            "indicator_code": r.indicator_code,
            "indicator_name": r.indicator_name,
            "unit": r.unit,
            "year": r.year,
            "sex": r.sex.value if hasattr(r.sex, "value") else str(r.sex),
            "value": float(r.value) if r.value is not None else None,
            "is_outlier": r.is_outlier,
        }
        for r in results
    ]


@router.get("/chronic-diseases")
def get_chronic_diseases():
    return CHRONIC_DISEASE_IMPACTS


@router.get("/globe/countries-stats")
def get_globe_countries_stats(
    service: ObservationService = Depends(get_observation_service),
):
    """Return latest country longevity stats indexed by ISO3, ISO2, numeric ID, and name."""
    stats = {}
    for r in service.list_globe_stats():
        item = {
            "iso3": r.iso3,
            "name": r.name,
            "region": r.region,
            "life_expectancy": r.life_expectancy,
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


@router.post("/pipeline/sync-country/{iso3}")
def live_sync_country(
    iso3: str,
    etl_service: EtlService = Depends(get_etl_service),
):
    """Fetch live data from WHO/World Bank for one country and upsert it."""
    return etl_service.sync_country(iso3)


@router.get("/country/{iso3}/baseline")
def get_country_baseline(
    iso3: str,
    sex: str = "BTSX",
    live_sync: bool = False,
    service: ObservationService = Depends(get_observation_service),
    etl_service: EtlService = Depends(get_etl_service),
):
    clean_iso3 = iso3.strip().upper()
    if live_sync:
        etl_service.sync_country(clean_iso3)

    baseline = service.get_country_baseline(clean_iso3, sex=sex)
    if baseline is None:
        return JSONResponse(
            status_code=404, content={"error": f"Country {iso3} not found"}
        )

    return {
        "iso3": baseline.iso3,
        "name": baseline.name,
        "region": baseline.region,
        "income_group": baseline.income_group,
        "life_expectancy": baseline.life_expectancy,
        "reference_year": baseline.reference_year,
        "source": "PostgreSQL Data Warehouse (Verified)",
    }


@router.post("/calculator/evaluate")
def evaluate_life_expectancy(
    req: CalculatorRequest,
    service: ObservationService = Depends(get_observation_service),
):
    clean_iso3 = req.country_iso3.strip().upper()
    baseline = service.get_country_baseline(clean_iso3, sex=req.sex)
    country_name = baseline.name if baseline is not None else clean_iso3
    baseline_le = baseline.life_expectancy if baseline is not None else 74.0

    return predict_longevity(
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

