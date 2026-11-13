"""Transform cached World Bank files and load them into PostgreSQL."""

from pathlib import Path

from etl.import_runner import (
    IndicatorSpec,
    SourceSpec,
    import_worldbank_source,
    report_and_exit_on_failure,
)
from etl.step_result import StepResult
from etl.transform_worldbank import (
    transform_worldbank_country_file,
    transform_worldbank_indicator_file,
)

SOURCE = SourceSpec(
    name="World Bank",
    url="https://data.worldbank.org/",
    raw_dir=Path(__file__).resolve().parents[1] / "data" / "raw" / "worldbank",
)

INDICATORS: tuple[IndicatorSpec, ...] = (
    IndicatorSpec(
        code="SH.XPD.CHEX.GD.ZS",
        remote_id="SH.XPD.CHEX.GD.ZS",
        name="Current health expenditure",
        unit="% of GDP",
        raw_filename="SH.XPD.CHEX.GD.ZS_2000-2023.json",
    ),
    IndicatorSpec(
        code="NY.GDP.PCAP.CD",
        remote_id="NY.GDP.PCAP.CD",
        name="GDP per capita",
        unit="current US$",
        raw_filename="NY.GDP.PCAP.CD_2000-2023.json",
    ),
    IndicatorSpec(
        code="SP.DYN.IMRT.IN",
        remote_id="SP.DYN.IMRT.IN",
        name="Infant mortality rate",
        unit="per 1,000 live births",
        raw_filename="SP.DYN.IMRT.IN_2000-2023.json",
    ),
    IndicatorSpec(
        code="SH.IMM.MEAS",
        remote_id="SH.IMM.MEAS",
        name="Measles immunization",
        unit="% of children 12-23 months",
        raw_filename="SH.IMM.MEAS_2000-2023.json",
    ),
)


def import_all() -> list[StepResult]:
    """Load countries and all cached World Bank indicators into PostgreSQL."""
    return import_worldbank_source(
        SOURCE,
        INDICATORS,
        transform_worldbank_country_file,
        transform_worldbank_indicator_file,
    )


if __name__ == "__main__":
    report_and_exit_on_failure(import_all())
