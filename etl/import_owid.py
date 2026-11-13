"""Transform cached Our World in Data files and load them into PostgreSQL."""

from pathlib import Path

from etl.import_runner import (
    IndicatorSpec,
    SourceSpec,
    import_for_loaded_countries,
    report_and_exit_on_failure,
)
from etl.step_result import StepResult
from etl.transform_owid import transform_owid_chart_file

SOURCE = SourceSpec(
    name="Our World in Data",
    url="https://ourworldindata.org/",
    raw_dir=Path(__file__).resolve().parents[1] / "data" / "raw" / "owid",
)

INDICATORS: tuple[IndicatorSpec, ...] = (
    IndicatorSpec(
        code="OWID_LIFE_EXPECTANCY",
        remote_id="life-expectancy",
        name="Life expectancy",
        unit="years",
        raw_filename="life-expectancy_full.csv",
    ),
)


def import_all() -> list[StepResult]:
    """Load all cached Our World in Data indicators into PostgreSQL."""
    return import_for_loaded_countries(
        SOURCE,
        INDICATORS,
        transform_owid_chart_file,
        missing_countries_hint=(
            "The country table is empty; run `python -m etl.import_worldbank` first."
        ),
    )


if __name__ == "__main__":
    report_and_exit_on_failure(import_all())
