"""Issue #101 IPW ATE/ATT accuracy and fatal-gate reliability."""

from __future__ import annotations

import math

import pytest

from packages.evals.statistical.observational_fixtures import run_ipw_fixture
from packages.experiments.analysis.causal.ipw import IPWStatus, IPWVarianceMethod
from packages.experiments.analysis.causal.propensity import OverlapStatus


@pytest.mark.parametrize(
    ("fixture_id", "estimand", "target", "treated_mean", "control_mean", "effect"),
    [
        ("ipw_ate_known_effect", "ate", "full", 9.0, 5.0, 4.0),
        ("ipw_att_known_effect", "att", "treated", 13.2, 8.0, 5.2),
    ],
)
def test_ipw_known_effect_references_preserve_estimand_and_weighted_means(
    fixture_id: str,
    estimand: str,
    target: str,
    treated_mean: float,
    control_mean: float,
    effect: float,
) -> None:
    result = run_ipw_fixture(fixture_id)

    assert result.status is IPWStatus.COMPLETED
    assert result.estimand is not None
    assert result.estimand.estimand_type.value == estimand
    assert result.target_population is not None
    assert result.target_population.kind.value == target
    assert result.treatment_mean == pytest.approx(treated_mean, abs=1e-12)
    assert result.control_mean == pytest.approx(control_mean, abs=1e-12)
    assert result.point_estimate == pytest.approx(effect, abs=1e-12)
    assert result.weights is not None
    assert result.weights.estimand.value == estimand
    assert result.weights.raw_treated_formula == ("1/e(X)" if estimand == "ate" else "1")
    assert result.weights.raw_control_formula == (
        "1/(1-e(X))" if estimand == "ate" else "e(X)/(1-e(X))"
    )
    assert result.test_result is not None
    assert result.test_result.variance_method is IPWVarianceMethod.FIXED_PROPENSITY_HAJEK_HC1
    assert result.test_result.confidence_interval.confidence_level == 0.95
    assert math.isfinite(result.test_result.standard_error)
    assert result.test_result.confidence_interval.lower <= result.point_estimate
    assert result.test_result.confidence_interval.upper >= result.point_estimate


def test_ipw_null_effect_reference_is_exactly_null() -> None:
    result = run_ipw_fixture("ipw_ate_null_effect")

    assert result.status is IPWStatus.COMPLETED
    assert result.point_estimate == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize(
    "fixture_id",
    ["ipw_ate_extreme_scores", "ipw_att_extreme_control_weights"],
)
def test_extreme_but_permitted_weights_remain_explicit_advisories(fixture_id: str) -> None:
    result = run_ipw_fixture(fixture_id)

    assert result.status is IPWStatus.COMPLETED
    assert result.weights is not None
    assert result.weights.raw.overall.maximum > 10.0
    assert math.isfinite(result.weights.raw.overall.maximum)
    assert result.overlap.status is OverlapStatus.WEAK
    assert {
        "overlap.weak_extreme_scores",
        "weight.extreme_tail",
    } & set(result.overlap.diagnostic_codes)


def test_ipw_stabilization_and_clipping_are_explicit_in_provenance() -> None:
    stabilized = run_ipw_fixture("ipw_ate_stabilized")
    clipped = run_ipw_fixture("ipw_ate_clipped")

    assert stabilized.status is IPWStatus.COMPLETED
    assert stabilized.configuration.stabilized is True
    assert stabilized.weights is not None
    assert stabilized.weights.stabilized is not None
    assert stabilized.weights.stabilization_rule is not None
    assert clipped.status is IPWStatus.COMPLETED
    assert clipped.configuration.clipping is not None
    assert clipped.weights is not None
    assert clipped.weights.clipping.enabled is True
    assert clipped.weights.clipping.affected_count > 0


class CountingEngine:
    def __init__(self) -> None:
        self.calls = 0

    def estimate(self, rows, execution):
        self.calls += 1
        raise AssertionError("fatal upstream diagnostics must prevent engine invocation")


@pytest.mark.parametrize(
    "fixture_id",
    [
        "ipw_failed_identification",
        "ipw_propensity_nonconvergence",
        "ipw_failed_overlap",
        "ipw_low_ess",
        "ipw_att_failed_overlap",
        "ipw_att_low_ess",
    ],
)
def test_fatal_upstream_diagnostic_blocks_engine_invocation(fixture_id: str) -> None:
    engine = CountingEngine()

    result = run_ipw_fixture(fixture_id, engine=engine)

    assert engine.calls == 0
    assert result.status in {IPWStatus.ABSTAINED, IPWStatus.INVALID}
    assert result.point_estimate is None
    assert result.test_result is None
    assert result.abstention_reason is not None


def test_ipw_repeated_results_are_deterministic() -> None:
    first = run_ipw_fixture("ipw_att_known_effect")
    repeated = run_ipw_fixture("ipw_att_known_effect")

    assert first.model_dump(mode="json") == repeated.model_dump(mode="json")
