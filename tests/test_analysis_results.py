from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from packages.experiments.analysis import (
    AbstainedAnalysisResult,
    AbstentionReason,
    AnalysisFailure,
    AnalysisOutcome,
    AnalysisStatus,
    CompletedAnalysisResult,
    EligibilityAssessment,
    FailedAnalysisResult,
    InconclusiveAnalysisResult,
)
from tests.analysis_contract_fixtures import abstained_result, randomized_estimate, source


def test_abstention_result_serializes_without_an_estimate_field() -> None:
    result = AbstainedAnalysisResult(
        outcome_type="abstained",
        status=AnalysisStatus.ABSTAINED,
        reason=AbstentionReason(
            code="covariate_timing_unknown",
            message="Causal adjustment is unsafe.",
            missing_or_invalid_information=("covariate timing",),
        ),
        diagnostics=(),
        warnings=(),
        provenance=(source(),),
    )
    payload = result.model_dump(mode="json")
    assert payload["status"] == "abstained"
    assert "findings" not in payload
    assert payload["reason"]["missing_or_invalid_information"] == ["covariate timing"]


def test_completed_result_rejects_inconclusive_child_status() -> None:
    with pytest.raises(ValidationError, match="finding status"):
        CompletedAnalysisResult(
            outcome_type="completed",
            status=AnalysisStatus.COMPLETED,
            findings=(randomized_estimate(analysis_status=AnalysisStatus.INCONCLUSIVE),),
            diagnostics=(),
            warnings=(),
            provenance=(source(),),
        )


def test_failed_result_requires_typed_failures_and_has_no_findings() -> None:
    with pytest.raises(ValidationError):
        FailedAnalysisResult(
            outcome_type="failed",
            status=AnalysisStatus.FAILED,
            failures=(),
            diagnostics=(),
            provenance=(source(),),
        )


def test_analysis_status_enum_contains_every_required_stable_value() -> None:
    assert [status.value for status in AnalysisStatus] == [
        "eligible",
        "eligible_with_warnings",
        "ineligible",
        "needs_more_data",
        "completed",
        "inconclusive",
        "abstained",
        "failed",
    ]


@pytest.mark.parametrize(
    "status",
    [
        AnalysisStatus.ELIGIBLE,
        AnalysisStatus.ELIGIBLE_WITH_WARNINGS,
        AnalysisStatus.INELIGIBLE,
        AnalysisStatus.NEEDS_MORE_DATA,
    ],
)
def test_eligibility_assessment_accepts_only_eligibility_states(
    status: AnalysisStatus,
) -> None:
    assessment = EligibilityAssessment(
        outcome_type="eligibility",
        status=status,
        diagnostics=(),
        warnings=(),
        required_data=(),
        provenance=(source(),),
    )
    assert assessment.status is status


def test_inconclusive_result_requires_inconclusive_findings() -> None:
    result = InconclusiveAnalysisResult(
        status=AnalysisStatus.INCONCLUSIVE,
        findings=(randomized_estimate(analysis_status=AnalysisStatus.INCONCLUSIVE),),
        diagnostics=(),
        warnings=(),
        provenance=(source(),),
    )
    assert result.findings[0].estimate.status is AnalysisStatus.INCONCLUSIVE


def test_terminal_outcomes_are_ready_for_discriminated_round_trips() -> None:
    completed = CompletedAnalysisResult(
        status=AnalysisStatus.COMPLETED,
        findings=(randomized_estimate(),),
        diagnostics=(),
        warnings=(),
        provenance=(source(),),
    )
    failed = FailedAnalysisResult(
        status=AnalysisStatus.FAILED,
        failures=(
            AnalysisFailure(
                code="analysis.execution",
                stage="analysis",
                message="The analysis could not complete.",
                retryable=True,
            ),
        ),
        diagnostics=(),
        provenance=(source(),),
    )
    adapter = TypeAdapter(AnalysisOutcome)
    for outcome in (completed, abstained_result(), failed):
        assert adapter.validate_python(outcome.model_dump(mode="json")) == outcome
