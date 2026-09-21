"""Immutable request-owned datasets; no implicit file, network, or database lookup."""

from dataclasses import dataclass
from typing import Annotated, Protocol, Self

from pydantic import (
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    ValidationError,
    model_validator,
)

from ..base import ContractModel, NonEmptyStr
from ..provenance import ProvenanceRecords
from ..validation.table import AnalysisTable

type JsonScalar = StrictStr | StrictInt | StrictFloat | StrictBool | None


class DatasetReference(ContractModel):
    reference: NonEmptyStr
    version: NonEmptyStr


class AnalysisDatasetInput(ContractModel):
    reference: NonEmptyStr
    experiment_id: NonEmptyStr
    version: NonEmptyStr
    columns: Annotated[tuple[NonEmptyStr, ...], Field(min_length=1)]
    rows: tuple[tuple[JsonScalar, ...], ...]
    provenance: ProvenanceRecords

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        if len(set(self.columns)) != len(self.columns):
            raise ValueError("dataset columns must be distinct")
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError("dataset rows must match declared columns")
        return self


@dataclass(frozen=True)
class ResolvedAnalysisDataset:
    table: AnalysisTable
    provenance: ProvenanceRecords
    version: str


class DatasetResolutionFailure(ContractModel):
    code: NonEmptyStr


class AnalysisDataResolver(Protocol):
    def resolve(
        self, reference: str, experiment_id: str
    ) -> ResolvedAnalysisDataset | DatasetResolutionFailure: ...


class RequestDatasetResolver:
    def __init__(self, datasets: tuple[AnalysisDatasetInput, ...]) -> None:
        self._datasets: dict[str, AnalysisDatasetInput] = {}
        self._invalid = False
        self._ambiguous: set[str] = set()
        for supplied in datasets:
            try:
                item = AnalysisDatasetInput.model_validate(supplied.model_dump(warnings=False))
            except (ValidationError, TypeError, ValueError):
                self._invalid = True
                continue
            if item.reference in self._datasets:
                self._ambiguous.add(item.reference)
            self._datasets[item.reference] = item

    def resolve(
        self, reference: str, experiment_id: str
    ) -> ResolvedAnalysisDataset | DatasetResolutionFailure:
        if self._invalid:
            return DatasetResolutionFailure(code="analysis.dataset_invalid")
        if reference in self._ambiguous:
            return DatasetResolutionFailure(code="analysis.dataset_ambiguous")
        item = self._datasets.get(reference)
        if item is None:
            return DatasetResolutionFailure(code="analysis.dataset_missing")
        if item.experiment_id != experiment_id:
            return DatasetResolutionFailure(code="analysis.dataset_ownership")
        return ResolvedAnalysisDataset(
            table=AnalysisTable(columns=item.columns, rows=item.rows),
            provenance=item.provenance,
            version=item.version,
        )
