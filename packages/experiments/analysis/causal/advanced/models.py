"""Library-independent advanced estimator configuration, inference and provenance."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ...base import ContractModel, FiniteFloat, NonEmptyStr, PositiveFiniteFloat, Probability
from ...provenance import ProvenanceRecords
from ...uncertainty import ConfidenceInterval
from ..diagnostics import EvidenceLimitation
from ..dml.models import (
    DMLDiagnostic,
    DMLExecutionRequest,
    DMLFoldPlan,
    DMLNuisanceDiagnostics,
    DMLOverlapDiagnostic,
    DMLSampleCounts,
)
from ..dml.protocols import NuisanceHyperparameter
from ..dml.results import DMLAbstentionReason, DMLFoldFitProvenance, DMLStatus
from ..variables import MeasurementTiming, VariableRole


class AdvancedFailureCode(StrEnum):
    OPTIONAL_DEPENDENCY_UNAVAILABLE = "OPTIONAL_DEPENDENCY_UNAVAILABLE"
    INCOMPATIBLE_DEPENDENCY_RUNTIME = "INCOMPATIBLE_DEPENDENCY_RUNTIME"
    UNSUPPORTED_TREATMENT = "UNSUPPORTED_TREATMENT"
    UNSUPPORTED_OUTCOME = "UNSUPPORTED_OUTCOME"
    UNSUPPORTED_ESTIMAND = "UNSUPPORTED_ESTIMAND"
    UNSUPPORTED_INFERENCE = "UNSUPPORTED_INFERENCE"
    INVALID_EFFECT_MODIFIER = "INVALID_EFFECT_MODIFIER"
    INVALID_DATA_SHAPE = "INVALID_DATA_SHAPE"
    ESTIMATOR_FIT_FAILURE = "ESTIMATOR_FIT_FAILURE"
    INFERENCE_FAILURE = "INFERENCE_FAILURE"
    NONFINITE_ESTIMATE = "NONFINITE_ESTIMATE"
    NONFINITE_UNCERTAINTY = "NONFINITE_UNCERTAINTY"


class AdvancedEstimatorConfig(ContractModel):
    """Intentionally bounded adapter options, never a raw library argument dictionary."""

    inference_mode: NonEmptyStr = "statsmodels_hc1"
    constant_effect_assumption: bool = False
    ridge_alpha: PositiveFiniteFloat = 1.0
    logistic_c: PositiveFiniteFloat = 1.0
    logistic_tolerance: PositiveFiniteFloat = 1e-8
    logistic_max_iterations: Annotated[int, Field(strict=True, gt=0)] = 1000


class AdvancedInference(ContractModel):
    method: Literal["statsmodels_hc1"] = "statsmodels_hc1"
    standard_error: PositiveFiniteFloat
    statistic: FiniteFloat
    p_value: Probability
    confidence_interval: ConfidenceInterval
    reference_distribution: Literal["standard_normal"] = "standard_normal"
    finite_sample_correction: Literal["n_over_n_minus_final_design_rank"] = (
        "n_over_n_minus_final_design_rank"
    )


class AdvancedFeatureMetadata(ContractModel):
    variable_id: NonEmptyStr
    column: NonEmptyStr
    role: VariableRole
    timing: MeasurementTiming


class RuntimeDependency(ContractModel):
    name: NonEmptyStr
    version: NonEmptyStr


class AdvancedAdapterProvenance(ContractModel):
    adapter_id: NonEmptyStr
    adapter_version: Literal["1"] = "1"
    econml_version: NonEmptyStr
    estimator_class: NonEmptyStr
    estimator_configuration: tuple[NuisanceHyperparameter, ...]
    inference_mode: Literal["statsmodels_hc1"] = "statsmodels_hc1"
    estimand: Literal["ate", "cate"]
    treatment_type: Literal["binary"] = "binary"
    outcome_type: Literal["continuous"] = "continuous"
    nuisance_configuration: AdvancedEstimatorConfig
    seed: Annotated[int, Field(strict=True, ge=0)]
    random_state: Annotated[int, Field(strict=True, ge=0)]
    nuisance_seed: Annotated[int, Field(strict=True, ge=0)]
    fold_count: Annotated[int, Field(strict=True, ge=2)]
    fold_fingerprint_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    features: tuple[AdvancedFeatureMetadata, ...]
    python_version: NonEmptyStr
    platform: NonEmptyStr
    dependencies: tuple[RuntimeDependency, ...]
    determinism: Literal["numerical_repeatability_same_runtime"] = (
        "numerical_repeatability_same_runtime"
    )

    @model_validator(mode="after")
    def validate_configuration(self) -> Self:
        if self.seed != self.random_state or self.seed != self.nuisance_seed:
            raise ValueError("advanced adapter seeds must match the ExperimentOS seed")
        if self.nuisance_configuration.inference_mode != self.inference_mode:
            raise ValueError("inference provenance must match adapter configuration")
        return self


class AdvancedCausalResult(ContractModel):
    """Average-effect result with no baseline-specific variance claims or fitted state."""

    outcome_type: Literal["advanced_causal_effect"] = "advanced_causal_effect"
    schema_version: Literal["1"] = "1"
    configuration_fingerprint_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None
    method: Literal["partialling_out_dml"] = "partialling_out_dml"
    execution_request: DMLExecutionRequest
    configuration: AdvancedEstimatorConfig
    status: DMLStatus
    point_estimate: FiniteFloat | None = None
    inference: AdvancedInference | None = None
    sample_counts: DMLSampleCounts
    overlap: DMLOverlapDiagnostic | None = None
    nuisance_diagnostics: DMLNuisanceDiagnostics | None = None
    fold_plan: DMLFoldPlan | None = None
    fold_fits: tuple[DMLFoldFitProvenance, ...] = ()
    diagnostics: tuple[DMLDiagnostic, ...] = ()
    evidence_limitations: tuple[EvidenceLimitation, ...]
    adapter_provenance: AdvancedAdapterProvenance | None = None
    provenance: ProvenanceRecords
    abstention_reason: DMLAbstentionReason | None = None

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        if self.status is DMLStatus.COMPLETED:
            if (
                any(
                    value is None
                    for value in (
                        self.point_estimate,
                        self.inference,
                        self.overlap,
                        self.nuisance_diagnostics,
                        self.fold_plan,
                        self.adapter_provenance,
                    )
                )
                or not self.fold_fits
                or self.abstention_reason is not None
            ):
                raise ValueError("completed advanced results require uncertainty and fit evidence")
        elif (
            self.point_estimate is not None
            or self.inference is not None
            or self.abstention_reason is None
        ):
            raise ValueError(
                "non-completed advanced results must suppress estimates and give a reason"
            )
        return self
