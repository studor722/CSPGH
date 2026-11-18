"""Server-side rendered HTML controller for on-demand ETL pipeline actions."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import get_etl_service
from app.services.etl_service import EtlService
from etl.step_result import StepResult, StepStatus

router = APIRouter(prefix="/actions", include_in_schema=False, tags=["etl"])
templates = Jinja2Templates(directory="app/templates")


def _render_result(
    request: Request,
    *,
    action: str,
    description: str,
    results: list[StepResult],
):
    ok_count = sum(1 for r in results if r.status == StepStatus.OK)
    skipped_count = sum(1 for r in results if r.status == StepStatus.SKIPPED)
    failed_count = sum(1 for r in results if r.status == StepStatus.FAILED)

    return templates.TemplateResponse(
        request=request,
        name="action_result.html",
        context={
            "active_page": "observations",
            "action": action,
            "description": description,
            "results": results,
            "ok_count": ok_count,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
        },
    )


@router.post("/extract", response_class=HTMLResponse)
def extract_action(
    request: Request,
    service: EtlService = Depends(get_etl_service),
):
    """Download fresh upstream snapshots into local raw landing files."""
    results = service.extract_all()
    return _render_result(
        request,
        action="Extract fresh data from sources",
        description=(
            "Downloads raw JSON and CSV snapshots from World Bank, WHO GHO, and "
            "Our World in Data into the local landing directory."
        ),
        results=results,
    )


@router.post("/load", response_class=HTMLResponse)
def load_action(
    request: Request,
    service: EtlService = Depends(get_etl_service),
):
    """Transform and load cached local JSON/CSV snapshots into PostgreSQL."""
    results = service.transform_and_load_all()
    return _render_result(
        request,
        action="Transform & load data from local JSON/CSV files",
        description=(
            "Normalizes, cleans, flags IQR outliers, and upserts cached raw snapshots "
            "from disk into PostgreSQL."
        ),
        results=results,
    )

