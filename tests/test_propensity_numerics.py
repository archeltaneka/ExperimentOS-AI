"""Hand-derived references for propensity diagnostic numerics."""

from __future__ import annotations

import math

import pytest

from packages.experiments.analysis.causal import CausalEstimandKind
from packages.experiments.analysis.causal.propensity import (
    CommonSupportDiagnostic,
    CommonSupportStatus,
    OverlapStatus,
    PropensityConfig,
    PropensityFitStatus,
    PropensityModelFit,
    PropensityWeight,
)
from packages.experiments.analysis.causal.propensity.numerics import (
    PropensityNumericalError,
    assess_overlap,
    build_ess_diagnostic,
    build_weight_diagnostics,
    common_support_diagnostic,
    compute_weight_values,
    effective_sample_size,
    standardized_mean_difference,
    summarize_distribution,
)


def test_ess_ratios_are_clamped_to_their_mathematical_probability_bound() -> None:
    diagnostic = build_ess_diagnostic(
        (4.0,) * 10 + (4.0 / 3.0,) * 30,
        (True,) * 10 + (False,) * 30,
        PropensityConfig(),
    )

    assert diagnostic.overall_ratio <= 1.0
    assert diagnostic.treated_ratio == 1.0
    assert diagnostic.control_ratio == 1.0


def _overlap_result(
    *,
    scores: tuple[float, ...],
    treated: tuple[bool, ...],
    config: PropensityConfig,
    estimand: CausalEstimandKind = CausalEstimandKind.ATE,
    support: CommonSupportDiagnostic | None = None,
):
    values = compute_weight_values(scores, treated, estimand)
    weights = build_weight_diagnostics(
        tuple(
            PropensityWeight(
                unit_id=f"unit-{index}",
                treated=is_treated,
                value=value,
            )
            for index, (is_treated, value) in enumerate(zip(treated, values, strict=True))
        ),
        estimand,
        config,
    )
    return assess_overlap(
        scores=scores,
        treated=treated,
        support=support or common_support_diagnostic(scores, treated),
        model_fit=PropensityModelFit(
            status=PropensityFitStatus.CONVERGED,
            converged=True,
            scores=scores,
            classes=(0, 1),
            iteration_count=3,
            solver="lbfgs",
            warning_codes=(),
            sklearn_version="test",
            training_accuracy=0.75,
            maximum_absolute_coefficient=1.0,
            extreme_score_fraction=0.0,
        ),
        weights=weights,
        estimand=estimand,
        config=config,
    )


def test_ate_weight_hand_reference() -> None:
    weights = compute_weight_values(
        (0.25, 0.80),
        (True, False),
        CausalEstimandKind.ATE,
    )

    assert weights == pytest.approx((4.0, 5.0))


def test_att_weight_hand_reference() -> None:
    weights = compute_weight_values(
        (0.25, 0.80),
        (True, False),
        CausalEstimandKind.ATT,
    )

    assert weights == pytest.approx((1.0, 4.0))


@pytest.mark.parametrize(
    ("scores", "treated"),
    (((0.0,), (True,)), ((1.0,), (False,))),
)
def test_weights_reject_zero_denominators_without_clipping(
    scores: tuple[float, ...], treated: tuple[bool, ...]
) -> None:
    with pytest.raises(PropensityNumericalError, match="denominator"):
        compute_weight_values(scores, treated, CausalEstimandKind.ATE)


def test_effective_sample_size_hand_reference() -> None:
    # (1 + 2 + 3)^2 / (1^2 + 2^2 + 3^2) = 36 / 14.
    result = effective_sample_size((1.0, 2.0, 3.0))

    assert result == pytest.approx(36.0 / 14.0)


def test_effective_sample_size_rejects_empty_or_invalid_weights() -> None:
    assert effective_sample_size(()) is None
    with pytest.raises(PropensityNumericalError):
        effective_sample_size((1.0, math.inf))
    with pytest.raises(PropensityNumericalError):
        effective_sample_size((0.0, 0.0))


def test_common_support_uses_intersection_of_observed_arm_ranges() -> None:
    support = common_support_diagnostic(
        (0.20, 0.40, 0.35, 0.70),
        (True, True, False, False),
    )

    assert support.status is CommonSupportStatus.AVAILABLE
    assert support.lower == pytest.approx(0.35)
    assert support.upper == pytest.approx(0.40)
    assert support.treated_inside == 1
    assert support.control_inside == 1
    assert support.treated_outside == 1
    assert support.control_outside == 1
    assert support.total_outside == 2


def test_empty_common_support_is_structured_not_negative_width() -> None:
    support = common_support_diagnostic(
        (0.80, 0.90, 0.10, 0.20),
        (True, True, False, False),
    )

    assert support.status is CommonSupportStatus.EMPTY
    assert support.lower == pytest.approx(0.80)
    assert support.upper == pytest.approx(0.20)
    assert support.width == 0.0
    assert support.total_outside == 4


def test_continuous_smd_hand_reference() -> None:
    # Means are 3 and 1. Population variances are both 1, so pooled SD is 1.
    result = standardized_mean_difference(
        treated_values=(2.0, 4.0),
        control_values=(0.0, 2.0),
        treated_weights=(1.0, 1.0),
        control_weights=(1.0, 1.0),
    )

    assert result.available is True
    assert result.treated_mean == pytest.approx(3.0)
    assert result.control_mean == pytest.approx(1.0)
    assert result.smd == pytest.approx(2.0)


def test_weighted_smd_uses_weighted_population_variance() -> None:
    result = standardized_mean_difference(
        treated_values=(0.0, 2.0),
        control_values=(0.0, 2.0),
        treated_weights=(1.0, 3.0),
        control_weights=(3.0, 1.0),
    )

    assert result.treated_mean == pytest.approx(1.5)
    assert result.control_mean == pytest.approx(0.5)
    assert result.treated_variance == pytest.approx(0.75)
    assert result.control_variance == pytest.approx(0.75)
    assert result.smd == pytest.approx(1.0 / math.sqrt(0.75))


def test_zero_pooled_variance_distinguishes_balance_from_unavailable() -> None:
    balanced = standardized_mean_difference(
        treated_values=(1.0, 1.0),
        control_values=(1.0, 1.0),
        treated_weights=(1.0, 1.0),
        control_weights=(1.0, 1.0),
    )
    imbalanced = standardized_mean_difference(
        treated_values=(1.0, 1.0),
        control_values=(0.0, 0.0),
        treated_weights=(1.0, 1.0),
        control_weights=(1.0, 1.0),
    )

    assert balanced.available is True
    assert balanced.smd == 0.0
    assert imbalanced.available is False
    assert imbalanced.smd is None
    assert imbalanced.warning_code == "balance.zero_pooled_variance"


def test_distribution_summary_uses_sample_sd_and_linear_quantiles() -> None:
    summary = summarize_distribution((1.0, 2.0, 3.0, 4.0), (0.25, 0.5, 0.75))

    assert summary.count == 4
    assert summary.mean == pytest.approx(2.5)
    assert summary.standard_deviation == pytest.approx(math.sqrt(5.0 / 3.0))
    assert summary.minimum == 1.0
    assert summary.maximum == 4.0
    assert summary.median == pytest.approx(2.5)
    assert tuple(item.value for item in summary.quantiles) == pytest.approx((1.75, 2.5, 3.25))


def test_extreme_score_fraction_uses_configured_weak_and_severe_thresholds() -> None:
    scores = (0.01, 0.99, 0.40, 0.60)
    treated = (True, False, True, False)
    weak = _overlap_result(
        scores=scores,
        treated=treated,
        config=PropensityConfig(
            weak_extreme_score_fraction=0.25,
            severe_extreme_score_fraction=0.75,
            extreme_weight_threshold=1000.0,
            minimum_effective_sample_size=1.0,
            minimum_ess_ratio=0.0,
        ),
        support=CommonSupportDiagnostic(status=CommonSupportStatus.AVAILABLE, width=0.8),
    )
    severe = _overlap_result(
        scores=scores,
        treated=treated,
        config=PropensityConfig(
            weak_extreme_score_fraction=0.10,
            severe_extreme_score_fraction=0.25,
            extreme_weight_threshold=1000.0,
            minimum_effective_sample_size=1.0,
            minimum_ess_ratio=0.0,
        ),
        support=CommonSupportDiagnostic(status=CommonSupportStatus.AVAILABLE, width=0.8),
    )

    assert weak.status is OverlapStatus.WEAK
    assert "overlap.weak_extreme_scores" in weak.diagnostic_codes
    assert severe.status is OverlapStatus.SEVERE
    assert "overlap.severe_extreme_scores" in severe.diagnostic_codes


def test_extreme_weight_fraction_can_be_a_severe_positivity_violation() -> None:
    result = _overlap_result(
        scores=(0.05, 0.95, 0.40, 0.60),
        treated=(True, False, True, False),
        config=PropensityConfig(
            extreme_score_threshold=0.01,
            extreme_weight_threshold=10.0,
            weak_extreme_weight_fraction=0.10,
            severe_extreme_weight_fraction=0.25,
            minimum_effective_sample_size=1.0,
            minimum_ess_ratio=0.0,
        ),
        support=CommonSupportDiagnostic(status=CommonSupportStatus.AVAILABLE, width=0.8),
    )

    assert result.status is OverlapStatus.SEVERE
    assert "weight.severe_extreme_tail" in result.diagnostic_codes


def test_att_requires_a_configured_minimum_comparable_control_population() -> None:
    result = _overlap_result(
        scores=(0.4, 0.6, 0.5, 0.55),
        treated=(True, True, False, False),
        estimand=CausalEstimandKind.ATT,
        config=PropensityConfig(
            minimum_effective_sample_size=1.0,
            minimum_ess_ratio=0.0,
            minimum_att_control_support_count=2,
            minimum_att_control_support_proportion=0.5,
        ),
        support=CommonSupportDiagnostic(
            status=CommonSupportStatus.AVAILABLE,
            lower=0.4,
            upper=0.6,
            width=0.2,
            treated_inside=2,
            control_inside=0,
            treated_outside=0,
            control_outside=2,
            total_outside=2,
            treated_inside_proportion=1.0,
            control_inside_proportion=0.0,
        ),
    )

    assert result.status is OverlapStatus.SEVERE
    assert result.comparator_inside_support_count == 0
    assert result.comparator_inside_support_fraction == 0.0
    assert "overlap.insufficient_att_controls" in result.diagnostic_codes
