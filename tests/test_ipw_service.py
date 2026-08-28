"""End-to-end deterministic observational IPW treatment-effect behavior."""

from __future__ import annotations

import math

import pytest

from packages.experiments.analysis.causal import (
    CausalEstimandKind,
    EffectScale,
    TargetPopulationKind,
)
from packages.experiments.analysis.causal.ipw import (
    IPWCausalStatus,
    IPWConfig,
    IPWStatus,
    IPWTreatmentEffectEstimator,
    IPWWeightClippingConfig,
)
from packages.experiments.analysis.causal.ipw.numerics import IPWNumericalError
from packages.experiments.analysis.causal.propensity import OverlapStatus
from tests.causal_identification_fixtures import provenance
from tests.ipw_fixtures import (
    ipw_execution,
    ipw_table,
    known_effect_rows,
    retained_ipw_execution,
)


class FailingNumericalEngine:
    def estimate(self, rows, execution):
        del rows, execution
        raise IPWNumericalError("deterministic test failure")


def test_known_effect_ate_matches_hand_reference() -> None:
    result = IPWTreatmentEffectEstimator().analyze(
        ipw_execution(estimand=CausalEstimandKind.ATE),
        ipw_table(),
        provenance=provenance("ipw-outcomes"),
    )

    assert result.status is IPWStatus.COMPLETED
    assert result.causal_status is IPWCausalStatus.CONDITIONAL_ON_DECLARED_ASSUMPTIONS
    assert result.estimand.estimand_type is CausalEstimandKind.ATE
    assert result.target_population.kind is TargetPopulationKind.FULL
    assert result.effect_scale is EffectScale.MEAN_DIFFERENCE
    assert result.treatment_mean == pytest.approx(9.0)
    assert result.control_mean == pytest.approx(5.0)
    assert result.point_estimate == pytest.approx(4.0)
    assert result.test_result is not None
    assert math.isfinite(result.test_result.standard_error)


def test_known_effect_att_preserves_treated_target_semantics() -> None:
    result = IPWTreatmentEffectEstimator().analyze(
        ipw_execution(estimand=CausalEstimandKind.ATT),
        ipw_table(),
        provenance=provenance("ipw-outcomes"),
    )

    assert result.status is IPWStatus.COMPLETED
    assert result.estimand.estimand_type is CausalEstimandKind.ATT
    assert result.target_population.kind is TargetPopulationKind.TREATED
    assert result.treatment_mean == pytest.approx(12.5)
    assert result.control_mean == pytest.approx(7.5)
    assert result.point_estimate == pytest.approx(5.0)
    assert all(item.value == 1.0 for item in result.weights.raw.weights if item.treated)


def test_valid_binary_null_effect_returns_finite_uncertainty_without_causal_proof() -> None:
    result = IPWTreatmentEffectEstimator().analyze(
        ipw_execution(estimand=CausalEstimandKind.ATE, binary=True),
        ipw_table(known_effect_rows(binary_null=True)),
        provenance=provenance("ipw-binary-null"),
    )

    assert result.status is IPWStatus.COMPLETED
    assert result.point_estimate == pytest.approx(0.0)
    assert result.test_result is not None
    assert math.isfinite(result.test_result.standard_error)
    assert result.test_result.p_value == pytest.approx(1.0)
    assert result.causal_status is IPWCausalStatus.CONDITIONAL_ON_DECLARED_ASSUMPTIONS


def test_estimator_reuses_supplied_scores_without_hidden_propensity_refit(monkeypatch) -> None:
    execution = ipw_execution()

    def fail_if_called(*args, **kwargs):
        raise AssertionError("IPW must not fit a propensity model")

    monkeypatch.setattr(
        "packages.experiments.analysis.causal.propensity."
        "DeterministicLogisticPropensityEstimator.fit_predict",
        fail_if_called,
    )

    result = IPWTreatmentEffectEstimator().analyze(
        execution,
        ipw_table(),
        provenance=provenance("ipw-no-refit"),
    )

    assert result.status is IPWStatus.COMPLETED
    assert result.score_model is not None
    assert result.score_model.model_provenance == execution.propensity_result.model_provenance
    assert set(execution.identification_result.provenance).issubset(result.provenance)
    assert set(execution.propensity_result.provenance).issubset(result.provenance)


def test_numerical_abstention_preserves_selected_overlap_and_recomputed_balance() -> None:
    execution = retained_ipw_execution().model_copy(
        update={
            "configuration": IPWConfig(
                clipping=IPWWeightClippingConfig(maximum=2.0),
                severe_balance_threshold=2.0,
            )
        }
    )
    source_balance = execution.propensity_result.balance
    assert source_balance is not None

    result = IPWTreatmentEffectEstimator(engine=FailingNumericalEngine()).analyze(
        execution,
        ipw_table(),
        provenance=provenance("ipw-numerical-abstention-selected-diagnostics"),
    )

    assert result.status is IPWStatus.ABSTAINED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "inference.unavailable"
    assert result.balance is not None
    assert result.balance != source_balance
    assert result.balance.weighted_max_absolute_smd > 0.0
    assert result.overlap.status in {OverlapStatus.ACCEPTABLE, OverlapStatus.WEAK}
