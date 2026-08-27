"""Deterministic issue-100 fixtures with independently declared propensity scores."""

from __future__ import annotations

from collections.abc import Sequence

from packages.experiments.analysis import (
    AnalysisTable,
    MetricDefinition,
    MetricType,
    MetricUnit,
    OutcomeDirection,
    OutcomeMetric,
    UnitDimension,
    ValueScale,
)
from packages.experiments.analysis.causal import (
    CausalEstimandKind,
    CausalIdentificationService,
    CausalOutcome,
    EffectScale,
    ObservationalAnalysisRequest,
)
from packages.experiments.analysis.causal.ipw import (
    IPWConfig,
    IPWExecutionRequest,
    IPWOutcomeBinding,
)
from packages.experiments.analysis.causal.propensity import (
    BalanceDiagnostics,
    BalanceStatus,
    CovariateBalanceDiagnostic,
    DeterministicLogisticPropensityEstimator,
    PropensityResult,
    PropensityScore,
    PropensityStatus,
    PropensityTrimmingConfig,
    PropensityWeight,
    RetainedPopulationDiagnostics,
    StandardizedMeanDifference,
)
from packages.experiments.analysis.causal.propensity.numerics import (
    assess_overlap,
    build_score_diagnostics,
    build_weight_diagnostics,
    common_support_diagnostic,
    compute_weight_values,
)
from tests.causal_identification_fixtures import provenance
from tests.propensity_fixtures import propensity_execution, propensity_request, propensity_table


def known_effect_rows(*, binary_null: bool = False) -> tuple[dict[str, object], ...]:
    """Return two exact propensity strata with true ATE 4 and ATT 5."""
    rows: list[dict[str, object]] = []
    strata = (
        ("low", 0.25, 10, 30, 0.0, 2.0),
        ("high", 0.75, 30, 10, 10.0, 6.0),
    )
    for label, _score, treated_count, control_count, baseline, effect in strata:
        for index in range(treated_count):
            rows.append(
                {
                    "account_id": f"{label}-t-{index:02d}",
                    "treated": 1,
                    "country": label,
                    "prior_orders": 0.0 if label == "low" else 1.0,
                    "conversion": (
                        (0 if label == "low" else 1)
                        if binary_null
                        else baseline + effect
                    ),
                }
            )
        for index in range(control_count):
            rows.append(
                {
                    "account_id": f"{label}-c-{index:02d}",
                    "treated": 0,
                    "country": label,
                    "prior_orders": 0.0 if label == "low" else 1.0,
                    "conversion": (
                        0 if binary_null and label == "low" else 1 if binary_null else baseline
                    ),
                }
            )
    return tuple(rows)


def ipw_table(rows: Sequence[dict[str, object]] | None = None) -> AnalysisTable:
    return AnalysisTable.from_records(tuple(rows or known_effect_rows()))


def ipw_request(
    *,
    estimand: CausalEstimandKind = CausalEstimandKind.ATE,
    binary: bool = False,
) -> ObservationalAnalysisRequest:
    source = propensity_request(estimand_kind=estimand)
    if binary:
        return source
    metric = OutcomeMetric(
        metric=MetricDefinition(
            metric_id="conversion",
            label="Continuous outcome",
            metric_type=MetricType.CONTINUOUS,
            unit=MetricUnit(
                dimension=UnitDimension.DIMENSIONLESS,
                value_scale=ValueScale.RAW,
                symbol="units",
                scale_to_base_unit=1.0,
            ),
        ),
        direction=OutcomeDirection.INCREASE,
    )
    outcome = CausalOutcome(variable_id="conversion", metric=metric)
    declared_estimand = source.identification.estimand
    assert declared_estimand is not None
    updated_estimand = declared_estimand.model_copy(
        update={"effect_scale": EffectScale.MEAN_DIFFERENCE}
    )
    return source.model_copy(
        update={
            "identification": source.identification.model_copy(
                update={"estimand": updated_estimand, "outcome": outcome}
            )
        }
    )


def exact_propensity_result(
    *,
    estimand: CausalEstimandKind = CausalEstimandKind.ATE,
    binary: bool = False,
) -> PropensityResult:
    """Return a completed issue-99 result with exact externally declared scores."""
    request = ipw_request(estimand=estimand, binary=binary)
    rows = known_effect_rows(binary_null=binary)
    execution = propensity_execution(analysis_request=request)
    base = DeterministicLogisticPropensityEstimator().fit_predict(
        execution,
        propensity_table(rows),
        provenance=provenance("ipw-score-source"),
    )
    assert base.status is PropensityStatus.COMPLETED

    score_values = tuple(0.25 if str(row["account_id"]).startswith("low") else 0.75 for row in rows)
    treated = tuple(row["treated"] == 1 for row in rows)
    unit_ids = tuple(str(row["account_id"]) for row in rows)
    scores = tuple(
        PropensityScore(unit_id=unit_id, treated=arm, score=score)
        for unit_id, arm, score in zip(unit_ids, treated, score_values, strict=True)
    )
    raw_values = compute_weight_values(score_values, treated, estimand)
    raw_weights = tuple(
        PropensityWeight(unit_id=unit_id, treated=arm, value=weight)
        for unit_id, arm, weight in zip(unit_ids, treated, raw_values, strict=True)
    )
    weight_diagnostics = build_weight_diagnostics(
        raw_weights,
        estimand,
        execution.configuration,
    )
    model_fit = base.model_fit.model_copy(update={"scores": score_values})
    support = common_support_diagnostic(score_values, treated)
    overlap = assess_overlap(
        scores=score_values,
        treated=treated,
        support=support,
        model_fit=model_fit,
        weights=weight_diagnostics,
        estimand=estimand,
        config=execution.configuration,
    )
    assert base.balance is not None
    weighted_mean = 0.5 if estimand is CausalEstimandKind.ATE else None
    weighted_variance = 0.25 if estimand is CausalEstimandKind.ATE else None
    features = tuple(
        CovariateBalanceDiagnostic(
            variable_id=item.variable_id,
            feature_name=item.feature_name,
            raw=item.raw,
            weighted=StandardizedMeanDifference(
                available=True,
                treated_mean=(
                    weighted_mean
                    if weighted_mean is not None
                    else item.raw.treated_mean
                ),
                control_mean=(
                    weighted_mean
                    if weighted_mean is not None
                    else item.raw.treated_mean
                ),
                treated_variance=(
                    weighted_variance
                    if weighted_variance is not None
                    else item.raw.treated_variance
                ),
                control_variance=(
                    weighted_variance
                    if weighted_variance is not None
                    else item.raw.treated_variance
                ),
                smd=0.0,
            ),
            status=BalanceStatus.BALANCED,
        )
        for item in base.balance.features
    )
    raw_values = tuple(abs(item.raw.smd) for item in features if item.raw.smd is not None)
    balance = BalanceDiagnostics(
        features=features,
        raw_max_absolute_smd=max(raw_values, default=0.0),
        weighted_max_absolute_smd=0.0,
        raw_above_threshold_count=sum(
            value > execution.configuration.balance_threshold for value in raw_values
        ),
        weighted_above_threshold_count=0,
        improved_count=sum(value > 0.0 for value in raw_values),
        worsened_count=0,
    )
    return PropensityResult.model_validate(
        base.model_dump(mode="python")
        | {
            "model_fit": model_fit,
            "scores": scores,
            "score_diagnostics": build_score_diagnostics(
                score_values,
                treated,
                execution.configuration,
            ),
            "common_support": support,
            "overlap": overlap,
            "weights": weight_diagnostics,
            "retained": None,
            "capped_weights": None,
            "balance": balance,
            "diagnostics": (),
            "warnings": (),
            "abstention_reason": None,
        }
    )


def ipw_execution(
    *,
    estimand: CausalEstimandKind = CausalEstimandKind.ATE,
    binary: bool = False,
    config: IPWConfig | None = None,
) -> IPWExecutionRequest:
    request = ipw_request(estimand=estimand, binary=binary)
    return IPWExecutionRequest(
        identification_result=CausalIdentificationService().identify(request),
        propensity_result=exact_propensity_result(estimand=estimand, binary=binary),
        binding=IPWOutcomeBinding(outcome_column="conversion"),
        configuration=config or IPWConfig(),
    )


def retained_ipw_execution() -> IPWExecutionRequest:
    """Return an execution with an explicit exact upstream retained population."""
    execution = ipw_execution()
    propensity = execution.propensity_result
    trimming = PropensityTrimmingConfig(lower=0.20, upper=0.80)
    selected = tuple(
        item for item in propensity.scores if trimming.lower <= item.score <= trimming.upper
    )
    selected_treated = sum(item.treated for item in selected)
    retained = RetainedPopulationDiagnostics(
        configuration=trimming,
        scores=selected,
        retained_count=len(selected),
        treated_retained=selected_treated,
        control_retained=len(selected) - selected_treated,
        dropped_count=len(propensity.scores) - len(selected),
        treated_dropped=propensity.sample_counts.model_treated - selected_treated,
        control_dropped=(
            propensity.sample_counts.model_control - (len(selected) - selected_treated)
        ),
        retained_proportion=len(selected) / len(propensity.scores),
        common_support=common_support_diagnostic(
            tuple(item.score for item in selected),
            tuple(item.treated for item in selected),
        ),
        score_diagnostics=build_score_diagnostics(
            tuple(item.score for item in selected),
            tuple(item.treated for item in selected),
            propensity.configuration,
        ),
    )
    configuration = propensity.configuration.model_copy(update={"trimming": trimming})
    assert propensity.model_provenance is not None
    model_provenance = propensity.model_provenance.model_copy(
        update={"trimming_enabled": True}
    )
    updated = propensity.model_copy(
        update={
            "configuration": configuration,
            "model_provenance": model_provenance,
            "retained": retained,
        }
    )
    return execution.model_copy(update={"propensity_result": updated})
