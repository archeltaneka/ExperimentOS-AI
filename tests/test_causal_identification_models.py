from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.experiments.analysis import DiagnosticSeverity
from packages.experiments.analysis.causal import (
    AssumptionApplicability,
    AssumptionTestability,
    CausalAbstentionReason,
    CausalAssumption,
    CausalAssumptionCode,
    CausalAssumptionStatus,
    CausalDiagnostic,
    CausalDiagnosticCategory,
    CausalDiagnosticCode,
    CausalDiagnosticStatus,
    EvidenceLimitation,
    EvidenceLimitationCode,
    IdentificationResult,
    IdentificationStatus,
)
from tests.causal_identification_fixtures import assumptions, provenance, request


def test_assumption_status_vocabulary_distinguishes_assertion_from_support() -> None:
    assert [status.value for status in CausalAssumptionStatus] == [
        "asserted",
        "supported_by_diagnostics",
        "violated",
        "unverified",
        "not_applicable",
    ]


def test_exchangeability_cannot_claim_diagnostic_support_as_proof() -> None:
    with pytest.raises(ValidationError, match="not fully testable"):
        CausalAssumption(
            code=CausalAssumptionCode.EXCHANGEABILITY,
            description="No unmeasured confounding.",
            applicability=AssumptionApplicability.REQUIRED,
            status=CausalAssumptionStatus.SUPPORTED_BY_DIAGNOSTICS,
            testability=AssumptionTestability.FULLY_TESTABLE,
            evidence=provenance("balance-diagnostic"),
            diagnostic_references=("balance.passed",),
            limitations=(),
        )


def test_not_applicable_assumption_requires_matching_applicability() -> None:
    with pytest.raises(ValidationError, match="not_applicable"):
        assumptions()[0].model_copy(
            update={"status": CausalAssumptionStatus.NOT_APPLICABLE}
        ).model_validate(
            assumptions()[0].model_copy(update={"status": CausalAssumptionStatus.NOT_APPLICABLE})
        )


def test_diagnostic_context_and_limitation_references_are_canonical() -> None:
    diagnostic = CausalDiagnostic(
        code=CausalDiagnosticCode.POST_TREATMENT_ADJUSTMENT,
        category=CausalDiagnosticCategory.TIMING,
        severity=DiagnosticSeverity.FATAL,
        status=CausalDiagnosticStatus.FAILED,
        message="Post-treatment adjustment is invalid.",
        context={"variable_id": "prior_orders", "timing": "post_treatment"},
    )
    limitation = EvidenceLimitation(
        code=EvidenceLimitationCode.UNMEASURED_CONFOUNDING_POSSIBLE,
        description="Unmeasured confounding remains possible.",
        assumption_codes=(
            CausalAssumptionCode.POSITIVITY,
            CausalAssumptionCode.EXCHANGEABILITY,
        ),
        provenance=provenance("limitation"),
    )

    assert tuple(entry.key for entry in diagnostic.context) == ("timing", "variable_id")
    assert limitation.assumption_codes == (
        CausalAssumptionCode.EXCHANGEABILITY,
        CausalAssumptionCode.POSITIVITY,
    )


def test_non_identified_result_requires_abstention() -> None:
    identified = request()
    payload = {
        "request_id": identified.request_id,
        "identification_request": identified.identification,
        "status": IdentificationStatus.INSUFFICIENT_EVIDENCE,
        "diagnostics": (),
        "warnings": (),
        "evidence_limitations": (),
        "provenance": provenance("result"),
    }
    with pytest.raises(ValidationError, match="abstention"):
        IdentificationResult(**payload)

    payload["abstention_reason"] = CausalAbstentionReason(
        code=CausalDiagnosticCode.INSUFFICIENT_IDENTIFICATION_EVIDENCE,
        message="Required evidence is missing.",
        missing_or_invalid_information=("adjustment_set",),
    )
    result = IdentificationResult(**payload)
    assert result.status is IdentificationStatus.INSUFFICIENT_EVIDENCE
