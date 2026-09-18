"""ExperimentOS-owned contracts for optional DoWhy evidence."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from ...base import ContractModel, FiniteFloat, NonEmptyStr
from ...provenance import ProvenanceRecords
from ..models import IdentificationResult


class DoWhyOperationStatus(StrEnum):
    COMPLETED = "completed"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    UNSUPPORTED = "unsupported"
    ERROR = "error"


class DoWhyRefuterStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    ABSTAINED = "abstained"
    UNSUPPORTED = "unsupported"
    ERROR = "error"


class DoWhyRefuterMethod(StrEnum):
    PLACEBO = "placebo_treatment_refuter"
    RANDOM_COMMON_CAUSE = "random_common_cause"
    DATA_SUBSET = "data_subset_refuter"


class DoWhyFailureCode(StrEnum):
    OPTIONAL_DEPENDENCY_UNAVAILABLE = "OPTIONAL_DEPENDENCY_UNAVAILABLE"
    INCOMPATIBLE_DEPENDENCY_RUNTIME = "INCOMPATIBLE_DEPENDENCY_RUNTIME"
    INVALID_IDENTIFICATION = "INVALID_IDENTIFICATION"
    INVALID_GRAPH = "INVALID_GRAPH"
    UNSUPPORTED_ESTIMAND = "UNSUPPORTED_ESTIMAND"
    INVALID_DATA = "INVALID_DATA"
    MODEL_CONSTRUCTION_FAILURE = "MODEL_CONSTRUCTION_FAILURE"
    IDENTIFICATION_FAILURE = "IDENTIFICATION_FAILURE"
    IDENTIFICATION_UNAVAILABLE = "IDENTIFICATION_UNAVAILABLE"
    ESTIMATION_FAILURE = "ESTIMATION_FAILURE"
    REFUTER_FAILURE = "REFUTER_FAILURE"
    NONFINITE_ESTIMATE = "NONFINITE_ESTIMATE"
    MALFORMED_DOWHY_RESULT = "MALFORMED_DOWHY_RESULT"


class DoWhyConfig(ContractModel):
    """Bounded adapter configuration; never a raw DoWhy argument mapping."""

    run_estimation: bool = False
    seed: Annotated[int, Field(strict=True, ge=0)] = 105
    num_simulations: Annotated[int, Field(strict=True, gt=0, le=1000)] = 20
    subset_fraction: Annotated[float, Field(strict=True, gt=0.0, lt=1.0)] = 0.8
    refuters: tuple[DoWhyRefuterMethod, ...] = ()

    @field_validator("refuters")
    @classmethod
    def canonicalize_refuters(
        cls, value: tuple[DoWhyRefuterMethod, ...]
    ) -> tuple[DoWhyRefuterMethod, ...]:
        if len(value) != len(set(value)):
            raise ValueError("refuter methods must be unique")
        order = {method: index for index, method in enumerate(DoWhyRefuterMethod)}
        return tuple(sorted(value, key=order.__getitem__))


class DoWhyCovariateBinding(ContractModel):
    variable_id: NonEmptyStr
    column: NonEmptyStr


class DoWhyDataBinding(ContractModel):
    treatment_column: NonEmptyStr
    outcome_column: NonEmptyStr
    covariates: tuple[DoWhyCovariateBinding, ...]


class DoWhyExecutionRequest(ContractModel):
    identification_result: IdentificationResult
    binding: DoWhyDataBinding
    configuration: DoWhyConfig = DoWhyConfig()


class DoWhyDiagnostic(ContractModel):
    code: NonEmptyStr
    message: NonEmptyStr


class DoWhyAbstentionReason(ContractModel):
    code: DoWhyFailureCode
    message: NonEmptyStr


class DoWhyIdentificationEvidence(ContractModel):
    status: DoWhyOperationStatus
    method: Literal["default_backdoor"]
    adjustment_set: tuple[NonEmptyStr, ...]
    graph_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    interpretation: NonEmptyStr

    @field_validator("adjustment_set")
    @classmethod
    def canonicalize_adjustment(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(value))


class DoWhyEstimateEvidence(ContractModel):
    method: Literal["backdoor.linear_regression"] = "backdoor.linear_regression"
    point_estimate: FiniteFloat
    adjustment_set: tuple[NonEmptyStr, ...]


class DoWhyRefutationResult(ContractModel):
    method: DoWhyRefuterMethod
    status: DoWhyRefuterStatus
    seed: Annotated[int, Field(strict=True, ge=0)]
    num_simulations: Annotated[int, Field(strict=True, gt=0)]
    subset_fraction: float | None = None
    original_estimate: FiniteFloat | None = None
    new_estimate: FiniteFloat | None = None
    delta: FiniteFloat | None = None
    p_value: Annotated[float, Field(strict=True, ge=0, le=1)] | None = None
    interpretation: NonEmptyStr


class DoWhyAdapterProvenance(ContractModel):
    adapter_id: Literal["experimentos_dowhy"] = "experimentos_dowhy"
    adapter_version: Literal["1"] = "1"
    dowhy_version: NonEmptyStr
    python_version: NonEmptyStr
    graph_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    identification_method: Literal["default_backdoor"] = "default_backdoor"
    estimator_method: NonEmptyStr | None = None


class DoWhyAnalysisResult(ContractModel):
    outcome_type: Literal["dowhy_causal_evidence"] = "dowhy_causal_evidence"
    configuration_fingerprint_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None
    execution_request: DoWhyExecutionRequest
    status: DoWhyOperationStatus
    identification: DoWhyIdentificationEvidence
    estimate: DoWhyEstimateEvidence | None = None
    refutations: tuple[DoWhyRefutationResult, ...] = ()
    diagnostics: tuple[DoWhyDiagnostic, ...] = ()
    adapter_provenance: DoWhyAdapterProvenance | None = None
    provenance: ProvenanceRecords
    abstention_reason: DoWhyAbstentionReason | None = None

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        if self.status is DoWhyOperationStatus.COMPLETED:
            if self.abstention_reason is not None or self.adapter_provenance is None:
                raise ValueError("completed results require provenance and no abstention")
        elif self.estimate is not None or self.abstention_reason is None:
            raise ValueError("non-completed results must suppress estimates and explain abstention")
        return self


__all__ = [
    "DoWhyConfig",
    "DoWhyAbstentionReason",
    "DoWhyAdapterProvenance",
    "DoWhyAnalysisResult",
    "DoWhyCovariateBinding",
    "DoWhyDataBinding",
    "DoWhyDiagnostic",
    "DoWhyEstimateEvidence",
    "DoWhyExecutionRequest",
    "DoWhyFailureCode",
    "DoWhyIdentificationEvidence",
    "DoWhyOperationStatus",
    "DoWhyRefuterMethod",
    "DoWhyRefuterStatus",
    "DoWhyRefutationResult",
]
