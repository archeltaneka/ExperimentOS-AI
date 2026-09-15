"""Owned advanced estimator capability and execution protocol."""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from ...provenance import ProvenanceRecords
from ...validation.table import AnalysisTable

RequestT = TypeVar("RequestT", contravariant=True)
ResultT = TypeVar("ResultT", covariant=True)


@runtime_checkable
class AdvancedCausalEstimator(Protocol[RequestT, ResultT]):
    @property
    def adapter_id(self) -> str: ...

    @property
    def supported_estimand(self) -> str: ...

    @property
    def treatment_type(self) -> str: ...

    @property
    def outcome_type(self) -> str: ...

    def analyze(
        self,
        execution: RequestT,
        table: AnalysisTable,
        *,
        provenance: ProvenanceRecords,
    ) -> ResultT: ...
