"""Hand-calculated contracts for unadjusted binary randomized estimates."""

from __future__ import annotations

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
from packages.experiments.analysis.randomized.binary import analyze_binary_two_proportion_z
from packages.experiments.analysis.randomized.models import (
    AlternativeHypothesis,
    ComputationStatus,
    Conclusion,
    RelativeEffectAvailability,
    RelativeEffectReason,
)


@pytest.fixture
def binary_metric() -> MetricDefinition:
    return MetricDefinition(
        metric_id="conversion",
        label="Conversion",
        metric_type=MetricType.BINARY,
        unit=MetricUnit(
            dimension=UnitDimension.PROPORTION,
            value_scale=ValueScale.PROPORTION,
            symbol="proportion",
            scale_to_base_unit=1.0,
        ),
    )


@pytest.fixture
def difference_in_proportions() -> EstimandDefinition:
    return EstimandDefinition(kind=EstimandKind.DIFFERENCE_IN_PROPORTIONS)


@pytest.fixture
def data_provenance() -> tuple[ProvenanceRecord, ...]:
    return (
        ProvenanceRecord(
            source_type=ProvenanceSourceType.EXPERIMENT_DATA,
            source_id="experiment-001",
        ),
    )


def test_analyze_binary_two_proportion_z_matches_hand_calculated_fixture(
    binary_metric: MetricDefinition,
    difference_in_proportions: EstimandDefinition,
    data_provenance: tuple[ProvenanceRecord, ...],
) -> None:
    """The null test uses pooled SE while the interval uses unpooled SE."""
    result = analyze_binary_two_proportion_z(
        request_id="request-001",
        metric=binary_metric,
        estimand=difference_in_proportions,
        treatment_arm_id="treatment",
        treatment_values=(1,) * 30 + (0,) * 20,
        control_arm_id="control",
        control_values=(1,) * 20 + (0,) * 60,
        provenance=data_provenance,
    )

    assert result.status is ComputationStatus.COMPLETED
    assert result.conclusion is Conclusion.STATISTICALLY_SIGNIFICANT
    assert result.treatment_summary is not None
    assert result.control_summary is not None
    assert result.point_effect is not None
    assert result.test_result is not None
    assert result.treatment_summary.rate == pytest.approx(0.6)
    assert result.control_summary.rate == pytest.approx(0.25)
    assert result.point_effect.absolute_effect.value == pytest.approx(0.35)
    assert result.point_effect.relative_effect == pytest.approx(1.4)
    assert result.point_effect.relative_effect_availability is RelativeEffectAvailability.AVAILABLE
    assert result.test_result.standard_error == pytest.approx(0.08770580193070292)
    assert result.test_result.statistic == pytest.approx(3.990613987846983)
    assert result.test_result.p_value == pytest.approx(0.000065902466)
    assert result.test_result.degrees_of_freedom is None
    assert result.test_result.confidence_interval.lower == pytest.approx(0.184342457309)
    assert result.test_result.confidence_interval.upper == pytest.approx(0.515657542691)
    assert result.test_result.confidence_interval.confidence_level == pytest.approx(0.95)
    assert (
        (
            result.test_result.confidence_interval.upper
            - result.test_result.confidence_interval.lower
        )
        / (2.0 * 1.959963984540054)
    ) == pytest.approx(0.08452070752188483)


def test_analyze_binary_two_proportion_z_marks_relative_lift_unavailable_at_zero_control(
    binary_metric: MetricDefinition,
    difference_in_proportions: EstimandDefinition,
    data_provenance: tuple[ProvenanceRecord, ...],
) -> None:
    """A zero control rate yields an absolute result but no fabricated relative effect."""
    result = analyze_binary_two_proportion_z(
        request_id="request-001",
        metric=binary_metric,
        estimand=difference_in_proportions,
        treatment_arm_id="treatment",
        treatment_values=(1,) * 10 + (0,) * 10,
        control_arm_id="control",
        control_values=(0,) * 20,
        provenance=data_provenance,
    )

    assert result.status is ComputationStatus.COMPLETED
    assert result.point_effect is not None
    assert result.point_effect.absolute_effect.value == pytest.approx(0.5)
    assert result.point_effect.relative_effect is None
    assert (
        result.point_effect.relative_effect_availability is RelativeEffectAvailability.UNAVAILABLE
    )
    assert result.point_effect.relative_effect_reason is RelativeEffectReason.ZERO_CONTROL_BASELINE
    assert "zero_control_baseline" in {diagnostic.code for diagnostic in result.diagnostics}


@pytest.mark.parametrize(
    ("treatment_values", "control_values"),
    [
        ((1,) * 10, (1,) * 10),
        ((0,) * 10, (0,) * 10),
    ],
)
def test_analyze_binary_two_proportion_z_abstains_for_all_success_or_failure_arms(
    binary_metric: MetricDefinition,
    difference_in_proportions: EstimandDefinition,
    data_provenance: tuple[ProvenanceRecord, ...],
    treatment_values: tuple[int, ...],
    control_values: tuple[int, ...],
) -> None:
    """A degenerate pooled null standard error has no finite z statistic."""
    result = analyze_binary_two_proportion_z(
        request_id="request-001",
        metric=binary_metric,
        estimand=difference_in_proportions,
        treatment_arm_id="treatment",
        treatment_values=treatment_values,
        control_arm_id="control",
        control_values=control_values,
        provenance=data_provenance,
    )

    assert result.status is ComputationStatus.ABSTAINED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "zero_standard_error"
    assert {diagnostic.code for diagnostic in result.diagnostics} == {"zero_standard_error"}


def test_analyze_binary_two_proportion_z_abstains_for_sparse_expected_cells(
    binary_metric: MetricDefinition,
    difference_in_proportions: EstimandDefinition,
    data_provenance: tuple[ProvenanceRecord, ...],
) -> None:
    """The configured normal approximation rejects a cell with expected count below five."""
    result = analyze_binary_two_proportion_z(
        request_id="request-001",
        metric=binary_metric,
        estimand=difference_in_proportions,
        treatment_arm_id="treatment",
        treatment_values=(1,) + (0,) * 9,
        control_arm_id="control",
        control_values=(1,) * 5 + (0,) * 5,
        provenance=data_provenance,
    )

    assert result.status is ComputationStatus.ABSTAINED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "sparse_cell"
    assert {diagnostic.code for diagnostic in result.diagnostics} == {"sparse_cell"}


def test_analyze_binary_two_proportion_z_abstains_for_invalid_binary_outcomes(
    binary_metric: MetricDefinition,
    difference_in_proportions: EstimandDefinition,
    data_provenance: tuple[ProvenanceRecord, ...],
) -> None:
    """The estimator must not coerce an invalid indicator to make an approximation run."""
    result = analyze_binary_two_proportion_z(
        request_id="request-001",
        metric=binary_metric,
        estimand=difference_in_proportions,
        treatment_arm_id="treatment",
        treatment_values=(1, 0, 2, 0, 1),
        control_arm_id="control",
        control_values=(1, 0, 1, 0, 1),
        provenance=data_provenance,
    )

    assert result.status is ComputationStatus.ABSTAINED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "invalid_binary_outcome"
    assert {diagnostic.code for diagnostic in result.diagnostics} == {"invalid_binary_outcome"}


@pytest.mark.parametrize(
    "alternative",
    [AlternativeHypothesis.GREATER_THAN, AlternativeHypothesis.LESS_THAN],
)
def test_analyze_binary_two_proportion_z_rejects_one_sided_alternatives(
    binary_metric: MetricDefinition,
    difference_in_proportions: EstimandDefinition,
    data_provenance: tuple[ProvenanceRecord, ...],
    alternative: AlternativeHypothesis,
) -> None:
    result = analyze_binary_two_proportion_z(
        request_id="request-001",
        metric=binary_metric,
        estimand=difference_in_proportions,
        treatment_arm_id="treatment",
        treatment_values=(1,) * 30 + (0,) * 20,
        control_arm_id="control",
        control_values=(1,) * 20 + (0,) * 60,
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
