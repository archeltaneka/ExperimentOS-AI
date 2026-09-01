"""Reference behavior for observational identification reliability cases."""

from __future__ import annotations

import pytest

from packages.evals.statistical.observational_fixtures import run_identification_fixture
from packages.experiments.analysis.causal import IdentificationStatus


@pytest.mark.parametrize(
    ("fixture_id", "estimand"),
    [
        ("identification_ate_identified", "ate"),
        ("identification_att_identified", "att"),
    ],
)
def test_identified_reference_preserves_estimand_and_declared_assumptions(
    fixture_id: str,
    estimand: str,
) -> None:
    result = run_identification_fixture(fixture_id)

    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.estimand is not None
    assert result.estimand.estimand_type.value == estimand
    assert result.estimand.target_population.kind.value == (
        "full" if estimand == "ate" else "treated"
    )
    assert len(result.assumptions) == 7
    assert {item.status.value for item in result.assumptions} == {"asserted"}
    assert result.evidence_limitations
    assert result.abstention_reason is None


@pytest.mark.parametrize(
    ("fixture_id", "status", "diagnostic_code"),
    [
        (
            "identification_post_treatment_adjustment",
            IdentificationStatus.INVALID,
            "adjustment.post_treatment",
        ),
        (
            "identification_treatment_leakage",
            IdentificationStatus.INVALID,
            "adjustment.treatment_leakage",
        ),
        (
            "identification_outcome_leakage",
            IdentificationStatus.INVALID,
            "adjustment.outcome_leakage",
        ),
        (
            "identification_post_treatment_modifier",
            IdentificationStatus.INVALID,
            "effect_modifier.post_treatment",
        ),
        (
            "identification_missing_estimand",
            IdentificationStatus.INSUFFICIENT_EVIDENCE,
            "identification.missing_estimand",
        ),
        (
            "identification_missing_assumptions",
            IdentificationStatus.INSUFFICIENT_EVIDENCE,
            "assumption.missing_required",
        ),
        (
            "identification_insufficient_evidence",
            IdentificationStatus.INSUFFICIENT_EVIDENCE,
            "identification.missing_adjustment_information",
        ),
        (
            "identification_contradictory_timing",
            IdentificationStatus.INVALID,
            "time.reversed",
        ),
        (
            "identification_unsupported_design",
            IdentificationStatus.UNSUPPORTED,
            "design.unsupported",
        ),
        (
            "identification_unverified_assumption",
            IdentificationStatus.PARTIALLY_IDENTIFIED,
            "assumption.unverified",
        ),
    ],
)
def test_invalid_or_insufficient_identification_abstains_with_expected_diagnostic(
    fixture_id: str,
    status: IdentificationStatus,
    diagnostic_code: str,
) -> None:
    result = run_identification_fixture(fixture_id)

    assert result.status is status
    assert diagnostic_code in {item.code.value for item in result.diagnostics}
    assert result.abstention_reason is not None


def test_identification_fixture_is_deterministic() -> None:
    first = run_identification_fixture("identification_ate_identified")
    repeated = run_identification_fixture("identification_ate_identified")

    assert first.model_dump(mode="json") == repeated.model_dump(mode="json")
