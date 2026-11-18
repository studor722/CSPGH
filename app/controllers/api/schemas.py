"""Pydantic Data Transfer Objects (DTOs) defining the public REST API contract."""

from decimal import Decimal

from pydantic import BaseModel

from app.domain import (
    CountrySeries,
    CountrySummary,
    IndicatorInfo,
    IndicatorSummary,
    Period,
    PeriodAverageReport,
)


def _to_number(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


class CountryResponse(BaseModel):
    """Public country representation for lookup endpoints."""

    iso3: str
    name: str

    @classmethod
    def from_domain(cls, country: CountrySummary) -> "CountryResponse":
        return cls(iso3=country.iso3, name=country.name)


class IndicatorResponse(BaseModel):
    """Public indicator summary for lookup endpoints."""

    code: str
    name: str

    @classmethod
    def from_domain(cls, indicator: IndicatorSummary) -> "IndicatorResponse":
        return cls(code=indicator.code, name=indicator.name)


class IndicatorDetailResponse(BaseModel):
    """Detailed indicator metadata including measurement unit."""

    code: str
    name: str
    unit: str

    @classmethod
    def from_domain(cls, indicator: IndicatorInfo) -> "IndicatorDetailResponse":
        return cls(code=indicator.code, name=indicator.name, unit=indicator.unit)


class PeriodResponse(BaseModel):
    """Year bucket metadata used as chart x-axis and table columns."""

    start: int
    end: int
    label: str

    @classmethod
    def from_domain(cls, period: Period) -> "PeriodResponse":
        return cls(start=period.start, end=period.end, label=period.label)


class CountrySeriesResponse(BaseModel):
    """One country's ordered per-period averages."""

    country_iso3: str
    country_name: str
    averages: list[float | None]

    @classmethod
    def from_domain(cls, series: CountrySeries) -> "CountrySeriesResponse":
        return cls(
            country_iso3=series.country_iso3,
            country_name=series.country_name,
            averages=[_to_number(a) for a in series.averages],
        )


class PeriodAveragesResponse(BaseModel):
    """Top-level response payload for /api/indicators/{code}/period-averages."""

    indicator: IndicatorDetailResponse
    periods: list[PeriodResponse]
    series: list[CountrySeriesResponse]

    @classmethod
    def from_domain(cls, report: PeriodAverageReport) -> "PeriodAveragesResponse":
        return cls(
            indicator=IndicatorDetailResponse.from_domain(report.indicator),
            periods=[PeriodResponse.from_domain(p) for p in report.periods],
            series=[CountrySeriesResponse.from_domain(s) for s in report.series],
        )
