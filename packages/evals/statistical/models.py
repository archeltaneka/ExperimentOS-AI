"""Strict repository-owned contracts for Phase 4 statistical reference cases."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import (
    Field,
    FiniteFloat,
    StrictBool,
    StrictInt,
    model_validator,
)

from .advanced.models import AdvancedCaseDetails, AdvancedResultDetails
from .reference_values import (
    ExpectedScalar,
    NonEmptyStr,
    StatisticalCaseModel,
    StatisticalExpectedValue,
    StatisticalTolerance,
)


def _default_deterministic_configuration() -> dict[NonEmptyStr, ExpectedScalar]:
    return {"execution_mode": "offline_deterministic"}


class StatisticalCapability(StrEnum):
    REPOSITORY_DML = "repository_dml"
    REPOSITORY_HTE = "repository_hte"
    ECONML_DML = "econml_dml"
    ECONML_HTE = "econml_hte"
    DOWHY_IDENTIFICATION = "dowhy_identification"
    DOWHY_ESTIMATION = "dowhy_estimation"
    DOWHY_PLACEBO = "dowhy_placebo"
    DOWHY_COMMON_CAUSE = "dowhy_common_cause"
    DOWHY_SUBSET = "dowhy_subset"
    CAUSAL_IDENTIFICATION = "causal_identification"
    ELIGIBILITY_VALIDATION = "eligibility_validation"
    DESCRIPTIVE_STATISTICS = "descriptive_statistics"
    DIFFERENCE_IN_DIFFERENCES = "difference_in_differences"
    PROPENSITY_SCORE = "propensity_score"
    IPW_ATE = "ipw_ate"
    IPW_ATT = "ipw_att"
    OBSERVATIONAL_COVERAGE = "observational_coverage"
    RANDOMIZED_CONTINUOUS = "randomized_continuous"
    RANDOMIZED_BINARY = "randomized_binary"
    CUPED = "cuped"
    SEQUENTIAL = "sequential"
    BAYESIAN_BINARY = "bayesian_binary"
    BAYESIAN_CONTINUOUS = "bayesian_continuous"


class StatisticalCaseCategory(StrEnum):
    SUCCESSFUL_INFERENCE = "successful_inference"
    INVALID_INPUT = "invalid_input"
    ABSTENTION = "abstention"
    SKIPPED = "skipped"


class CheckStatus(StrEnum):
    PASS = "pass"
    ADVISORY = "advisory"
    FAIL = "fail"
    SKIPPED = "skipped"


class StatisticalCheck(StatisticalCaseModel):
    """One structured reliability assertion and its policy-facing rule identity."""

    check_id: NonEmptyStr
    rule_id: NonEmptyStr
    dimension: NonEmptyStr
    status: CheckStatus
    expected: Any = None
    actual: Any = None
    delta: FiniteFloat | None = None
    tolerance: Annotated[FiniteFloat, Field(ge=0)] | None = None
    relative_tolerance: Annotated[FiniteFloat, Field(ge=0)] | None = None
    tolerance_rationale: NonEmptyStr | None = None
    tolerance_provenance: NonEmptyStr | None = None
    message: NonEmptyStr


class StatisticalCaseResult(StatisticalCaseModel):
    """Evaluation result for one reference case without raw source rows."""

    case_id: NonEmptyStr
    advanced: AdvancedResultDetails | None = None
    capability: StatisticalCapability
    category: StatisticalCaseCategory
    design: NonEmptyStr = "unspecified"
    estimand: NonEmptyStr = "not_applicable"
    method: NonEmptyStr = "unspecified"
    target_population: NonEmptyStr = "not_applicable"
    reference_result: dict[NonEmptyStr, Any] = Field(default_factory=dict)
    tolerances: dict[NonEmptyStr, FiniteFloat] = Field(default_factory=dict)
    simulation_metadata: dict[NonEmptyStr, Any] | None = None
    expected_status: NonEmptyStr
    actual_status: NonEmptyStr
    evaluation_status: CheckStatus
    passed: StrictBool
    checks: tuple[StatisticalCheck, ...]
    diagnostic_codes: tuple[NonEmptyStr, ...]
    advisory_codes: tuple[NonEmptyStr, ...]
    blocking_findings: tuple[NonEmptyStr, ...]
    advisory_findings: tuple[NonEmptyStr, ...]
    skipped_checks: tuple[NonEmptyStr, ...]
    skip_reasons: tuple[NonEmptyStr, ...]
    duration_ms: Annotated[FiniteFloat, Field(ge=0)]
    determinism_passed: StrictBool


class StatisticalCapabilityResult(StatisticalCaseModel):
    capability: StatisticalCapability
    cases: Annotated[int, Field(strict=True, ge=0)]
    passed: Annotated[int, Field(strict=True, ge=0)]
    failed: Annotated[int, Field(strict=True, ge=0)]
    advisory: Annotated[int, Field(strict=True, ge=0)]


class StatisticalPolicyRuleResult(StatisticalCaseModel):
    rule_id: NonEmptyStr
    category: NonEmptyStr
    severity: NonEmptyStr
    status: NonEmptyStr
    observed_value: Any = None
    operator: NonEmptyStr
    threshold_value: Any
    required: StrictBool
    message: NonEmptyStr
    method: NonEmptyStr
    design: NonEmptyStr = "aggregate"
    estimand: NonEmptyStr = "aggregate"
    case_id: NonEmptyStr
    expected_value: Any = None
    actual_value: Any = None
    diagnostic_evidence: tuple[NonEmptyStr, ...] = ()


class StatisticalPolicySummary(StatisticalCaseModel):
    policy_version: NonEmptyStr
    overall_status: NonEmptyStr
    blocking_rule_ids: tuple[NonEmptyStr, ...]
    advisory_rule_ids: tuple[NonEmptyStr, ...]
    skipped_rule_ids: tuple[NonEmptyStr, ...]
    rules: tuple[StatisticalPolicyRuleResult, ...]


class StatisticalBaselineReport(StatisticalCaseModel):
    """Authoritative deterministic aggregate Phase 4 reliability result."""

    schema_version: NonEmptyStr = "1"
    baseline_id: NonEmptyStr
    baseline_version: NonEmptyStr
    fixture_provenance: NonEmptyStr
    policy_version: NonEmptyStr
    offline_provider_statement: NonEmptyStr
    dataset_size: Annotated[int, Field(strict=True, ge=0)]
    cases_passed: Annotated[int, Field(strict=True, ge=0)]
    cases_failed: Annotated[int, Field(strict=True, ge=0)]
    cases_advisory: Annotated[int, Field(strict=True, ge=0)]
    cases_invalid: Annotated[int, Field(strict=True, ge=0)]
    cases_abstained: Annotated[int, Field(strict=True, ge=0)]
    cases_skipped: Annotated[int, Field(strict=True, ge=0)]
    overall_status: NonEmptyStr
    capability_results: tuple[StatisticalCapabilityResult, ...]
    case_results: tuple[StatisticalCaseResult, ...]
    quality_policy: StatisticalPolicySummary | None = None
    limitations: tuple[NonEmptyStr, ...]


class ObservationalSimulationSpecification(StatisticalCaseModel):
    """Complete versioned configuration for one deterministic observational DGP."""

    dgp_name: NonEmptyStr
    dgp_version: NonEmptyStr
    seed: StrictInt
    sample_size: Annotated[StrictInt, Field(gt=0)]
    treatment_assignment: NonEmptyStr
    confounders: Annotated[tuple[NonEmptyStr, ...], Field(min_length=1)]
    outcome_formula: NonEmptyStr
    true_causal_effect: FiniteFloat
    estimand: NonEmptyStr
    repetitions: Annotated[StrictInt, Field(gt=0)]
    model_configuration: dict[NonEmptyStr, ExpectedScalar]
    coverage_lower: Annotated[FiniteFloat, Field(ge=0, le=1)]
    coverage_upper: Annotated[FiniteFloat, Field(ge=0, le=1)]
    tolerance: Annotated[FiniteFloat, Field(ge=0)]

    @model_validator(mode="after")
    def validate_configuration(self) -> Self:
        if not self.model_configuration:
            raise ValueError("simulation model configuration must not be empty")
        if self.coverage_lower > self.coverage_upper:
            raise ValueError("simulation coverage bounds must be ordered")
        return self


class ObservationalCoverageResult(StatisticalCaseModel):
    """Aggregate-only result of a deterministic repeated observational DGP."""

    status: NonEmptyStr = "completed"
    method: NonEmptyStr
    estimand: NonEmptyStr
    true_effect: FiniteFloat
    repetitions: Annotated[StrictInt, Field(gt=0)]
    completed_repetitions: Annotated[StrictInt, Field(ge=0)]
    intervals_containing: Annotated[StrictInt, Field(ge=0)]
    interval_coverage: Annotated[FiniteFloat, Field(ge=0, le=1)]
    mean_estimate: FiniteFloat
    coverage_status: NonEmptyStr
    simulation: ObservationalSimulationSpecification

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.completed_repetitions != self.repetitions:
            raise ValueError("coverage simulation requires every repetition to complete")
        if self.intervals_containing > self.completed_repetitions:
            raise ValueError("coverage count cannot exceed completed repetitions")
        return self


class StatisticalReferenceCase(StatisticalCaseModel):
    """One deterministic Phase 4 capability input and independent expectation."""

    case_id: NonEmptyStr
    advanced: AdvancedCaseDetails | None = None
    capability: StatisticalCapability
    category: StatisticalCaseCategory
    method: NonEmptyStr = "fixed_horizon_ab"
    analysis_design: NonEmptyStr
    estimand: NonEmptyStr = "not_applicable"
    target_population: NonEmptyStr = "not_applicable"
    metric_type: NonEmptyStr
    fixture_id: NonEmptyStr
    expected_status: NonEmptyStr
    expected_method: NonEmptyStr | None = None
    expected_diagnostic_codes: tuple[NonEmptyStr, ...]
    expected_advisory_codes: tuple[NonEmptyStr, ...]
    expected_abstention: StrictBool
    expected_abstention_reason: NonEmptyStr | None
    expected_values: tuple[StatisticalExpectedValue, ...]
    expected_assumption_codes: tuple[NonEmptyStr, ...] = ()
    expected_uncertainty_fields: tuple[NonEmptyStr, ...] = ()
    deterministic_configuration: dict[NonEmptyStr, ExpectedScalar] = Field(
        default_factory=_default_deterministic_configuration
    )
    simulation: ObservationalSimulationSpecification | None = None
    reference_provenance: NonEmptyStr | None = None
    notes: NonEmptyStr
    fixture_provenance: NonEmptyStr

    @model_validator(mode="after")
    def validate_expectation_shape(self) -> Self:
        from .advanced.registry import REGISTRY

        is_advanced = self.capability.value in REGISTRY
        if is_advanced != (self.advanced is not None):
            raise ValueError("advanced capabilities require explicit conformance metadata")
        if self.advanced is not None:
            capability = REGISTRY[self.capability.value]
            if (
                self.advanced.capability_id != self.capability.value
                or self.method != capability.method
                or self.advanced.uncertainty != capability.uncertainty
            ):
                raise ValueError("advanced case metadata contradicts capability registry")
        if self.expected_abstention != (self.expected_abstention_reason is not None):
            raise ValueError(
                "expected_abstention and expected_abstention_reason must be declared together"
            )
        paths = tuple(item.path for item in self.expected_values)
        if len(paths) != len(set(paths)):
            raise ValueError("expected value paths must be unique within a case")
        if tuple(sorted(self.expected_diagnostic_codes)) != self.expected_diagnostic_codes:
            raise ValueError("expected diagnostic codes must use deterministic sorted order")
        if tuple(sorted(self.expected_advisory_codes)) != self.expected_advisory_codes:
            raise ValueError("expected advisory codes must use deterministic sorted order")
        object.__setattr__(
            self, "expected_assumption_codes", tuple(sorted(self.expected_assumption_codes))
        )
        object.__setattr__(
            self, "expected_uncertainty_fields", tuple(sorted(self.expected_uncertainty_fields))
        )
        if not self.deterministic_configuration:
            raise ValueError("deterministic configuration must not be empty")
        if (
            self.capability is StatisticalCapability.OBSERVATIONAL_COVERAGE
            and self.simulation is None
        ):
            raise ValueError("observational coverage cases require simulation metadata")
        if (
            self.capability is not StatisticalCapability.OBSERVATIONAL_COVERAGE
            and self.simulation is not None
        ):
            raise ValueError("only observational coverage cases may declare simulation metadata")
        if self.reference_provenance is None:
            object.__setattr__(self, "reference_provenance", self.fixture_provenance)
        return self


class StatisticalReferenceDataset(StatisticalCaseModel):
    """Versioned deterministic inventory for the statistical reliability baseline."""

    baseline_id: NonEmptyStr
    version: NonEmptyStr
    fixture_provenance: NonEmptyStr
    cases: tuple[StatisticalReferenceCase, ...]

    @model_validator(mode="after")
    def validate_cases(self) -> Self:
        if not self.cases:
            raise ValueError("statistical reference dataset requires at least one case")
        case_ids = tuple(case.case_id for case in self.cases)
        seen: set[str] = set()
        for case_id in case_ids:
            if case_id in seen:
                raise ValueError(f"duplicate statistical case_id: {case_id}")
            seen.add(case_id)
        if case_ids != tuple(sorted(case_ids)):
            raise ValueError("statistical reference cases must be sorted by case_id")
        if any(case.fixture_provenance != self.fixture_provenance for case in self.cases):
            raise ValueError("case fixture provenance must match the dataset")
        return self


__all__ = [
    "CheckStatus",
    "ObservationalSimulationSpecification",
    "ObservationalCoverageResult",
    "StatisticalBaselineReport",
    "StatisticalCapability",
    "StatisticalCapabilityResult",
    "StatisticalCaseResult",
    "StatisticalCaseCategory",
    "StatisticalCheck",
    "StatisticalPolicyRuleResult",
    "StatisticalPolicySummary",
    "StatisticalExpectedValue",
    "StatisticalReferenceCase",
    "StatisticalReferenceDataset",
    "StatisticalTolerance",
]
