from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from packages.experiments.analysis import (
    AnalysisFinding,
    AnalysisStatus,
    AssociationalEstimate,
    AssumptionStatus,
    ConclusionType,
    ConfidenceInterval,
    CredibleInterval,
    DescriptiveStatistic,
    DescriptiveStatisticType,
    Diagnostic,
    DiagnosticOutcome,
    DiagnosticSeverity,
    MeasuredValue,
    MetricUnit,
    ObservationalEstimate,
    PosteriorProbability,
    ProvenanceRecord,
    ProvenanceRecords,
    ProvenanceSourceType,
    QuasiExperimentalEstimate,
    RandomizedExperimentEstimate,
    StandardError,
    UncertaintyBundle,
    UncertaintyUnavailable,
    UnitDimension,
    ValueScale,
)
from tests.analysis_contract_fixtures import (
    effect_details,
    outcome,
    proportion_unit,
    randomized_estimate,
    source,
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


def test_associational_estimate_cannot_claim_a_causal_conclusion() -> None:
    with pytest.raises(ValidationError):
        AssociationalEstimate(
            finding_type="associational_estimate",
            conclusion_type=ConclusionType.CAUSAL_EFFECT,
            estimate=effect_details(analysis_status=AnalysisStatus.COMPLETED),
        )


def test_randomized_estimate_requires_an_explicit_conclusion_type() -> None:
    with pytest.raises(ValidationError):
        RandomizedExperimentEstimate.model_validate(
            {
                "finding_type": "randomized_experiment_estimate",
                "estimate": effect_details().model_dump(mode="json"),
            }
        )


def test_estimand_and_estimate_serialize_with_stable_values() -> None:
    estimate = randomized_estimate()
    payload = estimate.model_dump(mode="json")
    assert payload["finding_type"] == "randomized_experiment_estimate"
    assert payload["conclusion_type"] == "causal_effect"
    assert payload["estimate"]["estimand"]["kind"] == "intention_to_treat"
    assert payload["estimate"]["uncertainty"]["measures"][0]["kind"] == ("confidence_interval")


def test_descriptive_statistic_has_distinct_evidence_shape_without_estimand() -> None:
    statistic = DescriptiveStatistic(
        finding_type="descriptive_statistic",
        statistic_type=DescriptiveStatisticType.SAMPLE_PROPORTION,
        status=AnalysisStatus.COMPLETED,
        metric=outcome().metric,
        value=MeasuredValue(value=0.2, unit=proportion_unit()),
        uncertainty=effect_details().uncertainty,
        sample_size=200,
        provenance=(source(),),
    )
    payload = statistic.model_dump(mode="json")
    assert payload["statistic_type"] == "sample_proportion"
    assert payload["provenance"][0]["source_type"] == "experiment_data"
    assert "estimand" not in payload


def test_effect_categories_remain_distinct_through_finding_union_round_trip() -> None:
    details = effect_details()
    findings = (
        AssociationalEstimate(
            conclusion_type=ConclusionType.ASSOCIATION,
            estimate=details,
        ),
        randomized_estimate(),
        QuasiExperimentalEstimate(
            conclusion_type=ConclusionType.CAUSAL_EFFECT,
            estimate=details,
        ),
        ObservationalEstimate(
            conclusion_type=ConclusionType.ASSOCIATION,
            estimate=details,
        ),
    )
    adapter = TypeAdapter(AnalysisFinding)
    restored = tuple(adapter.validate_python(item.model_dump(mode="json")) for item in findings)
    assert [item.finding_type for item in restored] == [
        "associational_estimate",
        "randomized_experiment_estimate",
        "quasi_experimental_estimate",
        "observational_estimate",
    ]
    assert restored == findings


def test_observational_estimate_accepts_an_explicit_causal_conclusion() -> None:
    estimate = ObservationalEstimate(
        conclusion_type=ConclusionType.CAUSAL_EFFECT,
        estimate=effect_details(),
    )
    assert estimate.conclusion_type is ConclusionType.CAUSAL_EFFECT


def test_task_four_public_enum_vocabularies_are_stable() -> None:
    assert [member.value for member in DescriptiveStatisticType] == [
        "sample_mean",
        "sample_proportion",
        "sample_count",
    ]
    assert [member.value for member in ConclusionType] == [
        "association",
        "causal_effect",
        "projection",
    ]
    assert [member.value for member in ProvenanceSourceType] == [
        "experiment_data",
        "analysis_request",
        "report",
        "configuration",
        "derived",
        "user_supplied",
        "external_reference",
    ]
    assert [member.value for member in AssumptionStatus] == [
        "supported",
        "violated",
        "unassessed",
        "untestable",
    ]
    assert [member.value for member in DiagnosticSeverity] == [
        "info",
        "warning",
        "error",
        "fatal",
    ]
    assert [member.value for member in DiagnosticOutcome] == [
        "passed",
        "failed",
        "unavailable",
    ]


def test_effect_estimate_rejects_terminal_status_and_invalid_sample_counts() -> None:
    payload = effect_details().model_dump(mode="json")
    payload["status"] = "failed"
    with pytest.raises(ValidationError):
        type(effect_details()).model_validate(payload)

    payload = effect_details().model_dump(mode="json")
    payload["sample_counts"]["total"] = 201
    with pytest.raises(ValidationError, match="total"):
        type(effect_details()).model_validate(payload)


@pytest.mark.parametrize(
    ("value_scale", "expected_multiplier", "invalid_multiplier"),
    [
        (ValueScale.PROPORTION, 1.0, 0.01),
        (ValueScale.PERCENT, 0.01, 1.0),
        (ValueScale.PERCENTAGE_POINT, 0.01, 0.0001),
        (ValueScale.BASIS_POINT, 0.0001, 0.01),
    ],
)
def test_standardized_proportion_scales_require_exact_conversion_multipliers(
    value_scale: ValueScale,
    expected_multiplier: float,
    invalid_multiplier: float,
) -> None:
    unit = MetricUnit(
        dimension=UnitDimension.PROPORTION,
        value_scale=value_scale,
        symbol=value_scale.value,
        scale_to_base_unit=expected_multiplier,
    )
    assert unit.scale_to_base_unit == expected_multiplier

    with pytest.raises(ValidationError, match="scale_to_base_unit"):
        MetricUnit(
            dimension=UnitDimension.PROPORTION,
            value_scale=value_scale,
            symbol=value_scale.value,
            scale_to_base_unit=invalid_multiplier,
        )
