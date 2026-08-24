"""Owned propensity-score contract behavior."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from packages.experiments.analysis.causal.propensity import (
    NumericScalingPolicy,
    PropensityConfig,
    PropensityCovariateBinding,
    PropensityDataBinding,
    PropensityFeatureKind,
    PropensityScore,
    PropensityTrimmingConfig,
    PropensityWeight,
    PropensityWeightCapConfig,
)


def test_configuration_exposes_deterministic_statistical_defaults() -> None:
    config = PropensityConfig()

    assert config.model_family == "regularized_logistic_regression"
    assert config.link == "logit"
    assert config.solver == "lbfgs"
    assert config.penalty == "l2"
    assert config.l1_ratio == 0.0
    assert config.inverse_regularization_strength == 1.0
    assert config.tolerance == 1e-8
    assert config.maximum_iterations == 1000
    assert config.fit_intercept is True
    assert config.numeric_scaling is NumericScalingPolicy.STANDARDIZE
    assert config.categorical_encoding == "one_hot_drop_first"
    assert config.random_seed == 0
    assert config.weak_extreme_score_fraction == 0.05
    assert config.severe_extreme_score_fraction == 0.20
    assert config.weak_extreme_weight_fraction == 0.01
    assert config.severe_extreme_weight_fraction == 0.20
    assert config.minimum_att_control_support_count == 1
    assert config.minimum_att_control_support_proportion == 0.10
    assert config.trimming is None
    assert config.weight_cap is None


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("inverse_regularization_strength", 0.0),
        ("tolerance", 0.0),
        ("maximum_iterations", 0),
        ("extreme_score_threshold", 0.0),
        ("minimum_ess_ratio", 1.1),
        ("balance_threshold", -0.1),
    ),
)
def test_configuration_rejects_invalid_numerical_policy(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        PropensityConfig(**{field: value})


def test_configuration_rejects_incoherent_quantiles_and_overlap_thresholds() -> None:
    with pytest.raises(ValidationError, match="quantile"):
        PropensityConfig(score_quantiles=(0.5, 0.5))
    with pytest.raises(ValidationError, match="severe"):
        PropensityConfig(
            weak_outside_support_fraction=0.25,
            severe_outside_support_fraction=0.10,
        )
    with pytest.raises(ValidationError, match="extreme-score"):
        PropensityConfig(
            weak_extreme_score_fraction=0.25,
            severe_extreme_score_fraction=0.10,
        )
    with pytest.raises(ValidationError, match="extreme-weight"):
        PropensityConfig(
            weak_extreme_weight_fraction=0.25,
            severe_extreme_weight_fraction=0.10,
        )


def test_trim_and_cap_require_explicit_valid_bounds() -> None:
    assert PropensityTrimmingConfig(lower=0.1, upper=0.9).lower == 0.1
    assert PropensityWeightCapConfig(maximum=10.0).maximum == 10.0

    with pytest.raises(ValidationError, match="lower"):
        PropensityTrimmingConfig(lower=0.9, upper=0.1)
    with pytest.raises(ValidationError):
        PropensityWeightCapConfig(maximum=0.0)


def test_binding_requires_unique_roles_and_explicit_feature_kinds() -> None:
    binding = PropensityDataBinding(
        unit_column="unit_id",
        treatment_column="treated",
        covariates=(
            PropensityCovariateBinding(
                variable_id="country",
                column="country",
                feature_kind=PropensityFeatureKind.CATEGORICAL,
            ),
            PropensityCovariateBinding(
                variable_id="prior_orders",
                column="prior_orders",
                feature_kind=PropensityFeatureKind.NUMERIC,
            ),
        ),
    )

    assert tuple(item.variable_id for item in binding.covariates) == (
        "country",
        "prior_orders",
    )

    with pytest.raises(ValidationError, match="unique"):
        PropensityDataBinding(
            unit_column="unit_id",
            treatment_column="treated",
            covariates=(
                PropensityCovariateBinding(
                    variable_id="prior_orders",
                    column="x1",
                    feature_kind=PropensityFeatureKind.NUMERIC,
                ),
                PropensityCovariateBinding(
                    variable_id="prior_orders",
                    column="x2",
                    feature_kind=PropensityFeatureKind.NUMERIC,
                ),
            ),
        )


@pytest.mark.parametrize("score", (-0.1, 1.1, math.nan, math.inf))
def test_unit_scores_are_finite_probabilities(score: float) -> None:
    with pytest.raises(ValidationError):
        PropensityScore(unit_id="u-1", treated=True, score=score)


def test_unit_weights_allow_zero_for_att_control_units() -> None:
    assert PropensityWeight(unit_id="u-1", treated=False, value=0.0).value == 0.0


@pytest.mark.parametrize("weight", (-1.0, math.nan, math.inf))
def test_unit_weights_are_nonnegative_and_finite(weight: float) -> None:
    with pytest.raises(ValidationError):
        PropensityWeight(unit_id="u-1", treated=True, value=weight)
