"""Safety gates must prevent downstream observational effect estimation."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from packages.experiments.analysis.causal import IdentificationStatus
from packages.experiments.analysis.causal.ipw import (
    IPWExecutionRequest,
    IPWOutcomeBinding,
    IPWSensitivityCode,
    IPWStatus,
    IPWTreatmentEffectEstimator,
)
from packages.experiments.analysis.causal.propensity import (
    BalanceStatus,
    EffectiveSampleSizeStatus,
    OverlapStatus,
    PropensityFitStatus,
    PropensityScore,
    PropensityStatus,
    PropensityTrimmingConfig,
    PropensityWeight,
    RetainedPopulationDiagnostics,
)
from packages.experiments.analysis.causal.propensity.numerics import (
    assess_overlap,
    build_score_diagnostics,
    build_weight_diagnostics,
    common_support_diagnostic,
    compute_weight_values,
)
from tests.causal_identification_fixtures import provenance
from tests.ipw_fixtures import (
    ipw_execution,
    ipw_table,
    known_effect_rows,
    retained_ipw_execution,
)


class SpyEngine:
    def __init__(self) -> None:
        self.calls = 0

    def estimate(self, rows, execution):
        self.calls += 1
        raise AssertionError("fatal gates must prevent estimation")


def _failed_identification(execution: IPWExecutionRequest) -> IPWExecutionRequest:
    identification = execution.identification_result.model_copy(
        update={"status": IdentificationStatus.PARTIALLY_IDENTIFIED}
    )
    return execution.model_copy(update={"identification_result": identification})


def _nonconverged_propensity(execution: IPWExecutionRequest) -> IPWExecutionRequest:
    propensity = execution.propensity_result
    model_fit = propensity.model_fit.model_copy(
        update={"status": PropensityFitStatus.NON_CONVERGED, "converged": False}
    )
    return execution.model_copy(
        update={"propensity_result": propensity.model_copy(update={"model_fit": model_fit})}
    )


def _severe_overlap(execution: IPWExecutionRequest) -> IPWExecutionRequest:
    propensity = execution.propensity_result
    overlap = propensity.overlap.model_copy(update={"status": OverlapStatus.SEVERE})
    scores = tuple(
        item.model_copy(update={"score": 0.99 if item.treated else 0.01})
        for item in propensity.scores
    )
    return execution.model_copy(
        update={
            "propensity_result": propensity.model_copy(
                update={"overlap": overlap, "scores": scores}
            )
        }
    )


def _collapsed_ess(execution: IPWExecutionRequest) -> IPWExecutionRequest:
    propensity = execution.propensity_result
    assert propensity.weights is not None
    ess = propensity.weights.ess.model_copy(
        update={"status": EffectiveSampleSizeStatus.COLLAPSED}
    )
    weights = propensity.weights.model_copy(update={"ess": ess})
    return execution.model_copy(
        update={"propensity_result": propensity.model_copy(update={"weights": weights})}
    )


def _invalid_score_denominator(execution: IPWExecutionRequest) -> IPWExecutionRequest:
    propensity = execution.propensity_result
    first = propensity.scores[0]
    assert first.treated
    scores = (
        PropensityScore(unit_id=first.unit_id, treated=True, score=0.0),
        *propensity.scores[1:],
    )
    return execution.model_copy(
        update={"propensity_result": propensity.model_copy(update={"scores": scores})}
    )


def _severe_residual_balance(execution: IPWExecutionRequest) -> IPWExecutionRequest:
    propensity = execution.propensity_result
    assert propensity.balance is not None
    feature = propensity.balance.features[0]
    weighted = feature.weighted.model_copy(update={"smd": 0.30})
    changed_feature = feature.model_copy(
        update={"weighted": weighted, "status": BalanceStatus.IMBALANCED}
    )
    balance = propensity.balance.model_copy(
        update={
            "features": (changed_feature, *propensity.balance.features[1:]),
            "weighted_max_absolute_smd": 0.30,
            "weighted_above_threshold_count": 1,
        }
    )
    return execution.model_copy(
        update={"propensity_result": propensity.model_copy(update={"balance": balance})}
    )


def _propensity_not_completed(execution: IPWExecutionRequest) -> IPWExecutionRequest:
    propensity = execution.propensity_result.model_copy(
        update={"status": PropensityStatus.ABSTAINED}
    )
    return execution.model_copy(update={"propensity_result": propensity})


def _mismatched_upstream_identity(execution: IPWExecutionRequest) -> IPWExecutionRequest:
    propensity = execution.propensity_result.model_copy(update={"request_id": "other-request"})
    return execution.model_copy(update={"propensity_result": propensity})


def _missing_balance(execution: IPWExecutionRequest) -> IPWExecutionRequest:
    propensity = execution.propensity_result.model_copy(update={"balance": None})
    return execution.model_copy(update={"propensity_result": propensity})


def _missing_score_provenance(execution: IPWExecutionRequest) -> IPWExecutionRequest:
    propensity = execution.propensity_result.model_copy(update={"model_provenance": None})
    return execution.model_copy(update={"propensity_result": propensity})


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    (
        (_failed_identification, "identification.not_identified"),
        (_nonconverged_propensity, "propensity.not_converged"),
        (_severe_overlap, "overlap.fatal"),
        (_collapsed_ess, "weight.source_ess_collapsed"),
        (_invalid_score_denominator, "weight.invalid_denominator"),
        (_severe_residual_balance, "balance.severe_residual_imbalance"),
        (_propensity_not_completed, "propensity.not_completed"),
        (_mismatched_upstream_identity, "provenance.upstream_request_mismatch"),
        (_missing_balance, "balance.unavailable"),
        (_missing_score_provenance, "propensity.provenance_unavailable"),
    ),
)
def test_fatal_design_gate_abstains_without_invoking_effect_engine(
    mutate: Callable[[IPWExecutionRequest], IPWExecutionRequest],
    expected_code: str,
) -> None:
    engine = SpyEngine()

    result = IPWTreatmentEffectEstimator(engine=engine).analyze(
        mutate(ipw_execution()),
        ipw_table(),
        provenance=provenance("ipw-safety"),
    )

    expected_status = (
        IPWStatus.INVALID
        if expected_code
        in {"provenance.upstream_request_mismatch", "propensity.provenance_unavailable"}
        else IPWStatus.ABSTAINED
    )
    assert result.status is expected_status
    assert engine.calls == 0
    assert result.point_estimate is None
    assert result.test_result is None
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == expected_code


def test_invalid_outcome_alignment_stops_before_effect_engine() -> None:
    engine = SpyEngine()
    table = ipw_table().from_records(
        ({"account_id": "unmatched", "conversion": 1.0},)
    )

    result = IPWTreatmentEffectEstimator(engine=engine).analyze(
        ipw_execution(),
        table,
        provenance=provenance("ipw-invalid-outcome"),
    )

    assert result.status is IPWStatus.INVALID
    assert engine.calls == 0
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "outcome.invalid_alignment"


def test_treatment_orientation_mismatch_stops_before_effect_engine() -> None:
    engine = SpyEngine()
    records = [dict(row) for row in known_effect_rows()]
    records[0]["treated"] = 0

    result = IPWTreatmentEffectEstimator(engine=engine).analyze(
        ipw_execution(),
        ipw_table(records),
        provenance=provenance("ipw-treatment-mismatch"),
    )

    assert result.status is IPWStatus.INVALID
    assert engine.calls == 0
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "outcome.invalid_alignment"


@pytest.mark.parametrize(
    "mutate",
    (_nonconverged_propensity, _severe_overlap, _collapsed_ess),
)
def test_fatal_propensity_diagnostic_preserves_supplied_score_model_reference(
    mutate: Callable[[IPWExecutionRequest], IPWExecutionRequest],
) -> None:
    execution = mutate(ipw_execution())

    result = IPWTreatmentEffectEstimator(engine=SpyEngine()).analyze(
        execution,
        ipw_table(),
        provenance=provenance("ipw-safety-score-reference"),
    )

    assert result.score_model is not None
    assert result.score_model.configuration == execution.propensity_result.configuration
    assert result.score_model.fit_status is execution.propensity_result.model_fit.status
    assert result.score_model.converged is execution.propensity_result.model_fit.converged


@pytest.mark.parametrize(
    ("mutate", "expected_flag"),
    (
        (_nonconverged_propensity, IPWSensitivityCode.PROPENSITY_CONVERGENCE_CONCERNS),
        (_severe_overlap, IPWSensitivityCode.POOR_OVERLAP),
        (_collapsed_ess, IPWSensitivityCode.LOW_ESS),
    ),
)
def test_fatal_propensity_diagnostic_emits_structured_sensitivity_flag(
    mutate: Callable[[IPWExecutionRequest], IPWExecutionRequest],
    expected_flag: IPWSensitivityCode,
) -> None:
    result = IPWTreatmentEffectEstimator(engine=SpyEngine()).analyze(
        mutate(ipw_execution()),
        ipw_table(),
        provenance=provenance("ipw-safety-sensitivity"),
    )

    assert expected_flag in {item.code for item in result.sensitivity_flags}


def test_raw_table_count_mismatch_stops_before_effect_engine() -> None:
    engine = SpyEngine()
    records = [dict(row) for row in known_effect_rows()]
    extra = dict(records[-1])
    extra["account_id"] = "unexpected-extra-unit"
    records.append(extra)

    result = IPWTreatmentEffectEstimator(engine=engine).analyze(
        ipw_execution(),
        ipw_table(records),
        provenance=provenance("ipw-raw-count-mismatch"),
    )

    assert result.status is IPWStatus.INVALID
    assert engine.calls == 0
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "outcome.raw_count_mismatch"


@pytest.mark.parametrize("outcome_column", ("account_id", "treated", "prior_orders"))
def test_outcome_binding_cannot_alias_propensity_input_role(outcome_column: str) -> None:
    engine = SpyEngine()
    execution = ipw_execution().model_copy(
        update={"binding": IPWOutcomeBinding(outcome_column=outcome_column)}
    )

    result = IPWTreatmentEffectEstimator(engine=engine).analyze(
        execution,
        ipw_table(),
        provenance=provenance("ipw-outcome-role-conflict"),
    )

    assert result.status is IPWStatus.INVALID
    assert engine.calls == 0
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "binding.outcome_role_conflict"


def test_retained_population_must_be_exact_unchanged_configured_score_subset() -> None:
    engine = SpyEngine()
    execution = retained_ipw_execution()
    propensity = execution.propensity_result
    retained = propensity.retained
    assert retained is not None
    changed_scores = (
        retained.scores[0].model_copy(update={"score": 0.30}),
        *retained.scores[1:],
    )
    changed = RetainedPopulationDiagnostics(
        configuration=retained.configuration,
        scores=changed_scores,
        retained_count=retained.retained_count,
        treated_retained=retained.treated_retained,
        control_retained=retained.control_retained,
        dropped_count=retained.dropped_count,
        treated_dropped=retained.treated_dropped,
        control_dropped=retained.control_dropped,
        retained_proportion=retained.retained_proportion,
        common_support=common_support_diagnostic(
            tuple(item.score for item in changed_scores),
            tuple(item.treated for item in changed_scores),
        ),
        score_diagnostics=build_score_diagnostics(
            tuple(item.score for item in changed_scores),
            tuple(item.treated for item in changed_scores),
            propensity.configuration,
        ),
    )
    execution = execution.model_copy(
        update={"propensity_result": propensity.model_copy(update={"retained": changed})}
    )

    result = IPWTreatmentEffectEstimator(engine=engine).analyze(
        execution,
        ipw_table(),
        provenance=provenance("ipw-invalid-retained-scores"),
    )

    assert result.status is IPWStatus.INVALID
    assert engine.calls == 0
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "provenance.invalid_retained_population"


def test_trimming_that_destroys_overlap_abstains_before_effect_engine() -> None:
    engine = SpyEngine()
    execution = ipw_execution()
    propensity = execution.propensity_result
    changed_scores: list[PropensityScore] = []
    treated_outlier_added = False
    control_outlier_added = False
    for item in propensity.scores:
        if item.treated and not treated_outlier_added:
            score = 0.90
            treated_outlier_added = True
        elif not item.treated and not control_outlier_added:
            score = 0.10
            control_outlier_added = True
        else:
            score = 0.30 if item.treated else 0.70
        changed_scores.append(item.model_copy(update={"score": score}))
    scores = tuple(changed_scores)
    score_values = tuple(item.score for item in scores)
    treated = tuple(item.treated for item in scores)
    raw_values = compute_weight_values(score_values, treated, propensity.estimand)
    raw_weights = tuple(
        PropensityWeight(unit_id=item.unit_id, treated=item.treated, value=value)
        for item, value in zip(scores, raw_values, strict=True)
    )
    weights = build_weight_diagnostics(
        raw_weights,
        propensity.estimand,
        propensity.configuration,
    )
    support = common_support_diagnostic(score_values, treated)
    model_fit = propensity.model_fit.model_copy(update={"scores": score_values})
    overlap = assess_overlap(
        scores=score_values,
        treated=treated,
        support=support,
        model_fit=model_fit,
        weights=weights,
        estimand=propensity.estimand,
        config=propensity.configuration,
    )
    assert overlap.status in {OverlapStatus.ACCEPTABLE, OverlapStatus.WEAK}
    trimming = PropensityTrimmingConfig(lower=0.20, upper=0.80)
    selected = tuple(
        item for item in scores if trimming.lower <= item.score <= trimming.upper
    )
    selected_treated = sum(item.treated for item in selected)
    selected_scores = tuple(item.score for item in selected)
    selected_arms = tuple(item.treated for item in selected)
    retained = RetainedPopulationDiagnostics(
        configuration=trimming,
        scores=selected,
        retained_count=len(selected),
        treated_retained=selected_treated,
        control_retained=len(selected) - selected_treated,
        dropped_count=len(scores) - len(selected),
        treated_dropped=1,
        control_dropped=1,
        retained_proportion=len(selected) / len(scores),
        common_support=common_support_diagnostic(selected_scores, selected_arms),
        score_diagnostics=build_score_diagnostics(
            selected_scores,
            selected_arms,
            propensity.configuration,
        ),
    )
    assert propensity.model_provenance is not None
    changed = propensity.model_copy(
        update={
            "configuration": propensity.configuration.model_copy(
                update={"trimming": trimming}
            ),
            "model_fit": model_fit,
            "model_provenance": propensity.model_provenance.model_copy(
                update={"trimming_enabled": True}
            ),
            "scores": scores,
            "score_diagnostics": build_score_diagnostics(
                score_values, treated, propensity.configuration
            ),
            "common_support": support,
            "overlap": overlap,
            "weights": weights,
            "retained": retained,
        }
    )
    execution = execution.model_copy(update={"propensity_result": changed})

    result = IPWTreatmentEffectEstimator(engine=engine).analyze(
        execution,
        ipw_table(),
        provenance=provenance("ipw-selected-no-overlap"),
    )

    assert result.status is IPWStatus.ABSTAINED
    assert engine.calls == 0
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "overlap.selected_fatal"
    assert result.overlap.status is OverlapStatus.SEVERE
    flag = next(
        item
        for item in result.sensitivity_flags
        if item.code is IPWSensitivityCode.POOR_OVERLAP
    )
    assert flag.severity.value == "fatal"


def test_balance_gate_derives_severity_from_feature_level_smd() -> None:
    engine = SpyEngine()
    execution = _severe_residual_balance(ipw_execution())
    propensity = execution.propensity_result
    assert propensity.balance is not None
    contradictory = propensity.balance.model_copy(
        update={"weighted_max_absolute_smd": 0.0, "weighted_above_threshold_count": 0}
    )
    execution = execution.model_copy(
        update={"propensity_result": propensity.model_copy(update={"balance": contradictory})}
    )

    result = IPWTreatmentEffectEstimator(engine=engine).analyze(
        execution,
        ipw_table(),
        provenance=provenance("ipw-contradictory-balance"),
    )

    assert result.status is IPWStatus.INVALID
    assert engine.calls == 0
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "balance.inconsistent_diagnostics"


def test_severe_residual_balance_emits_fatal_sensitivity_flag() -> None:
    result = IPWTreatmentEffectEstimator(engine=SpyEngine()).analyze(
        _severe_residual_balance(ipw_execution()),
        ipw_table(),
        provenance=provenance("ipw-severe-balance-flag"),
    )

    flag = next(
        item
        for item in result.sensitivity_flags
        if item.code is IPWSensitivityCode.RESIDUAL_IMBALANCE
    )
    assert flag.severity.value == "fatal"
