"""Hand-calculated contracts for unadjusted continuous randomized estimates."""

from __future__ import annotations

import math

import pytest

from packages.experiments.analysis.estimands import EstimandDefinition, EstimandKind
from packages.experiments.analysis.metrics import (
    MetricDefinition,
    MetricType,
    MetricUnit,
    UnitDimension,
    ValueScale,
)
from packages.experiments.analysis.provenance import ProvenanceRecord, ProvenanceSourceType
from packages.experiments.analysis.randomized.continuous import analyze_continuous_welch
from packages.experiments.analysis.randomized.models import (
    AlternativeHypothesis,
    ComputationStatus,
    Conclusion,
    PracticalSignificance,
    RelativeEffectAvailability,
    RelativeEffectReason,
)


@pytest.fixture
def continuous_metric() -> MetricDefinition:
    return MetricDefinition(
        metric_id="revenue_per_user",
        label="Revenue per user",
        metric_type=MetricType.CONTINUOUS,
        unit=MetricUnit(
            dimension=UnitDimension.CURRENCY,
            value_scale=ValueScale.RAW,
            symbol="USD",
            scale_to_base_unit=1.0,
            currency_code="USD",
        ),
    )


@pytest.fixture
def difference_in_means() -> EstimandDefinition:
    return EstimandDefinition(kind=EstimandKind.DIFFERENCE_IN_MEANS)


@pytest.fixture
def data_provenance() -> tuple[ProvenanceRecord, ...]:
    return (
        ProvenanceRecord(
            source_type=ProvenanceSourceType.EXPERIMENT_DATA,
            source_id="experiment-001",
        ),
    )


def test_analyze_continuous_welch_matches_hand_calculated_fixture(
    continuous_metric: MetricDefinition,
    difference_in_means: EstimandDefinition,
    data_provenance: tuple[ProvenanceRecord, ...],
) -> None:
    """Welch's estimate uses sample variances, a two-sided t tail, and a t interval."""
    result = analyze_continuous_welch(
        request_id="request-001",
        metric=continuous_metric,
        estimand=difference_in_means,
        treatment_arm_id="treatment",
        treatment_values=(5.0, 7.0, 9.0),
        control_arm_id="control",
        control_values=(2.0, 4.0, 6.0),
        provenance=data_provenance,
    )

    assert result.status is ComputationStatus.COMPLETED
    assert result.conclusion is Conclusion.NOT_STATISTICALLY_SIGNIFICANT
    assert result.practical_significance is PracticalSignificance.NOT_ASSESSED
    assert result.treatment_summary is not None
    assert result.control_summary is not None
    assert result.point_effect is not None
    assert result.test_result is not None
    assert result.treatment_summary.mean == pytest.approx(7.0)
    assert result.control_summary.mean == pytest.approx(4.0)
    assert result.treatment_summary.sample_variance == pytest.approx(4.0)
    assert result.control_summary.sample_variance == pytest.approx(4.0)
    assert result.point_effect.absolute_effect.value == pytest.approx(3.0)
    assert result.point_effect.relative_effect == pytest.approx(0.75)
    assert result.point_effect.relative_effect_availability is RelativeEffectAvailability.AVAILABLE
    assert result.test_result.standard_error == pytest.approx(math.sqrt(8.0 / 3.0))
    assert result.test_result.confidence_interval_standard_error == pytest.approx(
        math.sqrt(8.0 / 3.0)
    )
    assert result.test_result.degrees_of_freedom == pytest.approx(4.0)
    assert result.test_result.statistic == pytest.approx(1.8371173070873836)
    assert result.test_result.p_value == pytest.approx(0.140065984912)
    assert result.test_result.confidence_interval.lower == pytest.approx(-1.533915871055)
    assert result.test_result.confidence_interval.upper == pytest.approx(7.533915871055)
    assert result.test_result.confidence_interval.confidence_level == pytest.approx(0.95)


@pytest.mark.parametrize(
    ("treatment_values", "control_values", "diagnostic_code"),
    [
        ((), (2.0, 4.0), "insufficient_observations"),
        ((5.0,), (2.0, 4.0), "one_observation_arm"),
        ((math.nan, 5.0), (2.0, 4.0), "nonfinite_continuous_outcome"),
    ],
)
def test_analyze_continuous_welch_abstains_with_explicit_input_diagnostic(
    continuous_metric: MetricDefinition,
    difference_in_means: EstimandDefinition,
    data_provenance: tuple[ProvenanceRecord, ...],
    treatment_values: tuple[float, ...],
    control_values: tuple[float, ...],
    diagnostic_code: str,
) -> None:
    """Invalid or undersized arms must be explicit abstentions rather than partial estimates."""
    result = analyze_continuous_welch(
        request_id="request-001",
        metric=continuous_metric,
        estimand=difference_in_means,
        treatment_arm_id="treatment",
        treatment_values=treatment_values,
        control_arm_id="control",
        control_values=control_values,
        provenance=data_provenance,
    )

    assert result.status is ComputationStatus.ABSTAINED
    assert result.conclusion is Conclusion.INCONCLUSIVE
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == diagnostic_code
    assert {diagnostic.code for diagnostic in result.diagnostics} == {diagnostic_code}
    assert result.treatment_summary is None
    assert result.control_summary is None
    assert result.point_effect is None
    assert result.test_result is None


def test_analyze_continuous_welch_marks_relative_lift_unavailable_at_zero_baseline(
    continuous_metric: MetricDefinition,
    difference_in_means: EstimandDefinition,
    data_provenance: tuple[ProvenanceRecord, ...],
) -> None:
    """A finite absolute effect must not fabricate a relative lift from a zero control mean."""
    result = analyze_continuous_welch(
        request_id="request-001",
        metric=continuous_metric,
        estimand=difference_in_means,
        treatment_arm_id="treatment",
        treatment_values=(1.0, 3.0, 5.0),
        control_arm_id="control",
        control_values=(-2.0, 0.0, 2.0),
        provenance=data_provenance,
    )

    assert result.status is ComputationStatus.COMPLETED
    assert result.point_effect is not None
    assert result.point_effect.relative_effect is None
    assert (
        result.point_effect.relative_effect_availability is RelativeEffectAvailability.UNAVAILABLE
    )
    assert result.point_effect.relative_effect_reason is RelativeEffectReason.ZERO_CONTROL_BASELINE
    assert "zero_control_baseline" in {diagnostic.code for diagnostic in result.diagnostics}


def test_analyze_continuous_welch_omits_misleading_relative_lift_for_negative_baseline(
    continuous_metric: MetricDefinition,
    difference_in_means: EstimandDefinition,
    data_provenance: tuple[ProvenanceRecord, ...],
) -> None:
    result = analyze_continuous_welch(
        request_id="request-001",
        metric=continuous_metric,
        estimand=difference_in_means,
        treatment_arm_id="treatment",
        treatment_values=(-7.0, -5.0, -3.0),
        control_arm_id="control",
        control_values=(-12.0, -10.0, -8.0),
        provenance=data_provenance,
    )

    assert result.status is ComputationStatus.COMPLETED
    assert result.point_effect is not None
    assert result.point_effect.absolute_effect.value == pytest.approx(5.0)
    assert result.point_effect.relative_effect is None
    assert (
        result.point_effect.relative_effect_availability is RelativeEffectAvailability.UNAVAILABLE
    )
    assert (
        result.point_effect.relative_effect_reason
        is RelativeEffectReason.NON_POSITIVE_CONTROL_BASELINE
    )
    assert "nonpositive_control_baseline" in {diagnostic.code for diagnostic in result.diagnostics}


def test_analyze_continuous_welch_abstains_when_nonzero_subnormal_baseline_overflows_lift(
    continuous_metric: MetricDefinition,
    difference_in_means: EstimandDefinition,
    data_provenance: tuple[ProvenanceRecord, ...],
) -> None:
    """A finite nonzero baseline can still produce an unrepresentable relative effect."""
    result = analyze_continuous_welch(
        request_id="request-001",
        metric=continuous_metric,
        estimand=difference_in_means,
        treatment_arm_id="treatment",
        treatment_values=(1.0, 2.0),
        control_arm_id="control",
        control_values=(5e-324, 1e-323),
        provenance=data_provenance,
    )

    assert result.status is ComputationStatus.ABSTAINED
    assert result.conclusion is Conclusion.INCONCLUSIVE
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "nonfinite_relative_effect"
    assert {diagnostic.code for diagnostic in result.diagnostics} == {"nonfinite_relative_effect"}


def test_analyze_continuous_welch_abstains_when_zero_standard_error_makes_t_undefined(
    continuous_metric: MetricDefinition,
    difference_in_means: EstimandDefinition,
    data_provenance: tuple[ProvenanceRecord, ...],
) -> None:
    """A zero-variance pair has no finite Welch t statistic or confidence interval."""
    result = analyze_continuous_welch(
        request_id="request-001",
        metric=continuous_metric,
        estimand=difference_in_means,
        treatment_arm_id="treatment",
        treatment_values=(5.0, 5.0),
        control_arm_id="control",
        control_values=(2.0, 2.0),
        provenance=data_provenance,
    )

    assert result.status is ComputationStatus.ABSTAINED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "zero_standard_error"
    assert {diagnostic.code for diagnostic in result.diagnostics} == {"zero_standard_error"}


@pytest.mark.parametrize(
    "alternative",
    [AlternativeHypothesis.GREATER_THAN, AlternativeHypothesis.LESS_THAN],
)
def test_analyze_continuous_welch_rejects_one_sided_alternatives(
    continuous_metric: MetricDefinition,
    difference_in_means: EstimandDefinition,
    data_provenance: tuple[ProvenanceRecord, ...],
    alternative: AlternativeHypothesis,
) -> None:
    result = analyze_continuous_welch(
        request_id="request-001",
        metric=continuous_metric,
        estimand=difference_in_means,
        treatment_arm_id="treatment",
        treatment_values=(5.0, 7.0, 9.0),
        control_arm_id="control",
        control_values=(2.0, 4.0, 6.0),
        provenance=data_provenance,
        alternative=alternative,
    )

    assert result.status is ComputationStatus.UNSUPPORTED
    assert result.conclusion is Conclusion.UNSUPPORTED
    assert result.hypothesis.alternative is alternative
    assert result.test_result is None
    assert result.point_effect is None
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "unsupported_alternative_hypothesis"


@pytest.mark.parametrize(
    ("treatment_values", "control_values", "expected_effect", "expected_p_value"),
    [
        ((1.0, 2.0, 3.0), (4.0, 5.0, 6.0), -3.0, 0.021311641128756727),
        ((1.0, 2.0, 3.0), (1.0, 2.0, 3.0), 0.0, 1.0),
    ],
)
def test_analyze_continuous_welch_covers_negative_and_null_effects(
    continuous_metric: MetricDefinition,
    difference_in_means: EstimandDefinition,
    data_provenance: tuple[ProvenanceRecord, ...],
    treatment_values: tuple[float, ...],
    control_values: tuple[float, ...],
    expected_effect: float,
    expected_p_value: float,
) -> None:
    result = analyze_continuous_welch(
        request_id="request-001",
        metric=continuous_metric,
        estimand=difference_in_means,
        treatment_arm_id="treatment",
        treatment_values=treatment_values,
        control_arm_id="control",
        control_values=control_values,
        provenance=data_provenance,
    )

    assert result.point_effect is not None
    assert result.test_result is not None
    assert result.point_effect.absolute_effect.value == pytest.approx(expected_effect)
    assert result.test_result.p_value == pytest.approx(expected_p_value)


def test_analyze_continuous_welch_supports_unequal_sizes_variances_and_one_constant_arm(
    continuous_metric: MetricDefinition,
    difference_in_means: EstimandDefinition,
    data_provenance: tuple[ProvenanceRecord, ...],
) -> None:
    result = analyze_continuous_welch(
        request_id="request-001",
        metric=continuous_metric,
        estimand=difference_in_means,
        treatment_arm_id="treatment",
        treatment_values=(10.0, 10.0, 10.0),
        control_arm_id="control",
        control_values=(1.0, 2.0, 4.0, 8.0),
        provenance=data_provenance,
    )

    assert result.status is ComputationStatus.COMPLETED
    assert result.treatment_summary is not None
    assert result.control_summary is not None
    assert result.test_result is not None
    assert result.treatment_summary.n == 3
    assert result.control_summary.n == 4
    assert result.treatment_summary.sample_variance == 0.0
    assert result.control_summary.sample_variance == pytest.approx(9.583333333333334)
    assert result.test_result.standard_error == pytest.approx(1.547847968417226)
    assert result.test_result.degrees_of_freedom == pytest.approx(3.0)
