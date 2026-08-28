"""Explicit stabilization, clipping, ESS, and sensitivity evidence."""

from __future__ import annotations

import pytest

from packages.experiments.analysis.causal import CausalEstimandKind
from packages.experiments.analysis.causal.ipw import (
    IPWBalanceStatus,
    IPWConfig,
    IPWSensitivityCode,
    IPWTreatmentEffectEstimator,
    IPWWeightClippingConfig,
)
from packages.experiments.analysis.causal.propensity import (
    BalanceStatus,
)
from tests.causal_identification_fixtures import provenance
from tests.ipw_fixtures import (
    ipw_execution,
    ipw_table,
    known_effect_rows,
    retained_ipw_execution,
)


def test_ate_stabilization_is_explicit_and_preserves_raw_weights() -> None:
    result = IPWTreatmentEffectEstimator().analyze(
        ipw_execution(
            estimand=CausalEstimandKind.ATE,
            config=IPWConfig(stabilized=True),
        ),
        ipw_table(),
        provenance=provenance("ipw-stabilized"),
    )

    assert result.weights is not None
    assert result.weights.stabilization_rule == "ATE: treated=p/e, control=(1-p)/(1-e)"
    assert result.weights.treatment_prevalence == pytest.approx(0.5)
    assert result.weights.stabilized is not None
    raw = tuple(item.value for item in result.weights.raw.weights)
    stabilized = tuple(item.value for item in result.weights.stabilized.weights)
    assert stabilized == pytest.approx(tuple(value * 0.5 for value in raw))
    assert result.point_estimate == pytest.approx(4.0)


def test_clipping_is_disabled_by_default_and_never_changes_raw_diagnostics() -> None:
    result = IPWTreatmentEffectEstimator().analyze(
        ipw_execution(),
        ipw_table(),
        provenance=provenance("ipw-unclipped"),
    )

    assert result.weights is not None
    assert result.weights.clipping.enabled is False
    assert result.weights.clipping.affected_count == 0
    assert result.weights.estimation.weights == result.weights.raw.weights


def test_explicit_clipping_reports_estimate_and_ess_impact() -> None:
    result = IPWTreatmentEffectEstimator().analyze(
        ipw_execution(
            config=IPWConfig(
                clipping=IPWWeightClippingConfig(maximum=2.0),
                severe_balance_threshold=2.0,
            ),
        ),
        ipw_table(),
        provenance=provenance("ipw-clipped"),
    )

    assert result.weights is not None
    clipping = result.weights.clipping
    assert clipping.enabled is True
    assert clipping.affected_count == 20
    assert clipping.treated_affected_count == 10
    assert clipping.control_affected_count == 10
    assert clipping.affected_proportion == pytest.approx(0.25)
    assert clipping.maximum_before == pytest.approx(4.0)
    assert clipping.maximum_after == pytest.approx(2.0)
    assert clipping.ess_after.overall > clipping.ess_before.overall
    assert max(item.value for item in result.weights.raw.weights) == pytest.approx(4.0)
    assert max(item.value for item in result.weights.estimation.weights) == pytest.approx(2.0)
    assert result.point_estimate == pytest.approx(8.0)
    assert IPWSensitivityCode.HEAVY_CLIPPING in {item.code for item in result.sensitivity_flags}
    ipw_provenance = next(
        item for item in result.provenance if item.source_id == "inverse_probability_weighting"
    )
    assert "formula=ate_inverse_probability" in ipw_provenance.source_version
    assert "clip_max=2.0" in ipw_provenance.source_version
    assert "balance_threshold=0.1" in ipw_provenance.source_version
    assert "minimum_ess=10.0" in ipw_provenance.source_version


def test_unverified_identification_assumptions_remain_a_sensitivity_flag() -> None:
    result = IPWTreatmentEffectEstimator().analyze(
        ipw_execution(),
        ipw_table(),
        provenance=provenance("ipw-assumptions"),
    )

    assert IPWSensitivityCode.IDENTIFICATION_ASSUMPTIONS_UNVERIFIED in {
        item.code for item in result.sensitivity_flags
    }


def test_upstream_retained_population_is_used_and_disclosed_without_hidden_trimming() -> None:
    execution = retained_ipw_execution()
    rows = [dict(row) for row in known_effect_rows()]
    for row in rows:
        unit_id = str(row["account_id"])
        if unit_id.startswith("low-"):
            index = int(unit_id.rsplit("-", maxsplit=1)[1])
            row["conversion"] = float(row["conversion"]) + (1.0 if index % 2 else -1.0)

    result = IPWTreatmentEffectEstimator().analyze(
        execution,
        ipw_table(rows),
        provenance=provenance("ipw-retained"),
    )

    assert result.sample_counts.raw_count == 80
    assert result.sample_counts.selected_count == 80
    assert result.sample_counts.upstream_trimming_enabled is True
    assert result.sample_counts.upstream_trimmed_count == 0
    assert result.weights is not None
    assert len(result.weights.estimation.weights) == 80
    assert result.balance is not None
    assert result.balance.raw_max_absolute_smd > 1.0
    assert result.balance.weighted_max_absolute_smd == pytest.approx(0.0)


def test_advisory_residual_imbalance_is_preserved_without_claiming_success() -> None:
    execution = ipw_execution()
    propensity = execution.propensity_result
    assert propensity.balance is not None
    feature = propensity.balance.features[0]
    weighted = feature.weighted.model_copy(update={"smd": 0.15})
    changed_feature = feature.model_copy(
        update={"weighted": weighted, "status": BalanceStatus.IMBALANCED}
    )
    balance = propensity.balance.model_copy(
        update={
            "features": (changed_feature, *propensity.balance.features[1:]),
            "weighted_max_absolute_smd": 0.15,
            "weighted_above_threshold_count": 1,
        }
    )
    execution = execution.model_copy(
        update={"propensity_result": propensity.model_copy(update={"balance": balance})}
    )

    result = IPWTreatmentEffectEstimator().analyze(
        execution,
        ipw_table(),
        provenance=provenance("ipw-balance-concern"),
    )

    assert result.balance_status is IPWBalanceStatus.CONCERN
    assert IPWSensitivityCode.RESIDUAL_IMBALANCE in {item.code for item in result.sensitivity_flags}
