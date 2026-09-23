"""Versioned workflow golden-case declarations; source rows never enter reports."""

from typing import Literal

from pydantic import Field, FiniteFloat, JsonValue

from ..reference_values import NonEmptyStr, StatisticalCaseModel, StatisticalExpectedValue


class WorkflowExpectations(StatisticalCaseModel):
    numerical: tuple[StatisticalExpectedValue, ...] = ()
    required_paths: tuple[NonEmptyStr, ...] = ()
    forbidden_paths: tuple[NonEmptyStr, ...] = ()
    diagnostic_codes: tuple[NonEmptyStr, ...] = ()
    assumption_codes: tuple[NonEmptyStr, ...] = ()
    business_status: NonEmptyStr | None = None
    policy_rule_ids: tuple[NonEmptyStr, ...] = ()
    forbidden_calls: tuple[NonEmptyStr, ...] = ()


class AnalysisWorkflowCase(StatisticalCaseModel):
    case_id: NonEmptyStr
    case_version: Literal["1"] = "1"
    family: NonEmptyStr = "workflow"
    design: NonEmptyStr = "unspecified"
    estimand: NonEmptyStr = "not_applicable"
    fixture_id: NonEmptyStr = "workflow_analysis"
    ask_payload: dict[str, JsonValue]
    expected_method: str | None
    expected_status: Literal[
        "completed", "inconclusive", "invalid", "abstained", "unavailable", "failed"
    ]
    expectations: WorkflowExpectations = Field(default_factory=WorkflowExpectations)
    presenter_candidate: str | None = None
    optional_unavailable: bool = False
    optional_scenario: Literal["broken"] | None = None


class AnalysisCheck(StatisticalCaseModel):
    code: str
    status: Literal["pass", "warning", "fail", "skipped"]
    method: str | None
    execution_status: str | None
    applicable: bool = True
    rule_id: str = ""
    case_id: str = ""
    diagnostic_evidence: tuple[str, ...] = ()
    expected: str | int | FiniteFloat | bool | None = None
    actual: str | int | FiniteFloat | bool | None = None


class WorkflowCaseResult(StatisticalCaseModel):
    case_id: NonEmptyStr
    case_version: NonEmptyStr
    family: NonEmptyStr
    method: str | None
    design: NonEmptyStr
    estimand: NonEmptyStr
    execution_status: NonEmptyStr
    native_status: str | None = None
    checks: dict[str, AnalysisCheck]
    evidence: dict[str, JsonValue] | None = None
    business_evidence: dict[str, JsonValue] | None = None
    duration_ms: FiniteFloat = Field(ge=0)
    dependency_state: str = "not_required"
    dependency_version: str | None = None
    execution_kind: str = "real"
    trace_summary: tuple[dict[str, JsonValue], ...] = ()
    call_counts: dict[str, int] = Field(default_factory=dict)
    detected_rule_ids: tuple[str, ...] = ()
    injection_detected: bool | None = None
