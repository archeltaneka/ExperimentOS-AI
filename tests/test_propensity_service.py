"""End-to-end deterministic propensity diagnostic service behavior."""

from __future__ import annotations

from dataclasses import fields, is_dataclass

import pytest

from packages.experiments.analysis.causal import CausalEstimandKind
from packages.experiments.analysis.causal.propensity import (
    DeterministicLogisticPropensityEstimator,
    EffectiveSampleSizeStatus,
    OverlapStatus,
    PropensityConfig,
    PropensityFitStatus,
    PropensityModelFit,
    PropensityStatus,
)
from tests.causal_identification_fixtures import provenance
from tests.propensity_fixtures import (
    extreme_weight_rows,
    good_overlap_rows,
    propensity_execution,
    propensity_request,
    propensity_table,
    separation_rows,
    weak_overlap_rows,
)


def analyze(rows=None, *, estimand=CausalEstimandKind.ATE, config=None, adapter=None):
    execution = propensity_execution(
        analysis_request=propensity_request(estimand_kind=estimand),
        config=config,
    )
    return DeterministicLogisticPropensityEstimator(adapter=adapter).fit_predict(
        execution,
        propensity_table(rows or good_overlap_rows()),
        provenance=provenance("propensity-input"),
    )


def test_good_overlap_returns_scores_weights_balance_ess_and_full_provenance() -> None:
    result = analyze()

    assert result.status is PropensityStatus.COMPLETED
    assert result.estimand is CausalEstimandKind.ATE
    assert result.model_fit.status is PropensityFitStatus.CONVERGED
    assert len(result.scores) == 60
    assert tuple(item.unit_id for item in result.scores[:4]) == (
        "c-00",
        "t-00",
        "c-01",
        "t-01",
    )
    assert all(0.0 <= item.score <= 1.0 for item in result.scores)
    assert result.score_diagnostics.overall.count == 60
    assert result.score_diagnostics.treated.count == 30
    assert result.score_diagnostics.control.count == 30
    assert result.common_support.lower is not None
    assert result.common_support.upper is not None
    assert result.overlap.status in {OverlapStatus.ACCEPTABLE, OverlapStatus.WEAK}
    assert result.weights is not None
    assert len(result.weights.raw) == 60
    assert result.weights.ess.status is EffectiveSampleSizeStatus.ACCEPTABLE
    assert result.balance.weighted_max_absolute_smd < result.balance.raw_max_absolute_smd
    assert result.balance.improved_count > 0
    assert result.model_provenance.solver == "lbfgs"
    assert result.model_provenance.penalty == "l2"
    assert result.model_provenance.l1_ratio == 0.0
    assert result.model_provenance.feature_names == result.encoding.model_feature_names
    assert result.model_provenance.treated_value == 1
    assert result.model_provenance.control_value == 0
    assert result.model_provenance.score_orientation == "P(T=1 | X), T=1 is treated_value"
    assert result.abstention_reason is None
    assert "effect" not in type(result).model_fields
    assert "effect_estimate" not in type(result).model_fields


def test_repeated_runs_have_identical_owned_results_except_no_duration_state() -> None:
    first = analyze()
    second = analyze()

    assert first == second
    assert first.model_dump_json() == second.model_dump_json()


def test_weight_formula_matches_declared_estimand_and_score_orientation() -> None:
    ate = analyze(estimand=CausalEstimandKind.ATE)
    att = analyze(estimand=CausalEstimandKind.ATT)

    assert ate.weights is not None
    assert att.weights is not None
    for score, ate_weight, att_weight in zip(
        ate.scores,
        ate.weights.raw,
        att.weights.raw,
        strict=True,
    ):
        if score.treated:
            assert ate_weight.value == pytest.approx(1.0 / score.score)
            assert att_weight.value == 1.0
        else:
            assert ate_weight.value == pytest.approx(1.0 / (1.0 - score.score))
            assert att_weight.value == pytest.approx(score.score / (1.0 - score.score))


def test_weak_overlap_surfaces_warning_or_blocking_status_and_reduced_ess() -> None:
    result = analyze(weak_overlap_rows())

    assert result.overlap.status in {OverlapStatus.WEAK, OverlapStatus.SEVERE}
    assert result.weights is not None
    assert result.weights.ess.overall_ratio < 1.0
    assert result.weights.overall.maximum > result.weights.overall.median
    assert any(item.code.startswith("overlap.") for item in result.diagnostics)


def test_separation_abstains_without_presenting_weights_as_usable() -> None:
    result = analyze(separation_rows())

    assert result.status is PropensityStatus.ABSTAINED
    assert result.overlap.status is OverlapStatus.SEVERE
    assert result.abstention_reason is not None
    assert any(
        item.code in {"model.separation", "overlap.empty_common_support"}
        for item in result.diagnostics
    )


def test_extreme_weight_fixture_reports_tail_and_ess_loss() -> None:
    result = analyze(extreme_weight_rows())

    assert result.weights is not None
    assert result.weights.extreme_weight_count >= 1
    assert result.weights.overall.maximum > 10.0
    assert result.weights.ess.overall_ratio < 0.75
    assert any(item.code == "weight.extreme_tail" for item in result.diagnostics)


class NonConvergingAdapter:
    def fit_predict(self, encoded, config):
        return PropensityModelFit(
            status=PropensityFitStatus.NON_CONVERGED,
            converged=False,
            scores=(),
            classes=(0, 1),
            iteration_count=config.maximum_iterations,
            solver=config.solver,
            warning_codes=("model.convergence_failure",),
            sklearn_version="test-stub",
        )


def test_deterministic_adapter_convergence_failure_abstains_without_scores() -> None:
    result = analyze(adapter=NonConvergingAdapter())

    assert result.status is PropensityStatus.ABSTAINED
    assert result.scores == ()
    assert result.weights is None
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "model.convergence_failure"


def test_configured_ess_requirement_can_block_downstream_readiness() -> None:
    config = PropensityConfig(
        minimum_effective_sample_size=29.5,
        minimum_ess_ratio=0.99,
    )

    result = analyze(config=config)

    assert result.status is PropensityStatus.ABSTAINED
    assert result.weights is not None
    assert result.weights.ess.status is EffectiveSampleSizeStatus.COLLAPSED
    assert result.abstention_reason is not None


def test_result_boundary_contains_no_dataclass_or_third_party_estimator() -> None:
    result = analyze()

    def inspect(value: object) -> None:
        assert not is_dataclass(value) or not any(
            field.name in {"estimator", "coef_"} for field in fields(value)
        )
        assert value.__class__.__module__.split(".")[0] not in {"sklearn", "numpy"}
        if hasattr(value, "model_dump"):
            inspect(value.model_dump(mode="python"))
        elif isinstance(value, dict):
            for item in value.values():
                inspect(item)
        elif isinstance(value, (tuple, list)):
            for item in value:
                inspect(item)

    inspect(result)


def test_zero_variance_numeric_covariate_is_reported_as_advisory() -> None:
    rows = [dict(row, prior_orders=7.0) for row in good_overlap_rows()]

    result = analyze(rows)

    assert any(item.code == "encoding.zero_variance_numeric" for item in result.diagnostics)
    assert any(item.code == "encoding.zero_variance_numeric" for item in result.warnings)
