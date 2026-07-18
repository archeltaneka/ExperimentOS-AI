"""Immutable tabular snapshots for deterministic analysis validation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


class AnalysisTableError(ValueError):
    """Raised when a caller-supplied table cannot form a valid immutable snapshot."""


@dataclass(frozen=True)
class AnalysisTable:
    """Ordered columns and rows captured without retaining caller-owned mappings."""

    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]

    def __post_init__(self) -> None:
        if any(len(row) != len(self.columns) for row in self.rows):
            raise AnalysisTableError("every row must match the declared column count")

    @classmethod
    def from_records(cls, records: Sequence[Mapping[str, object]]) -> AnalysisTable:
        """Snapshot records using the first record's deterministic column order."""
        snapshots = tuple(dict(record) for record in records)
        columns = tuple(snapshots[0]) if snapshots else ()
        if any(set(record) != set(columns) for record in snapshots):
            raise AnalysisTableError("every record must contain the same columns")
        return cls(
            columns=columns,
            rows=tuple(tuple(record[name] for name in columns) for record in snapshots),
        )
