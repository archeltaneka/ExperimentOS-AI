from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from packages.experiments.analysis import (
    AnalysisWarning,
    AssumptionAssessment,
    AssumptionStatus,
    ConfidenceInterval,
    EstimandDefinition,
    EstimandKind,
    MeasuredValue,
    MetricDefinition,
    MetricType,
    MetricUnit,
    ProvenanceRecord,
    ProvenanceSourceType,
    UnitDimension,
    ValueScale,
)
from packages.experiments.analysis.randomized import (
    BinaryArmSummary,
    ComputationStatus,
    Conclusion,
    ContinuousArmSummary,
    EvidenceCategory,
    PointEffect,
    PracticalSignificance,
    RandomizedAbstentionReason,
    RandomizedAnalysisConfig,
    RandomizedAnalysisResult,
    RandomizedDiagnostic,
    RandomizedDiagnosticCategory,
    RandomizedTestResult,
    RandomizedTestType,
    RelativeEffectAvailability,
    RelativeEffectReason,
)


def _proportion_unit() -> MetricUnit:
    return MetricUnit(
        dimension=UnitDimension.PROPORTION,
        value_scale=ValueScale.PROPORTION,
        symbol="1",
        scale_to_base_unit=1.0,
    )


def _metric() -> MetricDefinition:
    return MetricDefinition(
        metric_id="conversion_rate",
        label="Conversion rate",
        metric_type=MetricType.BINARY,
        unit=_proportion_unit(),
    )


def _provenance() -> tuple[ProvenanceRecord, ...]:
    return (
        ProvenanceRecord(
            source_type=ProvenanceSourceType.EXPERIMENT_DATA,
            source_id="exp-001",
        ),
    )


def _test_result() -> RandomizedTestResult:
    return RandomizedTestResult(
        test_type=RandomizedTestType.TWO_PROPORTION_Z,
        standard_error=0.04,
        statistic=2.5,
        degrees_of_freedom=None,
        p_value=0.012,
        confidence_interval=ConfidenceInterval(
            lower=0.02,
            upper=0.18,
            confidence_level=0.95,
        ),
    )


def _completed_result() -> RandomizedAnalysisResult:
    return RandomizedAnalysisResult(
        request_id="request-001",
        metric=_metric(),
        estimand=EstimandDefinition(kind=EstimandKind.INTENTION_TO_TREAT),
        status=ComputationStatus.COMPLETED,
        conclusion=Conclusion.STATISTICALLY_SIGNIFICANT,
        practical_significance=PracticalSignificance.NOT_ASSESSED,
        evidence_category=EvidenceCategory.RANDOMIZED_DESIGN_WITH_SUPPORTED_ASSUMPTIONS,
        treatment_summary=BinaryArmSummary(
            arm_id="treatment",
            n=100,
            successes=60,
            failures=40,
            rate=0.6,
        ),
        control_summary=BinaryArmSummary(
            arm_id="control",
            n=100,
            successes=50,
            failures=50,
            rate=0.5,
        ),
        point_effect=PointEffect(
            absolute_effect=MeasuredValue(value=0.1, unit=_proportion_unit()),
            relative_effect=0.2,
            relative_effect_availability=RelativeEffectAvailability.AVAILABLE,
        ),
        test_result=_test_result(),
        assumptions=(
            AssumptionAssessment(
                code="random_assignment",
                statement="Assignment was randomized.",
                status=AssumptionStatus.SUPPORTED,
            ),
        ),
        diagnostics=(),
        warnings=(AnalysisWarning(code="demo", message="Demo warning.", scope="analysis"),),
        provenance=_provenance(),
        configuration=RandomizedAnalysisConfig(),
    )


def test_config_defaults_are_frozen_and_emit_stable_provenance() -> None:
    config = RandomizedAnalysisConfig()

    assert config.alpha == 0.05
    assert config.confidence_level == 0.95
    assert config.configuration_provenance() == config.configuration_provenance()
    assert config.configuration_provenance().source_type is ProvenanceSourceType.CONFIGURATION
    with pytest.raises(ValidationError):
        config.alpha = 0.1  # type: ignore[misc]


def test_randomized_contracts_are_exported_from_the_analysis_boundary() -> None:
    from packages.experiments.analysis import RandomizedAnalysisConfig as ExportedConfig
    from packages.experiments.analysis import RandomizedAnalysisResult as ExportedResult

    assert ExportedConfig is RandomizedAnalysisConfig
    assert ExportedResult is RandomizedAnalysisResult


def test_config_requires_complementary_alpha_and_confidence_level() -> None:
    with pytest.raises(ValidationError, match="alpha plus confidence_level must equal 1"):
        RandomizedAnalysisConfig(alpha=0.1, confidence_level=0.95)


def test_config_requires_at_least_two_observations_per_arm() -> None:
    with pytest.raises(ValidationError):
        RandomizedAnalysisConfig(minimum_observations_per_arm=1)


def test_arm_summaries_reject_nonfinite_values_and_inconsistent_binary_counts() -> None:
    with pytest.raises(ValidationError):
        ContinuousArmSummary(arm_id="treatment", n=4, mean=math.nan, sample_variance=1.0)
    with pytest.raises(ValidationError, match="successes plus failures must equal n"):
        BinaryArmSummary(arm_id="treatment", n=4, successes=3, failures=2, rate=0.75)


def test_point_effect_requires_a_reason_only_when_relative_effect_is_unavailable() -> None:
    unavailable = PointEffect(
        absolute_effect=MeasuredValue(value=0.1, unit=_proportion_unit()),
        relative_effect=None,
        relative_effect_availability=RelativeEffectAvailability.UNAVAILABLE,
        relative_effect_reason=RelativeEffectReason.ZERO_CONTROL_BASELINE,
    )

    assert unavailable.relative_effect is None
    with pytest.raises(ValidationError, match="available relative effects require a finite value"):
        PointEffect(
            absolute_effect=MeasuredValue(value=0.1, unit=_proportion_unit()),
            relative_effect=None,
            relative_effect_availability=RelativeEffectAvailability.AVAILABLE,
        )


def test_diagnostic_context_is_sorted_and_unique() -> None:
    diagnostic = RandomizedDiagnostic(
        code="sparse_cell",
        category=RandomizedDiagnosticCategory.SAMPLE,
        severity="warning",
        status="failed",
        message="A cell is sparse.",
        context={"z": 5, "a": 2},
        recommended_action="Collect more data.",
    )

    assert [entry.key for entry in diagnostic.context] == ["a", "z"]
    with pytest.raises(ValidationError, match="context keys must be unique"):
        RandomizedDiagnostic(
            code="duplicate_context",
            category=RandomizedDiagnosticCategory.SAMPLE,
            severity="warning",
            status="failed",
            message="Duplicate keys.",
            context=(
                {"key": "a", "value": 1},
                {"key": "a", "value": 2},
            ),
        )


@pytest.mark.parametrize(
    ("status", "conclusion"),
    [
        (ComputationStatus.ABSTAINED, Conclusion.INCONCLUSIVE),
        (ComputationStatus.UNSUPPORTED, Conclusion.UNSUPPORTED),
        (ComputationStatus.INVALID, Conclusion.INVALID),
    ],
)
def test_non_completed_results_cannot_include_fabricated_estimates_or_tests(
    status: ComputationStatus,
    conclusion: Conclusion,
) -> None:
    payload = _completed_result().model_dump()
    payload.update(
        status=status,
        conclusion=conclusion,
        treatment_summary=None,
        control_summary=None,
        point_effect=None,
        test_result=None,
        abstention_reason=RandomizedAbstentionReason(
            code="insufficient_data",
            message="Not enough observations.",
        ),
    )
    result = RandomizedAnalysisResult.model_validate(payload)

    assert result.point_effect is None
    payload["point_effect"] = _completed_result().point_effect
    with pytest.raises(ValidationError, match="must not include point_effect or test_result"):
        RandomizedAnalysisResult.model_validate(payload)


def test_result_requires_its_interval_level_to_match_the_configuration() -> None:
    payload = _completed_result().model_dump()
    payload["configuration"] = RandomizedAnalysisConfig(alpha=0.1, confidence_level=0.9)

    with pytest.raises(ValidationError, match="confidence_interval confidence_level"):
        RandomizedAnalysisResult.model_validate(payload)


@pytest.mark.parametrize(
    ("status", "conclusion"),
    [
        (ComputationStatus.ABSTAINED, Conclusion.INCONCLUSIVE),
        (ComputationStatus.UNSUPPORTED, Conclusion.UNSUPPORTED),
        (ComputationStatus.INVALID, Conclusion.INVALID),
    ],
)
def test_non_numerical_results_omit_arm_summaries(
    status: ComputationStatus,
    conclusion: Conclusion,
) -> None:
    payload = _completed_result().model_dump()
    payload.update(
        status=status,
        conclusion=conclusion,
        treatment_summary=None,
        control_summary=None,
        point_effect=None,
        test_result=None,
        abstention_reason=RandomizedAbstentionReason(
            code="insufficient_data",
            message="Not enough observations.",
        ),
    )

    result = RandomizedAnalysisResult.model_validate(payload)

    assert result.treatment_summary is None
    assert result.control_summary is None


@pytest.mark.parametrize(
    ("status", "conclusion"),
    [
        (ComputationStatus.COMPLETED, Conclusion.STATISTICALLY_SIGNIFICANT),
        (ComputationStatus.INCONCLUSIVE, Conclusion.INCONCLUSIVE),
    ],
)
def test_numerical_results_require_arm_summaries(
    status: ComputationStatus,
    conclusion: Conclusion,
) -> None:
    payload = _completed_result().model_dump()
    payload.update(
        status=status,
        conclusion=conclusion,
        treatment_summary=None,
        control_summary=None,
    )

    with pytest.raises(ValidationError, match="require arm summaries"):
        RandomizedAnalysisResult.model_validate(payload)


def test_result_canonicalizes_diagnostic_order() -> None:
    earlier = RandomizedDiagnostic(
        code="a_diagnostic",
        category=RandomizedDiagnosticCategory.INPUT,
        severity="warning",
        status="failed",
        message="The first diagnostic.",
    )
    later = RandomizedDiagnostic(
        code="z_diagnostic",
        category=RandomizedDiagnosticCategory.INPUT,
        severity="warning",
        status="failed",
        message="The second diagnostic.",
    )
    payload = _completed_result().model_dump()
    payload["diagnostics"] = (later, earlier)

    result = RandomizedAnalysisResult.model_validate(payload)

    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "a_diagnostic",
        "z_diagnostic",
    ]


def test_result_canonicalizes_diagnostics_that_share_the_former_sort_key() -> None:
    earlier = RandomizedDiagnostic(
        code="same_code",
        category=RandomizedDiagnosticCategory.INPUT,
        severity="info",
        status="failed",
        message="Earlier message.",
        context={"a": 1},
        recommended_action="First action.",
    )
    later = RandomizedDiagnostic(
        code="same_code",
        category=RandomizedDiagnosticCategory.INPUT,
        severity="warning",
        status="failed",
        message="Later message.",
        context={"a": 2},
        recommended_action="Second action.",
    )
    payload = _completed_result().model_dump()
    payload["diagnostics"] = (later, earlier)

    result = RandomizedAnalysisResult.model_validate(payload)

    assert [diagnostic.message for diagnostic in result.diagnostics] == [
        "Earlier message.",
        "Later message.",
    ]
