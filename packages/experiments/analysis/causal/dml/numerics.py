"""Finite-safe orthogonal score, diagnostics, overlap, and DML inference."""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.stats import norm  # type: ignore[import-untyped]

from ...uncertainty import ConfidenceInterval
from ..propensity.models import (
    CommonSupportStatus,
    OverlapStatus,
    PropensityScoreDiagnostics,
)
from ..propensity.numerics import common_support_diagnostic, summarize_distribution
from .models import (
    DMLConfig,
    DMLInfluenceDiagnostics,
    DMLNuisanceDiagnostics,
    DMLOutcomeNuisanceDiagnostics,
    DMLOverlapDiagnostic,
    DMLResidualSummary,
    DMLTestResult,
    DMLTreatmentNuisanceDiagnostics,
    DMLVarianceMethod,
)


class DMLNumericalError(ValueError):
    """Owned numerical refusal carrying a stable DML diagnostic code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class DMLComputation:
    """Internal orthogonal-score calculation and safe aggregate evidence."""

    point_estimate: float
    numerator: float
    denominator: float
    outcome_residuals: tuple[float, ...]
    treatment_residuals: tuple[float, ...]
    outcome_residual_diagnostics: DMLResidualSummary
    treatment_residual_diagnostics: DMLResidualSummary
    influence_values: tuple[float, ...]
    influence_diagnostics: DMLInfluenceDiagnostics
    inference: DMLTestResult


def estimate_partialling_out(
    *,
    outcome: tuple[float, ...],
    treatment: tuple[float, ...],
    outcome_prediction: tuple[float, ...],
    treatment_prediction: tuple[float, ...],
    config: DMLConfig,
) -> DMLComputation:
    """Solve the supported partialling-out score and estimate influence uncertainty."""
    lengths = {
        len(outcome),
        len(treatment),
        len(outcome_prediction),
        len(treatment_prediction),
    }
    if len(lengths) != 1 or not outcome:
        raise DMLNumericalError(
            "dml.input.shape_mismatch",
            "Outcome, treatment, and nuisance predictions must align and be non-empty.",
        )
    if len(outcome) < 2:
        raise DMLNumericalError(
            "dml.inference.inadequate_sample",
            "DML influence inference requires at least two observations.",
        )
    values = (*outcome, *treatment, *outcome_prediction, *treatment_prediction)
    if any(not math.isfinite(value) for value in values):
        raise DMLNumericalError(
            "dml.nonfinite_residual",
            "DML inputs and residuals must be finite.",
        )
    outcome_residuals = tuple(
        observed - predicted
        for observed, predicted in zip(outcome, outcome_prediction, strict=True)
    )
    treatment_residuals = tuple(
        observed - predicted
        for observed, predicted in zip(treatment, treatment_prediction, strict=True)
    )
    outcome_summary = summarize_residuals(outcome_residuals)
    treatment_summary = summarize_residuals(treatment_residuals)
    denominator = math.fsum(value * value for value in treatment_residuals)
    if denominator <= config.treatment_residual_tolerance:
        raise DMLNumericalError(
            "dml.degenerate_treatment_residual",
            "Residualized treatment has insufficient variation for DML estimation.",
        )
    if outcome_summary.variance <= config.outcome_residual_variance_tolerance:
        raise DMLNumericalError(
            "dml.degenerate_outcome_residual",
            "Outcome residuals have insufficient variation for meaningful DML inference.",
        )
    numerator = math.fsum(
        treatment_value * outcome_value
        for treatment_value, outcome_value in zip(
            treatment_residuals,
            outcome_residuals,
            strict=True,
        )
    )
    point_estimate = _finite(numerator / denominator, code="dml.inference.nonfinite_estimate")
    q_hat = denominator / len(outcome)
    influence = tuple(
        treatment_value * (outcome_value - point_estimate * treatment_value) / q_hat
        for treatment_value, outcome_value in zip(
            treatment_residuals,
            outcome_residuals,
            strict=True,
        )
    )
    if any(not math.isfinite(value) for value in influence):
        raise DMLNumericalError(
            "dml.inference.nonfinite_influence",
            "DML influence values must be finite.",
        )
    sample_size = len(influence)
    influence_squared_sum = math.fsum(value * value for value in influence)
    estimate_variance = _finite(
        influence_squared_sum / (sample_size * (sample_size - 1)),
        code="dml.inference.nonfinite_variance",
    )
    standard_error = _finite(
        math.sqrt(estimate_variance),
        code="dml.inference.nonfinite_standard_error",
    )
    if standard_error <= 0.0:
        raise DMLNumericalError(
            "dml.inference.degenerate_standard_error",
            "DML inference requires a positive finite standard error.",
        )
    statistic = _finite(
        point_estimate / standard_error,
        code="dml.inference.nonfinite_statistic",
    )
    p_value = _finite(
        min(1.0, 2.0 * float(norm.sf(abs(statistic)))),
        code="dml.inference.nonfinite_p_value",
    )
    critical = _finite(
        float(norm.ppf(1.0 - (1.0 - config.confidence_level) / 2.0)),
        code="dml.inference.nonfinite_critical_value",
    )
    lower = _finite(
        point_estimate - critical * standard_error,
        code="dml.inference.nonfinite_interval",
    )
    upper = _finite(
        point_estimate + critical * standard_error,
        code="dml.inference.nonfinite_interval",
    )
    inference = DMLTestResult(
        variance_method=DMLVarianceMethod.ORTHOGONAL_SCORE_INFLUENCE_HC1,
        standard_error=standard_error,
        statistic=statistic,
        p_value=p_value,
        confidence_interval=ConfidenceInterval(
            lower=lower,
            upper=upper,
            confidence_level=config.confidence_level,
        ),
    )
    influence_diagnostics = DMLInfluenceDiagnostics(
        count=sample_size,
        variance=influence_squared_sum / (sample_size - 1),
        maximum_absolute=max(abs(value) for value in influence),
        nonfinite_count=0,
    )
    return DMLComputation(
        point_estimate=point_estimate,
        numerator=numerator,
        denominator=denominator,
        outcome_residuals=outcome_residuals,
        treatment_residuals=treatment_residuals,
        outcome_residual_diagnostics=outcome_summary,
        treatment_residual_diagnostics=treatment_summary,
        influence_values=influence,
        influence_diagnostics=influence_diagnostics,
        inference=inference,
    )


def summarize_residuals(values: tuple[float, ...]) -> DMLResidualSummary:
    """Summarize finite residual variation with sample-variance semantics."""
    if not values:
        raise DMLNumericalError("dml.residual.empty", "Residual diagnostics require observations.")
    nonfinite_count = sum(not math.isfinite(value) for value in values)
    if nonfinite_count:
        raise DMLNumericalError(
            "dml.nonfinite_residual",
            "Residual diagnostics cannot summarize non-finite values.",
        )
    count = len(values)
    mean = math.fsum(values) / count
    squared_deviations = math.fsum((value - mean) ** 2 for value in values)
    variance = squared_deviations / (count - 1) if count > 1 else 0.0
    return DMLResidualSummary(
        count=count,
        mean=mean,
        standard_deviation=math.sqrt(variance),
        minimum=min(values),
        maximum=max(values),
        variance=variance,
        squared_norm=math.fsum(value * value for value in values),
        nonfinite_count=0,
    )


def build_nuisance_diagnostics(
    *,
    outcome: tuple[float, ...],
    outcome_prediction: tuple[float, ...],
    treatment: tuple[bool, ...],
    treatment_prediction: tuple[float, ...],
    config: DMLConfig,
) -> DMLNuisanceDiagnostics:
    """Compute predictive metrics that make no causal-identification claim."""
    if (
        not outcome
        or len(outcome) != len(outcome_prediction)
        or len(outcome) != len(treatment)
        or len(outcome) != len(treatment_prediction)
    ):
        raise DMLNumericalError(
            "dml.nuisance.metric_shape",
            "Nuisance metric inputs must align and be non-empty.",
        )
    values = (*outcome, *outcome_prediction, *treatment_prediction)
    if any(not math.isfinite(value) for value in values):
        raise DMLNumericalError(
            "dml.nuisance.nonfinite_metric_input",
            "Nuisance metric inputs must be finite.",
        )
    if any(value < 0.0 or value > 1.0 for value in treatment_prediction):
        raise DMLNumericalError(
            "dml.nuisance.invalid_probability",
            "Treatment nuisance metric inputs must be probabilities.",
        )
    errors = tuple(
        observed - predicted
        for observed, predicted in zip(outcome, outcome_prediction, strict=True)
    )
    squared_error = math.fsum(value * value for value in errors)
    outcome_mean = math.fsum(outcome) / len(outcome)
    total_squares = math.fsum((value - outcome_mean) ** 2 for value in outcome)
    r_squared = None if total_squares == 0.0 else 1.0 - squared_error / total_squares
    epsilon = config.metric_probability_clip
    clipped = tuple(min(1.0 - epsilon, max(epsilon, value)) for value in treatment_prediction)
    log_loss = -math.fsum(
        math.log(score) if treated else math.log(1.0 - score)
        for treated, score in zip(treatment, clipped, strict=True)
    ) / len(treatment)
    brier = math.fsum(
        (float(treated) - score) ** 2
        for treated, score in zip(treatment, treatment_prediction, strict=True)
    ) / len(treatment)
    return DMLNuisanceDiagnostics(
        outcome=DMLOutcomeNuisanceDiagnostics(
            rmse=math.sqrt(squared_error / len(errors)),
            mae=math.fsum(abs(value) for value in errors) / len(errors),
            r_squared=r_squared,
        ),
        treatment=DMLTreatmentNuisanceDiagnostics(
            log_loss=log_loss,
            brier_score=brier,
            roc_auc=_binary_auc(treatment, treatment_prediction),
            score_distribution=summarize_distribution(
                treatment_prediction,
                config.score_quantiles,
            ),
        ),
        interpretation=(
            "Nuisance predictive performance does not establish causal validity, "
            "exchangeability, correct adjustment, or positivity."
        ),
    )


def assess_dml_overlap(
    *,
    scores: tuple[float, ...],
    treated: tuple[bool, ...],
    config: DMLConfig,
) -> DMLOverlapDiagnostic:
    """Assess DML overlap from cross-fitted treatment probabilities only."""
    if len(scores) != len(treated) or not scores:
        raise DMLNumericalError(
            "dml.overlap.shape",
            "DML overlap scores and treatment indicators must align.",
        )
    if any(not math.isfinite(score) or score < 0.0 or score > 1.0 for score in scores):
        raise DMLNumericalError(
            "dml.overlap.invalid_score",
            "DML overlap requires finite probabilities in [0, 1].",
        )
    treated_scores = tuple(score for score, arm in zip(scores, treated, strict=True) if arm)
    control_scores = tuple(score for score, arm in zip(scores, treated, strict=True) if not arm)
    if not treated_scores or not control_scores:
        raise DMLNumericalError(
            "dml.overlap.missing_arm",
            "DML overlap requires treated and control observations.",
        )
    support = common_support_diagnostic(scores, treated)
    score_diagnostics = PropensityScoreDiagnostics(
        overall=summarize_distribution(scores, config.score_quantiles),
        treated=summarize_distribution(treated_scores, config.score_quantiles),
        control=summarize_distribution(control_scores, config.score_quantiles),
    )
    outside = max(
        1.0 - support.treated_inside_proportion,
        1.0 - support.control_inside_proportion,
    )
    threshold = config.extreme_score_threshold
    extreme_count = sum(score <= threshold or score >= 1.0 - threshold for score in scores)
    extreme_fraction = extreme_count / len(scores)
    severe_codes: list[str] = []
    weak_codes: list[str] = []
    shared_nonextreme_point = (
        max(scores) == min(scores)
        and threshold < scores[0] < 1.0 - threshold
    )
    if support.status is CommonSupportStatus.EMPTY:
        severe_codes.append("dml.overlap.empty_support")
    elif support.status is CommonSupportStatus.UNAVAILABLE:
        severe_codes.append("dml.overlap.unavailable")
    else:
        if not shared_nonextreme_point and support.width < config.severe_support_width:
            severe_codes.append("dml.overlap.severe_support_width")
        elif not shared_nonextreme_point and support.width < config.weak_support_width:
            weak_codes.append("dml.overlap.weak_support_width")
    if outside >= config.severe_outside_support_fraction:
        severe_codes.append("dml.overlap.severe_outside_support")
    elif outside >= config.weak_outside_support_fraction:
        weak_codes.append("dml.overlap.weak_outside_support")
    if extreme_fraction >= config.severe_extreme_score_fraction:
        severe_codes.append("dml.overlap.severe_extreme_scores")
    elif extreme_fraction >= config.weak_extreme_score_fraction:
        weak_codes.append("dml.overlap.weak_extreme_scores")
    status = (
        OverlapStatus.SEVERE
        if severe_codes
        else OverlapStatus.WEAK
        if weak_codes
        else OverlapStatus.ACCEPTABLE
    )
    return DMLOverlapDiagnostic(
        status=status,
        common_support=support,
        score_diagnostics=score_diagnostics,
        target_outside_support_fraction=outside,
        extreme_score_count=extreme_count,
        extreme_score_fraction=extreme_fraction,
        diagnostic_codes=tuple(sorted((*severe_codes, *weak_codes))),
    )


def _binary_auc(treated: tuple[bool, ...], scores: tuple[float, ...]) -> float | None:
    treated_scores = tuple(score for score, arm in zip(scores, treated, strict=True) if arm)
    control_scores = tuple(score for score, arm in zip(scores, treated, strict=True) if not arm)
    if not treated_scores or not control_scores:
        return None
    favorable = math.fsum(
        1.0 if treated_score > control_score else 0.5 if treated_score == control_score else 0.0
        for treated_score in treated_scores
        for control_score in control_scores
    )
    return favorable / (len(treated_scores) * len(control_scores))


def _finite(value: float, *, code: str) -> float:
    if not math.isfinite(value):
        raise DMLNumericalError(code, "DML arithmetic produced a non-finite result.")
    return value


__all__ = [
    "DMLComputation",
    "DMLNumericalError",
    "assess_dml_overlap",
    "build_nuisance_diagnostics",
    "estimate_partialling_out",
    "summarize_residuals",
]
