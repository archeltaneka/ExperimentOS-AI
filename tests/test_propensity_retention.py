"""Explicit trimming and capping retain unmodified raw diagnostics."""

from __future__ import annotations

import pytest

from packages.experiments.analysis.causal.propensity import (
    DeterministicLogisticPropensityEstimator,
    PropensityConfig,
    PropensityTrimmingConfig,
    PropensityWeightCapConfig,
)
from packages.experiments.analysis.causal.propensity.numerics import common_support_diagnostic
from tests.causal_identification_fixtures import provenance
from tests.propensity_fixtures import (
    good_overlap_rows,
    propensity_execution,
    propensity_table,
)


def analyze(config: PropensityConfig):
    return DeterministicLogisticPropensityEstimator().fit_predict(
        propensity_execution(config=config),
        propensity_table(good_overlap_rows()),
        provenance=provenance("propensity-retention"),
    )


def test_default_policy_does_not_trim_or_cap_any_population() -> None:
    result = analyze(PropensityConfig())

    assert result.retained is None
    assert result.capped_weights is None
    assert result.sample_counts.model == 60
    assert result.weights is not None
    assert len(result.weights.raw) == 60


def test_explicit_trimming_keeps_raw_population_and_recomputes_retained_support() -> None:
    config = PropensityConfig(
        trimming=PropensityTrimmingConfig(lower=0.45, upper=0.55),
    )

    result = analyze(config)

    assert result.retained is not None
    retained = result.retained
    assert 0 < retained.retained_count < result.sample_counts.model
    assert retained.dropped_count == result.sample_counts.model - retained.retained_count
    assert retained.treated_dropped + retained.control_dropped == retained.dropped_count
    assert retained.retained_proportion == pytest.approx(retained.retained_count / 60)
    assert all(0.45 <= item.score <= 0.55 for item in retained.scores)
    assert len(result.scores) == 60
    assert result.weights is not None
    assert len(result.weights.raw) == 60
    expected = common_support_diagnostic(
        tuple(item.score for item in retained.scores),
        tuple(item.treated for item in retained.scores),
    )
    assert retained.common_support == expected


def test_explicit_weight_cap_preserves_raw_weights_and_reports_affected_ess() -> None:
    config = PropensityConfig(weight_cap=PropensityWeightCapConfig(maximum=1.5))

    result = analyze(config)

    assert result.weights is not None
    assert result.capped_weights is not None
    capped = result.capped_weights
    raw_values = tuple(item.value for item in result.weights.raw)
    capped_values = tuple(item.value for item in capped.weights)
    expected_affected = sum(value > 1.5 for value in raw_values)
    assert capped.affected_count == expected_affected
    assert capped.affected_proportion == pytest.approx(expected_affected / len(raw_values))
    assert capped_values == pytest.approx(tuple(min(value, 1.5) for value in raw_values))
    assert max(capped_values) <= 1.5
    assert any(value > 1.5 for value in raw_values)
    assert capped.ess_before == result.weights.ess
    assert capped.ess_after.overall is not None
    assert result.weights.ess.overall is not None
    assert capped.ess_after.overall >= result.weights.ess.overall
