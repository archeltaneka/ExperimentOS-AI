"""Strict repository-owned contracts for Phase 4 statistical reference cases."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    StrictBool,
    StrictInt,
    model_validator,
)

type NonEmptyStr = Annotated[str, Field(strict=True, min_length=1)]
type ExpectedScalar = StrictBool | StrictInt | FiniteFloat | NonEmptyStr | None


class StatisticalCaseModel(BaseModel):
    """Frozen strict model used by repository-owned evaluation data."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class StatisticalCapability(StrEnum):
    ELIGIBILITY_VALIDATION = "eligibility_validation"
    DESCRIPTIVE_STATISTICS = "descriptive_statistics"
    RANDOMIZED_CONTINUOUS = "randomized_continuous"
    RANDOMIZED_BINARY = "randomized_binary"


class StatisticalCaseCategory(StrEnum):
    SUCCESSFUL_INFERENCE = "successful_inference"
    INVALID_INPUT = "invalid_input"
    ABSTENTION = "abstention"


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
    tolerance_rationale: NonEmptyStr | None = None
    tolerance_provenance: NonEmptyStr | None = None
    message: NonEmptyStr


class StatisticalCaseResult(StatisticalCaseModel):
    """Evaluation result for one reference case without raw source rows."""

    case_id: NonEmptyStr
    capability: StatisticalCapability
    category: StatisticalCaseCategory
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


class StatisticalTolerance(StatisticalCaseModel):
    """One independently justified absolute tolerance."""

    absolute: Annotated[FiniteFloat, Field(ge=0)]
    rationale: NonEmptyStr
    provenance: NonEmptyStr


class StatisticalExpectedValue(StatisticalCaseModel):
    """Expected leaf value addressed by a stable dotted result path."""

    path: NonEmptyStr
    value: ExpectedScalar
    tolerance: StatisticalTolerance | None = None

    @model_validator(mode="after")
    def require_float_tolerance(self) -> Self:
        if isinstance(self.value, float) and self.tolerance is None:
            raise ValueError("floating expected values require a tolerance")
        return self


class StatisticalReferenceCase(StatisticalCaseModel):
    """One deterministic Phase 4 capability input and independent expectation."""

    case_id: NonEmptyStr
    capability: StatisticalCapability
    category: StatisticalCaseCategory
    analysis_design: NonEmptyStr
    metric_type: NonEmptyStr
    fixture_id: NonEmptyStr
    expected_status: NonEmptyStr
    expected_method: NonEmptyStr | None = None
    expected_diagnostic_codes: tuple[NonEmptyStr, ...]
    expected_advisory_codes: tuple[NonEmptyStr, ...]
    expected_abstention: StrictBool
    expected_abstention_reason: NonEmptyStr | None
    expected_values: tuple[StatisticalExpectedValue, ...]
    notes: NonEmptyStr
    fixture_provenance: NonEmptyStr

    @model_validator(mode="after")
    def validate_expectation_shape(self) -> Self:
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
