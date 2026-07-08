from __future__ import annotations

from packages.agents.tools import (
    execute_tool,
    get_tool,
    list_tools,
    score_decision_confidence,
)
from packages.agents.tools.decision import DecisionConfidenceInput


def test_registry_lookup_returns_registered_tool() -> None:
    tool = get_tool("calculate_absolute_lift")

    assert tool.name == "calculate_absolute_lift"


def test_list_tools_returns_registered_tools_in_sorted_order() -> None:
    assert list_tools() == [
        "calculate_absolute_lift",
        "calculate_relative_lift",
        "score_decision_confidence",
        "score_experiment_risk",
        "validate_required_evidence",
    ]


def test_calculate_absolute_lift_returns_expected_delta() -> None:
    execution = execute_tool(
        "calculate_absolute_lift",
        {"baseline_value": 0.676, "treatment_value": 0.731},
        node="business_impact",
    )

    assert execution.output is not None
    assert execution.output.absolute_lift == 0.055
    assert execution.record["status"] == "completed"


def test_calculate_relative_lift_handles_zero_baseline_without_crashing() -> None:
    execution = execute_tool(
        "calculate_relative_lift",
        {"baseline_value": 0.0, "absolute_lift": 0.2},
        node="business_impact",
    )

    assert execution.output is not None
    assert execution.output.relative_lift is None
    assert execution.output.status == "undefined_zero_baseline"
    assert execution.record["status"] == "completed"


def test_score_experiment_risk_returns_score_and_level() -> None:
    execution = execute_tool(
        "score_experiment_risk",
        {
            "risk_factors": [
                {"severity": "medium"},
                {"severity": "high"},
            ]
        },
        node="risk_assessment",
    )

    assert execution.output is not None
    assert execution.output.risk_score == 5
    assert execution.output.overall_risk_level == "high"


def test_validate_required_evidence_identifies_missing_requirements() -> None:
    execution = execute_tool(
        "validate_required_evidence",
        {
            "has_experiment_analysis": False,
            "has_business_impact": False,
            "has_risk_assessment": True,
            "has_statistical_significance": False,
            "citation_count": 0,
        },
        node="decision",
    )

    assert execution.output is not None
    assert execution.output.is_valid is False
    assert "experiment_analysis" in execution.output.missing_requirements


def test_execute_tool_records_structured_failure_for_invalid_payload() -> None:
    execution = execute_tool(
        "calculate_absolute_lift",
        {"baseline_value": "bad", "treatment_value": 0.731},
        node="business_impact",
    )

    assert execution.output is None
    assert execution.record["status"] == "failed"
    assert execution.record["error"]


def test_score_decision_confidence_returns_high_when_inputs_support_it() -> None:
    result = score_decision_confidence(
        DecisionConfidenceInput(
            analysis_confidence="high",
            business_confidence="high",
            risk_confidence="high",
            overall_risk_level="low",
            has_statistical_support=True,
            has_citations=True,
        )
    )

    assert result.confidence == "high"
