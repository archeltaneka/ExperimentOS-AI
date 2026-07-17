from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from packages.experiments.analysis import (
    ConfidenceInterval,
    CredibleInterval,
    Diagnostic,
    DiagnosticOutcome,
    DiagnosticSeverity,
    PosteriorProbability,
    ProvenanceRecord,
    ProvenanceRecords,
    ProvenanceSourceType,
    StandardError,
    UncertaintyBundle,
    UncertaintyUnavailable,
)


@pytest.mark.parametrize(("lower", "upper"), [(2.0, 1.0), (float("nan"), 1.0)])
def test_interval_rejects_invalid_bounds(lower: float, upper: float) -> None:
    with pytest.raises(ValidationError):
        ConfidenceInterval(lower=lower, upper=upper, confidence_level=0.95)


@pytest.mark.parametrize("level", [0.0, 1.0, -0.1, 1.1])
def test_confidence_and_credible_intervals_reject_invalid_levels(level: float) -> None:
    with pytest.raises(ValidationError):
        ConfidenceInterval(lower=0.0, upper=1.0, confidence_level=level)
    with pytest.raises(ValidationError):
        CredibleInterval(lower=0.0, upper=1.0, credible_level=level)


def test_uncertainty_unavailable_cannot_mix_with_numeric_uncertainty() -> None:
    with pytest.raises(ValidationError, match="cannot coexist"):
        UncertaintyBundle(
            measures=(
                StandardError(value=0.02),
                UncertaintyUnavailable(reason="raw samples unavailable"),
            )
        )


def test_standard_error_and_posterior_probability_reject_invalid_values() -> None:
    with pytest.raises(ValidationError):
        StandardError(value=-0.01)
    with pytest.raises(ValidationError):
        PosteriorProbability(probability=1.01, event="treatment effect is positive")


def test_uncertainty_variants_have_stable_semantic_discriminators() -> None:
    measures = (
        StandardError(value=0.02),
        ConfidenceInterval(lower=0.0, upper=0.1, confidence_level=0.95),
        CredibleInterval(lower=0.01, upper=0.09, credible_level=0.9),
        PosteriorProbability(probability=0.98, event="treatment effect is positive"),
    )

    assert [measure.model_dump(mode="json")["kind"] for measure in measures] == [
        "standard_error",
        "confidence_interval",
        "credible_interval",
        "posterior_probability",
    ]
    assert UncertaintyUnavailable(reason="raw samples unavailable").kind == "unavailable"


def test_uncertainty_bundle_requires_at_least_one_measure() -> None:
    with pytest.raises(ValidationError):
        UncertaintyBundle(measures=())


def test_provenance_requires_typed_non_empty_records_and_aware_timestamps() -> None:
    record = ProvenanceRecord(
        source_type=ProvenanceSourceType.EXPERIMENT_DATA,
        source_id="exp-001-payment-recommendation",
        observed_at=datetime(2026, 7, 15, tzinfo=UTC),
    )
    assert TypeAdapter(ProvenanceRecords).validate_python((record,)) == (record,)

    with pytest.raises(ValidationError):
        TypeAdapter(ProvenanceRecords).validate_python(())
    with pytest.raises(ValidationError, match="timezone-aware"):
        ProvenanceRecord(
            source_type=ProvenanceSourceType.EXPERIMENT_DATA,
            source_id="exp-001-payment-recommendation",
            observed_at=datetime(2026, 7, 15),
        )


def test_diagnostic_serializes_with_stable_enum_values() -> None:
    diagnostic = Diagnostic(
        code="overlap.low",
        severity=DiagnosticSeverity.WARNING,
        outcome=DiagnosticOutcome.FAILED,
        message="Observed overlap is below the planned threshold.",
    )
    assert diagnostic.model_dump(mode="json") == {
        "code": "overlap.low",
        "severity": "warning",
        "outcome": "failed",
        "message": "Observed overlap is below the planned threshold.",
        "observed_value": None,
        "threshold": None,
    }
