"""Typed outcome records shared by CLI runners, ETL services, and web actions."""

from dataclasses import dataclass
from enum import StrEnum


class StepStatus(StrEnum):
    OK = "ok"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class StepResult:
    """Result of one extract or transform+load step for a single dataset item."""

    source: str
    item: str
    status: StepStatus
    detail: str

    @property
    def ok(self) -> bool:
        return self.status == StepStatus.OK

    @property
    def skipped(self) -> bool:
        return self.status == StepStatus.SKIPPED

    @classmethod
    def from_error(cls, source: str, item: str, exc: BaseException) -> "StepResult":
        """Build a failed step result carrying the exception description."""
        return cls(
            source=source,
            item=item,
            status=StepStatus.FAILED,
            detail=str(exc),
        )

