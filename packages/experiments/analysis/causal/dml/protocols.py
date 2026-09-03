"""ExperimentOS-owned nuisance model protocols and fit evidence."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Literal, Protocol, Self, runtime_checkable

from pydantic import Field, field_validator, model_validator

from ...base import ContractModel, FiniteFloat, NonEmptyStr, ScalarValue
from .folds import canonical_observation_key

type PositiveCount = Annotated[int, Field(strict=True, gt=0)]
type NonNegativeCount = Annotated[int, Field(strict=True, ge=0)]
type NonNegativeFiniteFloat = Annotated[FiniteFloat, Field(ge=0.0)]


class NuisanceRole(StrEnum):
    """The two nuisance functions required by partialling-out DML."""

    OUTCOME = "outcome"
    TREATMENT = "treatment"


class NuisanceFitStatus(StrEnum):
    """Normalized fit state independent of estimator libraries."""

    CONVERGED = "converged"
    NON_CONVERGED = "non_converged"
    FAILED = "failed"


class NuisanceHyperparameter(ContractModel):
    """One deterministic scalar adapter configuration value."""

    key: NonEmptyStr
    value: ScalarValue


class NuisanceAdapterMetadata(ContractModel):
    """Reproducibility-critical adapter metadata with no fitted estimator state."""

    role: NuisanceRole
    adapter_name: NonEmptyStr
    adapter_version: NonEmptyStr
    model_family: NonEmptyStr
    hyperparameters: tuple[NuisanceHyperparameter, ...]
    preprocessing: NonEmptyStr
    feature_order: Annotated[tuple[NonEmptyStr, ...], Field(min_length=1)]
    deterministic: Literal[True] = True
    seed: Annotated[int, Field(strict=True, ge=0)]
    minimum_training_rows: PositiveCount
    dependency_name: NonEmptyStr
    dependency_version: NonEmptyStr
    configuration_fingerprint_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

    @field_validator("hyperparameters")
    @classmethod
    def canonicalize_hyperparameters(
        cls,
        value: tuple[NuisanceHyperparameter, ...],
    ) -> tuple[NuisanceHyperparameter, ...]:
        canonical = tuple(sorted(value, key=lambda item: item.key))
        if len(canonical) != len({item.key for item in canonical}):
            raise ValueError("nuisance hyperparameter keys must be unique")
        return canonical

    @field_validator("feature_order")
    @classmethod
    def require_unique_features(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("nuisance feature names must be unique")
        return value

    @classmethod
    def create(
        cls,
        *,
        role: NuisanceRole,
        adapter_name: str,
        adapter_version: str,
        model_family: str,
        hyperparameters: Mapping[str, ScalarValue],
        preprocessing: str,
        feature_order: tuple[str, ...],
        seed: int,
        minimum_training_rows: int,
        dependency_name: str,
        dependency_version: str,
    ) -> Self:
        values = tuple(
            NuisanceHyperparameter(key=key, value=value)
            for key, value in sorted(hyperparameters.items())
        )
        payload = {
            "adapter_name": adapter_name,
            "adapter_version": adapter_version,
            "dependency_name": dependency_name,
            "dependency_version": dependency_version,
            "deterministic": True,
            "feature_order": feature_order,
            "hyperparameters": tuple(item.model_dump(mode="json") for item in values),
            "minimum_training_rows": minimum_training_rows,
            "model_family": model_family,
            "preprocessing": preprocessing,
            "role": role.value,
            "seed": seed,
        }
        fingerprint = _fingerprint(payload)
        return cls(
            role=role,
            adapter_name=adapter_name,
            adapter_version=adapter_version,
            model_family=model_family,
            hyperparameters=values,
            preprocessing=preprocessing,
            feature_order=feature_order,
            seed=seed,
            minimum_training_rows=minimum_training_rows,
            dependency_name=dependency_name,
            dependency_version=dependency_version,
            configuration_fingerprint_sha256=fingerprint,
        )


class NuisanceFeatureBatch(ContractModel):
    """Owned aligned numeric features and identities supplied to an adapter."""

    observation_ids: Annotated[tuple[ScalarValue, ...], Field(min_length=1)]
    feature_names: Annotated[tuple[NonEmptyStr, ...], Field(min_length=1)]
    rows: Annotated[tuple[tuple[FiniteFloat, ...], ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_alignment(self) -> Self:
        if len(self.observation_ids) != len(self.rows):
            raise ValueError("observation IDs and feature rows must align")
        keys = tuple(canonical_observation_key(item) for item in self.observation_ids)
        if len(keys) != len(set(keys)):
            raise ValueError("observation IDs must be unique in a nuisance batch")
        if len(self.feature_names) != len(set(self.feature_names)):
            raise ValueError("nuisance feature names must be unique")
        if any(len(row) != len(self.feature_names) for row in self.rows):
            raise ValueError("every nuisance row must match the feature count")
        if any(not math.isfinite(value) for row in self.rows for value in row):
            raise ValueError("nuisance feature values must be finite")
        return self


class NuisancePreprocessingFeature(ContractModel):
    """Fold-local standardization provenance for one feature."""

    feature_name: NonEmptyStr
    mean: FiniteFloat
    scale: Annotated[FiniteFloat, Field(gt=0.0)]
    zero_variance: bool


class NuisanceFitReport(ContractModel):
    """Owned fold fit evidence without model objects or coefficient arrays."""

    role: NuisanceRole
    status: NuisanceFitStatus
    converged: bool
    training_count: PositiveCount
    iteration_count: NonNegativeCount | None = None
    classes: tuple[int, ...] = ()
    warning_codes: tuple[NonEmptyStr, ...] = ()
    preprocessing: tuple[NuisancePreprocessingFeature, ...] = ()

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        if (self.status is NuisanceFitStatus.CONVERGED) != self.converged:
            raise ValueError("only converged nuisance fits may set converged true")
        return self


@runtime_checkable
class OutcomeNuisanceModel(Protocol):
    """Owned interface for deterministic outcome nuisance adapters."""

    @property
    def metadata(self) -> NuisanceAdapterMetadata: ...

    def for_fold(self, seed: int) -> OutcomeNuisanceModel: ...

    def fit(
        self,
        batch: NuisanceFeatureBatch,
        target: tuple[float, ...],
    ) -> NuisanceFitReport: ...

    def predict(self, batch: NuisanceFeatureBatch) -> tuple[float, ...]: ...


@runtime_checkable
class TreatmentNuisanceModel(Protocol):
    """Owned interface for deterministic treatment nuisance adapters."""

    @property
    def metadata(self) -> NuisanceAdapterMetadata: ...

    def for_fold(self, seed: int) -> TreatmentNuisanceModel: ...

    def fit(
        self,
        batch: NuisanceFeatureBatch,
        target: tuple[float, ...],
    ) -> NuisanceFitReport: ...

    def predict_probability(self, batch: NuisanceFeatureBatch) -> tuple[float, ...]: ...


def validate_nuisance_adapter(
    adapter: object,
    *,
    role: NuisanceRole,
) -> OutcomeNuisanceModel | TreatmentNuisanceModel:
    """Reject adapters that do not satisfy the owned deterministic boundary."""
    protocol = OutcomeNuisanceModel if role is NuisanceRole.OUTCOME else TreatmentNuisanceModel
    if not isinstance(adapter, protocol):
        raise TypeError(f"adapter does not satisfy the {role.value} nuisance protocol")
    metadata = adapter.metadata
    if not isinstance(metadata, NuisanceAdapterMetadata):
        raise TypeError("nuisance adapter metadata must use the owned contract")
    if metadata.role is not role:
        raise ValueError("nuisance adapter metadata role does not match its requested role")
    expected = NuisanceAdapterMetadata.create(
        role=metadata.role,
        adapter_name=metadata.adapter_name,
        adapter_version=metadata.adapter_version,
        model_family=metadata.model_family,
        hyperparameters={item.key: item.value for item in metadata.hyperparameters},
        preprocessing=metadata.preprocessing,
        feature_order=metadata.feature_order,
        seed=metadata.seed,
        minimum_training_rows=metadata.minimum_training_rows,
        dependency_name=metadata.dependency_name,
        dependency_version=metadata.dependency_version,
    )
    if metadata.configuration_fingerprint_sha256 != expected.configuration_fingerprint_sha256:
        raise ValueError("nuisance adapter configuration fingerprint is invalid")
    return adapter


def _fingerprint(payload: object) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


__all__ = [
    "NuisanceAdapterMetadata",
    "NuisanceFeatureBatch",
    "NuisanceFitReport",
    "NuisanceFitStatus",
    "NuisanceHyperparameter",
    "NuisancePreprocessingFeature",
    "NuisanceRole",
    "OutcomeNuisanceModel",
    "TreatmentNuisanceModel",
    "validate_nuisance_adapter",
]
