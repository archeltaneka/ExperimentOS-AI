"""Shared fail-closed helpers for owned source adapters."""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum

from pydantic import BaseModel, ValidationError

from ..base import ContractModel
from ..provenance import Diagnostic, DiagnosticOutcome, DiagnosticSeverity
from .source_models import SourceRecord


def revalidate_exact[OwnedSource: ContractModel](
    source: object, expected: type[OwnedSource]
) -> OwnedSource | None:
    """Revalidate an exact owned type so unchecked copies cannot cross the boundary."""
    if type(source) is not expected:
        return None
    try:
        assert isinstance(source, expected)
        return expected.model_validate(source.model_dump(mode="python", round_trip=True))
    except (AttributeError, TypeError, ValueError, ValidationError):
        return None


def value_text(value: object, fallback: str) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, str) and value:
        return value
    return fallback


def snapshot(scope: str, records: Iterable[BaseModel]) -> tuple[SourceRecord, ...]:
    return tuple(
        SourceRecord(
            scope=scope,
            record_type=f"{type(record).__module__}.{type(record).__name__}",
            payload=record.model_dump(mode="json"),
        )
        for record in records
    )


def block(code: str, message: str) -> Diagnostic:
    return Diagnostic(
        code=code,
        severity=DiagnosticSeverity.FATAL,
        outcome=DiagnosticOutcome.FAILED,
        message=message,
    )


def native_diagnostic_blocks(records: Iterable[BaseModel]) -> tuple[Diagnostic, ...]:
    """Apply the shared fatal/error-failed policy without dropping source records."""
    result: list[Diagnostic] = []
    for record in records:
        severity = value_text(getattr(record, "severity", None), "")
        status = value_text(getattr(record, "status", getattr(record, "outcome", None)), "")
        if severity == DiagnosticSeverity.FATAL.value or (
            severity == DiagnosticSeverity.ERROR.value and status == "failed"
        ):
            native_code = value_text(getattr(record, "code", None), "unknown")
            message = value_text(
                getattr(record, "message", None),
                "Source diagnostic blocks business-impact use.",
            )
            result.append(block(f"impact.source.native_diagnostic.{native_code}", message))
    return tuple(result)


def unique_blocks(records: Iterable[Diagnostic]) -> tuple[Diagnostic, ...]:
    by_code: dict[str, Diagnostic] = {}
    for record in records:
        by_code.setdefault(record.code, record)
    return tuple(by_code[code] for code in sorted(by_code))


def interval_contains(point: float | None, interval: object | None) -> bool:
    if point is None or interval is None:
        return False
    lower = getattr(interval, "lower", None)
    upper = getattr(interval, "upper", None)
    return isinstance(lower, float) and isinstance(upper, float) and lower <= point <= upper


__all__ = [
    "block",
    "native_diagnostic_blocks",
    "interval_contains",
    "revalidate_exact",
    "snapshot",
    "unique_blocks",
    "value_text",
]
