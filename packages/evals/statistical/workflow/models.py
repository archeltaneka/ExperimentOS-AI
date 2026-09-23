"""Versioned workflow golden-case declarations; source rows never enter reports."""

from typing import Literal

from pydantic import Field, JsonValue

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


class AnalysisCheck(StatisticalCaseModel):
    code: str
    status: Literal["pass", "warning", "fail", "skipped"]
    method: str | None
    execution_status: str | None
    applicable: bool = True
