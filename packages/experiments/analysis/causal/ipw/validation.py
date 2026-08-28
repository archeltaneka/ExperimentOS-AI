"""Deterministic safety gates for observational IPW estimation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from numbers import Real
from typing import cast

from ...base import ScalarValue
from ...metrics import MetricType
from ...provenance import DiagnosticSeverity
from ...validation.table import AnalysisTable
from ..adjustment import AdjustmentValidationStatus
from ..estimands import CausalEstimandKind, EffectScale, TargetPopulationKind
from ..models import IdentificationStatus
from ..propensity import (
    BalanceDiagnostics,
    BalanceStatus,
    EffectiveSampleSizeStatus,
    OverlapDiagnostic,
    OverlapStatus,
    PropensityDiagnosticStatus,
    PropensityFeatureKind,
    PropensityFitStatus,
    PropensityScore,
    PropensityStatus,
    PropensityWeight,
)
from ..propensity.encoding import EncodedPropensityData
from ..propensity.numerics import (
    assess_overlap,
    build_balance_diagnostics,
    build_ess_diagnostic,
    build_score_diagnostics,
    build_weight_diagnostics,
    common_support_diagnostic,
)
from .models import (
    IPWBalanceStatus,
    IPWDiagnostic,
    IPWDiagnosticCategory,
    IPWExecutionRequest,
)
from .numerics import (
    IPWNumericalError,
    clip_weights,
    compute_raw_weights,
    stabilize_weights,
)


class IPWValidationDisposition(StrEnum):
    """Terminal pre-estimation validation state."""

    VALID = "valid"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class ValidatedIPWRow:
    """One aligned selected unit retained only inside the estimator."""

    unit_id: ScalarValue
    treated: bool
    score: float
    outcome: float


@dataclass(frozen=True, slots=True)
class IPWValidationResult:
    """Internal aligned inputs plus privacy-safe validation evidence."""

    disposition: IPWValidationDisposition
    rows: tuple[ValidatedIPWRow, ...]
    balance_status: IPWBalanceStatus
    diagnostics: tuple[IPWDiagnostic, ...]
    balance: BalanceDiagnostics | None = None
    overlap: OverlapDiagnostic | None = None


def validate_ipw_input(
    execution: IPWExecutionRequest,
    table: AnalysisTable,
) -> IPWValidationResult:
    """Apply fatal gates in dependency order before effect estimation."""
    identification = execution.identification_result
    propensity = execution.propensity_result
    if identification.status is not IdentificationStatus.IDENTIFIED:
        return _failure(
            "identification.not_identified",
            IPWDiagnosticCategory.IDENTIFICATION,
            "Causal identification must be completed before IPW estimation.",
        )
    if (
        identification.request_id != propensity.request_id
        or identification.identification_request != propensity.analysis_request.identification
    ):
        return _failure(
            "provenance.upstream_request_mismatch",
            IPWDiagnosticCategory.IDENTIFICATION,
            "Identification and propensity results must reference the same request.",
            disposition=IPWValidationDisposition.INVALID,
        )
    adjustment = identification.adjustment_set
    if (
        adjustment is None
        or adjustment.validation_status is not AdjustmentValidationStatus.VALID
        or adjustment.variable_ids != propensity.adjustment_covariates
    ):
        return _failure(
            "provenance.invalid_adjustment_set",
            IPWDiagnosticCategory.IDENTIFICATION,
            "A valid matching adjustment set with provenance is required.",
            disposition=IPWValidationDisposition.INVALID,
        )
    estimand = identification.estimand
    if estimand is None or estimand.estimand_type not in {
        CausalEstimandKind.ATE,
        CausalEstimandKind.ATT,
    }:
        return _failure(
            "estimand.unsupported",
            IPWDiagnosticCategory.IDENTIFICATION,
            "V1 supports only declared ATE and ATT estimands.",
            disposition=IPWValidationDisposition.UNSUPPORTED,
        )
    expected_target = (
        TargetPopulationKind.FULL
        if estimand.estimand_type is CausalEstimandKind.ATE
        else TargetPopulationKind.TREATED
    )
    if estimand.target_population.kind is not expected_target or propensity.estimand is not (
        estimand.estimand_type
    ):
        return _failure(
            "estimand.upstream_mismatch",
            IPWDiagnosticCategory.IDENTIFICATION,
            "The propensity estimand and target population must match identification.",
            disposition=IPWValidationDisposition.INVALID,
        )
    if propensity.status is not PropensityStatus.COMPLETED:
        return _failure(
            "propensity.not_completed",
            IPWDiagnosticCategory.PROPENSITY,
            "The propensity result must be completed before effect estimation.",
        )
    if (
        propensity.model_fit.status is not PropensityFitStatus.CONVERGED
        or not propensity.model_fit.converged
    ):
        return _failure(
            "propensity.not_converged",
            IPWDiagnosticCategory.PROPENSITY,
            "The supplied propensity model did not converge safely.",
        )
    treatment = identification.treatment
    provenance = propensity.model_provenance
    if (
        treatment is None
        or provenance is None
        or propensity.encoding is None
        or propensity.score_diagnostics is None
        or not _typed_equal(provenance.treated_value, treatment.treated_value)
        or not _typed_equal(provenance.control_value, treatment.control_value)
        or provenance.estimand is not estimand.estimand_type
    ):
        return _failure(
            "propensity.provenance_unavailable",
            IPWDiagnosticCategory.PROPENSITY,
            (
                "Complete score-model, encoding, treatment-orientation, and diagnostic "
                "provenance is required."
            ),
            disposition=IPWValidationDisposition.INVALID,
        )
    if propensity.overlap.status not in {OverlapStatus.ACCEPTABLE, OverlapStatus.WEAK}:
        return _failure(
            "overlap.fatal",
            IPWDiagnosticCategory.OVERLAP,
            "Severe or unavailable overlap prevents IPW estimation.",
        )
    if propensity.weights is None:
        return _failure(
            "weight.missing_diagnostics",
            IPWDiagnosticCategory.WEIGHT,
            "Completed propensity input must include weight diagnostics.",
        )
    if propensity.weights.ess.status is not EffectiveSampleSizeStatus.ACCEPTABLE:
        return _failure(
            "weight.source_ess_collapsed",
            IPWDiagnosticCategory.WEIGHT,
            "Source propensity weights do not meet effective-sample requirements.",
        )
    role_diagnostic = _validate_outcome_role(execution)
    if role_diagnostic is not None:
        return IPWValidationResult(
            disposition=IPWValidationDisposition.INVALID,
            rows=(),
            balance_status=IPWBalanceStatus.UNAVAILABLE,
            diagnostics=(role_diagnostic,),
        )
    retained_diagnostic = _validate_selected_population(execution)
    if retained_diagnostic is not None:
        return IPWValidationResult(
            disposition=IPWValidationDisposition.INVALID,
            rows=(),
            balance_status=IPWBalanceStatus.UNAVAILABLE,
            diagnostics=(retained_diagnostic,),
        )
    selected = propensity.retained.scores if propensity.retained is not None else propensity.scores
    if not selected:
        return _failure(
            "weight.missing_scores",
            IPWDiagnosticCategory.WEIGHT,
            "The selected propensity population must contain aligned scores.",
        )
    score_diagnostic = _validate_scores(execution, selected)
    if score_diagnostic is not None:
        return IPWValidationResult(
            disposition=IPWValidationDisposition.ABSTAINED,
            rows=(),
            balance_status=IPWBalanceStatus.UNAVAILABLE,
            diagnostics=(score_diagnostic,),
        )
    selected_ess_diagnostic = _validate_selected_ess(execution, selected)
    if selected_ess_diagnostic is not None:
        return IPWValidationResult(
            disposition=IPWValidationDisposition.ABSTAINED,
            rows=(),
            balance_status=IPWBalanceStatus.UNAVAILABLE,
            diagnostics=(selected_ess_diagnostic,),
        )
    selected_overlap = _selected_overlap(execution, selected)
    if selected_overlap.status not in {OverlapStatus.ACCEPTABLE, OverlapStatus.WEAK}:
        return IPWValidationResult(
            disposition=IPWValidationDisposition.ABSTAINED,
            rows=(),
            balance_status=IPWBalanceStatus.UNAVAILABLE,
            diagnostics=(
                _diagnostic(
                    "overlap.selected_fatal",
                    IPWDiagnosticCategory.OVERLAP,
                    "The exact selected population fails overlap or positivity requirements.",
                ),
            ),
            overlap=selected_overlap,
        )
    outcome_support = _validate_outcome_support(execution)
    if outcome_support is not None:
        return IPWValidationResult(
            disposition=IPWValidationDisposition.UNSUPPORTED,
            rows=(),
            balance_status=IPWBalanceStatus.UNAVAILABLE,
            diagnostics=(outcome_support,),
            overlap=selected_overlap,
        )
    try:
        rows = _align_rows(execution, table, selected)
    except IPWNumericalError as error:
        return _failure(
            "outcome.invalid_alignment",
            IPWDiagnosticCategory.OUTCOME,
            str(error),
            disposition=IPWValidationDisposition.INVALID,
            overlap=selected_overlap,
        )
    if len(table.rows) != propensity.sample_counts.raw:
        return _failure(
            "outcome.raw_count_mismatch",
            IPWDiagnosticCategory.OUTCOME,
            "The outcome table row count must match the propensity raw sample count.",
            disposition=IPWValidationDisposition.INVALID,
            overlap=selected_overlap,
        )
    balance, balance_diagnostic = _resolve_balance(execution, table, selected)
    if balance_diagnostic is not None:
        return IPWValidationResult(
            disposition=(
                IPWValidationDisposition.INVALID
                if balance_diagnostic.code == "balance.inconsistent_diagnostics"
                else IPWValidationDisposition.ABSTAINED
            ),
            rows=(),
            balance_status=IPWBalanceStatus.UNAVAILABLE,
            diagnostics=(balance_diagnostic,),
            balance=balance,
            overlap=selected_overlap,
        )
    assert balance is not None
    balance_status = _balance_status(execution, balance)
    if balance_status is IPWBalanceStatus.UNAVAILABLE:
        return _failure(
            "balance.unavailable",
            IPWDiagnosticCategory.BALANCE,
            "Every required adjustment feature needs weighted balance diagnostics.",
            balance_status=balance_status,
            balance=balance,
            overlap=selected_overlap,
        )
    if balance_status is IPWBalanceStatus.SEVERE:
        return _failure(
            "balance.severe_residual_imbalance",
            IPWDiagnosticCategory.BALANCE,
            "Severe residual measured-covariate imbalance prevents estimation.",
            balance_status=balance_status,
            balance=balance,
            overlap=selected_overlap,
        )
    return IPWValidationResult(
        disposition=IPWValidationDisposition.VALID,
        rows=rows,
        balance_status=balance_status,
        diagnostics=(),
        balance=balance,
        overlap=selected_overlap,
    )


def _validate_scores(
    execution: IPWExecutionRequest,
    selected: tuple[PropensityScore, ...],
) -> IPWDiagnostic | None:
    estimand = execution.identification_result.estimand
    assert estimand is not None
    for item in selected:
        score = item.score
        if not math.isfinite(score):
            return _diagnostic(
                "weight.invalid_score",
                IPWDiagnosticCategory.WEIGHT,
                "Every selected propensity score must be finite.",
            )
        denominator = score if item.treated else 1.0 - score
        if estimand.estimand_type is CausalEstimandKind.ATT and item.treated:
            denominator = 1.0
        if denominator <= 0.0:
            return _diagnostic(
                "weight.invalid_denominator",
                IPWDiagnosticCategory.WEIGHT,
                "A selected propensity score creates a zero weight denominator.",
            )
    return None


def _validate_outcome_role(execution: IPWExecutionRequest) -> IPWDiagnostic | None:
    binding = execution.propensity_result.binding
    propensity_columns = {
        binding.unit_column,
        binding.treatment_column,
        *(item.column for item in binding.covariates),
    }
    if execution.binding.outcome_column in propensity_columns:
        return _diagnostic(
            "binding.outcome_role_conflict",
            IPWDiagnosticCategory.OUTCOME,
            "The outcome column must be distinct from unit, treatment, and covariate roles.",
        )
    return None


def _validate_selected_population(execution: IPWExecutionRequest) -> IPWDiagnostic | None:
    """Require retained scores to be the exact configured subset of model scores."""
    propensity = execution.propensity_result
    scores = propensity.scores
    typed_ids = tuple(_typed_key(item.unit_id) for item in scores)
    invalid = (
        len(typed_ids) != len(set(typed_ids))
        or len(scores) != propensity.sample_counts.model
        or sum(item.treated for item in scores) != propensity.sample_counts.model_treated
    )
    trimming = propensity.configuration.trimming
    retained = propensity.retained
    provenance = propensity.model_provenance
    if trimming is None:
        invalid = (
            invalid or retained is not None or bool(provenance and provenance.trimming_enabled)
        )
    else:
        if retained is None or provenance is None:
            invalid = True
        else:
            expected = tuple(
                item for item in scores if trimming.lower <= item.score <= trimming.upper
            )
            treated = sum(item.treated for item in expected)
            control = len(expected) - treated
            expected_scores = tuple(item.score for item in expected)
            expected_treatment = tuple(item.treated for item in expected)
            invalid = invalid or any(
                (
                    not provenance.trimming_enabled,
                    retained.configuration != trimming,
                    retained.scores != expected,
                    retained.retained_count != len(expected),
                    retained.treated_retained != treated,
                    retained.control_retained != control,
                    retained.dropped_count != len(scores) - len(expected),
                    retained.treated_dropped != propensity.sample_counts.model_treated - treated,
                    retained.control_dropped != propensity.sample_counts.model_control - control,
                    retained.common_support
                    != common_support_diagnostic(expected_scores, expected_treatment),
                    retained.score_diagnostics
                    != build_score_diagnostics(
                        expected_scores,
                        expected_treatment,
                        propensity.configuration,
                    ),
                    not math.isclose(
                        retained.retained_proportion,
                        len(expected) / len(scores) if scores else 0.0,
                        rel_tol=0.0,
                        abs_tol=1e-15,
                    ),
                )
            )
    if invalid:
        return _diagnostic(
            "provenance.invalid_retained_population",
            IPWDiagnosticCategory.PROPENSITY,
            "Retained scores must be the exact ordered subset defined by upstream trimming.",
        )
    return None


def _resolve_balance(
    execution: IPWExecutionRequest,
    table: AnalysisTable,
    selected: tuple[PropensityScore, ...],
) -> tuple[BalanceDiagnostics | None, IPWDiagnostic | None]:
    source = execution.propensity_result.balance
    encoding = execution.propensity_result.encoding
    if source is None or encoding is None:
        return None, _diagnostic(
            "balance.unavailable",
            IPWDiagnosticCategory.BALANCE,
            "Complete feature-level balance and encoding provenance are required.",
            unavailable=True,
        )
    if not _balance_contract_is_consistent(execution, source):
        return source, _diagnostic(
            "balance.inconsistent_diagnostics",
            IPWDiagnosticCategory.BALANCE,
            "Feature-level balance does not match its declared coverage or aggregates.",
        )
    if execution.propensity_result.retained is None and execution.configuration.clipping is None:
        return source, None
    try:
        recomputed = _recompute_selected_balance(execution, table, selected)
    except (IPWNumericalError, ValueError, ZeroDivisionError):
        return None, _diagnostic(
            "balance.unavailable",
            IPWDiagnosticCategory.BALANCE,
            "Balance could not be recomputed for the exact estimation population and weights.",
            unavailable=True,
        )
    return recomputed, None


def _balance_contract_is_consistent(
    execution: IPWExecutionRequest,
    balance: BalanceDiagnostics,
) -> bool:
    encoding = execution.propensity_result.encoding
    assert encoding is not None
    expected_names = encoding.balance_feature_names
    if tuple(item.feature_name for item in balance.features) != expected_names:
        return False
    threshold = execution.propensity_result.configuration.balance_threshold
    for item in balance.features:
        expected_variable = item.feature_name.split("==", maxsplit=1)[0]
        expected_status = BalanceStatus.UNAVAILABLE
        if item.weighted.smd is not None:
            expected_status = (
                BalanceStatus.BALANCED
                if abs(item.weighted.smd) <= threshold
                else BalanceStatus.IMBALANCED
            )
        if item.variable_id != expected_variable or item.status is not expected_status:
            return False
    raw = tuple(abs(item.raw.smd) for item in balance.features if item.raw.smd is not None)
    weighted = tuple(
        abs(item.weighted.smd) for item in balance.features if item.weighted.smd is not None
    )
    expected = (
        max(raw, default=0.0),
        max(weighted, default=0.0),
        sum(value > threshold for value in raw),
        sum(value > threshold for value in weighted),
        sum(
            item.raw.smd is not None
            and item.weighted.smd is not None
            and abs(item.weighted.smd) < abs(item.raw.smd)
            for item in balance.features
        ),
        sum(
            item.raw.smd is not None
            and item.weighted.smd is not None
            and abs(item.weighted.smd) > abs(item.raw.smd)
            for item in balance.features
        ),
    )
    actual = (
        balance.raw_max_absolute_smd,
        balance.weighted_max_absolute_smd,
        balance.raw_above_threshold_count,
        balance.weighted_above_threshold_count,
        balance.improved_count,
        balance.worsened_count,
    )
    return all(
        math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)
        if isinstance(left, float)
        else left == right
        for left, right in zip(actual, expected, strict=True)
    )


def _recompute_selected_balance(
    execution: IPWExecutionRequest,
    table: AnalysisTable,
    selected: tuple[PropensityScore, ...],
) -> BalanceDiagnostics:
    propensity = execution.propensity_result
    encoding = propensity.encoding
    estimand = execution.identification_result.estimand
    assert encoding is not None
    assert estimand is not None
    binding = propensity.binding
    required = (binding.unit_column, *(item.column for item in binding.covariates))
    if any(column not in table.columns for column in required):
        raise IPWNumericalError("Bound balance columns must exist in the outcome table.")
    unit_index = table.columns.index(binding.unit_column)
    source_rows = {_typed_key(row[unit_index]): row for row in table.rows}
    if len(source_rows) != len(table.rows):
        raise IPWNumericalError("Unit identifiers must be unique for balance recomputation.")
    covariates = {item.variable_id: item for item in binding.covariates}
    feature_specs: dict[str, tuple[str, ScalarValue | None]] = {}
    for numeric in encoding.numeric:
        covariate = covariates.get(numeric.variable_id)
        if covariate is None or covariate.feature_kind is not PropensityFeatureKind.NUMERIC:
            raise IPWNumericalError("Numeric encoding provenance does not match its binding.")
        feature_specs[numeric.feature_name] = (covariate.column, None)
    for categorical in encoding.categorical:
        covariate = covariates.get(categorical.variable_id)
        if covariate is None or covariate.feature_kind is not PropensityFeatureKind.CATEGORICAL:
            raise IPWNumericalError("Categorical encoding provenance does not match its binding.")
        if len(categorical.categories) != len(categorical.balance_feature_names):
            raise IPWNumericalError("Categorical encoding provenance is incomplete.")
        for category, feature_name in zip(
            categorical.categories, categorical.balance_feature_names, strict=True
        ):
            feature_specs[feature_name] = (covariate.column, category)
    if set(feature_specs) != set(encoding.balance_feature_names) or len(feature_specs) != len(
        encoding.balance_feature_names
    ):
        raise IPWNumericalError("Balance feature order does not match encoding provenance.")
    matrix: list[tuple[float, ...]] = []
    for score in selected:
        row = source_rows.get(_typed_key(score.unit_id))
        if row is None:
            raise IPWNumericalError("Every selected score requires its original covariates.")
        values: list[float] = []
        for feature_name in encoding.balance_feature_names:
            column, feature_category = feature_specs[feature_name]
            raw = row[table.columns.index(column)]
            values.append(
                _finite(raw, name=feature_name)
                if feature_category is None
                else float(_typed_equal(raw, feature_category))
            )
        matrix.append(tuple(values))
    treated = tuple(item.treated for item in selected)
    weights = compute_raw_weights(
        tuple(item.score for item in selected), treated, estimand.estimand_type
    )
    if execution.configuration.stabilized:
        weights = stabilize_weights(
            weights,
            treated,
            estimand.estimand_type,
            treatment_prevalence=sum(treated) / len(treated),
        )
    if execution.configuration.clipping is not None:
        weights = clip_weights(
            weights, treated, maximum=execution.configuration.clipping.maximum
        ).weights
    encoded = EncodedPropensityData(
        unit_ids=tuple(item.unit_id for item in selected),
        treated=treated,
        model_matrix=tuple(() for _ in selected),
        balance_matrix=tuple(matrix),
        metadata=encoding,
    )
    return build_balance_diagnostics(encoded, weights, propensity.configuration)


def _validate_outcome_support(execution: IPWExecutionRequest) -> IPWDiagnostic | None:
    outcome = execution.identification_result.outcome
    estimand = execution.identification_result.estimand
    if outcome is None or estimand is None:
        return _diagnostic(
            "outcome.unsupported",
            IPWDiagnosticCategory.OUTCOME,
            "A supported declared outcome is required.",
            unavailable=True,
        )
    metric_type = outcome.metric.metric.metric_type
    expected_scale = (
        EffectScale.RISK_DIFFERENCE
        if metric_type is MetricType.BINARY
        else EffectScale.MEAN_DIFFERENCE
    )
    if metric_type not in {MetricType.BINARY, MetricType.CONTINUOUS} or (
        estimand.effect_scale is not expected_scale
    ):
        return _diagnostic(
            "outcome.unsupported",
            IPWDiagnosticCategory.OUTCOME,
            "V1 supports binary risk differences and continuous mean differences.",
            unavailable=True,
        )
    return None


def _align_rows(
    execution: IPWExecutionRequest,
    table: AnalysisTable,
    selected: tuple[PropensityScore, ...],
) -> tuple[ValidatedIPWRow, ...]:
    unit_column = execution.propensity_result.binding.unit_column
    treatment_column = execution.propensity_result.binding.treatment_column
    outcome_column = execution.binding.outcome_column
    required_columns = (unit_column, treatment_column, outcome_column)
    if any(column not in table.columns for column in required_columns):
        raise IPWNumericalError("The bound unit, treatment, and outcome columns must exist.")
    unit_index = table.columns.index(unit_column)
    treatment_index = table.columns.index(treatment_column)
    outcome_index = table.columns.index(outcome_column)
    source = tuple(
        (row[unit_index], row[treatment_index], row[outcome_index]) for row in table.rows
    )
    metric = execution.identification_result.outcome
    contrast = execution.identification_result.treatment
    assert metric is not None
    assert contrast is not None
    aligned: list[ValidatedIPWRow] = []
    for score in selected:
        matches = tuple(
            (treatment_value, outcome)
            for unit, treatment_value, outcome in source
            if _typed_equal(unit, score.unit_id)
        )
        if len(matches) != 1:
            raise IPWNumericalError("Each selected propensity unit requires exactly one outcome.")
        treatment_value, raw_outcome = matches[0]
        expected_treatment = contrast.treated_value if score.treated else contrast.control_value
        if not _typed_equal(treatment_value, expected_treatment):
            raise IPWNumericalError("Selected treatment coding must match score orientation.")
        outcome = _finite(raw_outcome, name="outcome")
        if metric.metric.metric.metric_type is MetricType.BINARY and outcome not in {0.0, 1.0}:
            raise IPWNumericalError("Binary outcomes must be exactly zero or one.")
        aligned.append(
            ValidatedIPWRow(
                unit_id=score.unit_id,
                treated=score.treated,
                score=score.score,
                outcome=outcome,
            )
        )
    return tuple(aligned)


def _validate_selected_ess(
    execution: IPWExecutionRequest,
    selected: tuple[PropensityScore, ...],
) -> IPWDiagnostic | None:
    treated = tuple(item.treated for item in selected)
    estimand = execution.identification_result.estimand
    assert estimand is not None
    try:
        weights = compute_raw_weights(
            tuple(item.score for item in selected),
            treated,
            estimand.estimand_type,
        )
        if execution.configuration.stabilized:
            weights = stabilize_weights(
                weights,
                treated,
                estimand.estimand_type,
                treatment_prevalence=sum(treated) / len(treated),
            )
        if execution.configuration.clipping is not None:
            weights = clip_weights(
                weights,
                treated,
                maximum=execution.configuration.clipping.maximum,
            ).weights
        ess = build_ess_diagnostic(
            weights,
            treated,
            execution.propensity_result.configuration,
        )
    except (IPWNumericalError, ZeroDivisionError):
        return _diagnostic(
            "weight.invalid_selected_population",
            IPWDiagnosticCategory.WEIGHT,
            "The selected population cannot produce finite valid weights.",
        )
    if ess.status is not EffectiveSampleSizeStatus.ACCEPTABLE:
        return _diagnostic(
            "weight.selected_ess_collapsed",
            IPWDiagnosticCategory.WEIGHT,
            "Configured estimation weights do not meet effective-sample requirements.",
        )
    return None


def _selected_overlap(
    execution: IPWExecutionRequest,
    selected: tuple[PropensityScore, ...],
) -> OverlapDiagnostic:
    """Recompute overlap for the exact selected population without refitting scores."""
    estimand = execution.identification_result.estimand
    assert estimand is not None
    scores = tuple(item.score for item in selected)
    treated = tuple(item.treated for item in selected)
    raw_values = compute_raw_weights(scores, treated, estimand.estimand_type)
    raw_weights = tuple(
        PropensityWeight(unit_id=item.unit_id, treated=item.treated, value=value)
        for item, value in zip(selected, raw_values, strict=True)
    )
    weight_diagnostics = build_weight_diagnostics(
        raw_weights,
        estimand.estimand_type,
        execution.propensity_result.configuration,
    )
    return assess_overlap(
        scores=scores,
        treated=treated,
        support=common_support_diagnostic(scores, treated),
        model_fit=execution.propensity_result.model_fit,
        weights=weight_diagnostics,
        estimand=estimand.estimand_type,
        config=execution.propensity_result.configuration,
    )


def _balance_status(
    execution: IPWExecutionRequest,
    balance: BalanceDiagnostics,
) -> IPWBalanceStatus:
    if not balance.features or any(
        item.status is BalanceStatus.UNAVAILABLE or item.weighted.smd is None
        for item in balance.features
    ):
        return IPWBalanceStatus.UNAVAILABLE
    maximum = balance.weighted_max_absolute_smd
    if maximum > execution.configuration.severe_balance_threshold:
        return IPWBalanceStatus.SEVERE
    if maximum > execution.propensity_result.configuration.balance_threshold:
        return IPWBalanceStatus.CONCERN
    return IPWBalanceStatus.ACCEPTABLE


def _failure(
    code: str,
    category: IPWDiagnosticCategory,
    message: str,
    *,
    disposition: IPWValidationDisposition = IPWValidationDisposition.ABSTAINED,
    balance_status: IPWBalanceStatus = IPWBalanceStatus.UNAVAILABLE,
    balance: BalanceDiagnostics | None = None,
    overlap: OverlapDiagnostic | None = None,
) -> IPWValidationResult:
    return IPWValidationResult(
        disposition=disposition,
        rows=(),
        balance_status=balance_status,
        diagnostics=(_diagnostic(code, category, message),),
        balance=balance,
        overlap=overlap,
    )


def _diagnostic(
    code: str,
    category: IPWDiagnosticCategory,
    message: str,
    *,
    unavailable: bool = False,
) -> IPWDiagnostic:
    return IPWDiagnostic(
        code=code,
        category=category,
        severity=DiagnosticSeverity.FATAL,
        status=(
            PropensityDiagnosticStatus.UNAVAILABLE
            if unavailable
            else PropensityDiagnosticStatus.FAILED
        ),
        message=message,
    )


def _typed_equal(left: object, right: object) -> bool:
    return type(left) is type(right) and left == right


def _typed_key(value: object) -> tuple[str, ScalarValue]:
    if type(value) not in {bool, int, float, str}:
        raise IPWNumericalError("unit identifiers must be supported scalar values")
    return type(value).__name__, cast(ScalarValue, value)


def _finite(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise IPWNumericalError(f"{name} must be a finite real number")
    try:
        checked = float(value)
    except OverflowError as error:
        raise IPWNumericalError(f"{name} must be a finite real number") from error
    if not math.isfinite(checked):
        raise IPWNumericalError(f"{name} must be a finite real number")
    return checked


__all__ = [
    "IPWValidationDisposition",
    "IPWValidationResult",
    "ValidatedIPWRow",
    "validate_ipw_input",
]
