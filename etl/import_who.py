"""Transform cached WHO GHO files and load them into PostgreSQL."""

from pathlib import Path

from etl.import_runner import (
    IndicatorSpec,
    SourceSpec,
    import_for_loaded_countries,
    report_and_exit_on_failure,
)
from etl.step_result import StepResult
from etl.transform_who import transform_who_file

SOURCE = SourceSpec(
    name="WHO",
    url="https://www.who.int/data/gho",
    raw_dir=Path(__file__).resolve().parents[1] / "data" / "raw" / "who",
)

INDICATORS: tuple[IndicatorSpec, ...] = (
    IndicatorSpec(
        code="WHOSIS_000001",
        remote_id="WHOSIS_000001",
        name="Life expectancy at birth",
        unit="years",
        raw_filename="WHOSIS_000001_from2000.json",
    ),
    IndicatorSpec(
        code="M_Est_tob_curr_std",
        remote_id="M_Est_tob_curr_std",
        name="Age-standardized tobacco use prevalence",
        unit="%",
        raw_filename="M_Est_tob_curr_std_from2000.json",
    ),
)


def import_all() -> list[StepResult]:
    """Load all cached WHO indicators into PostgreSQL."""
    return import_for_loaded_countries(
        SOURCE,
        INDICATORS,
        transform_who_file,
        missing_countries_hint=(
            "The country table is empty; run `python -m etl.import_worldbank` first."
        ),
    )


if __name__ == "__main__":
    report_and_exit_on_failure(import_all())
