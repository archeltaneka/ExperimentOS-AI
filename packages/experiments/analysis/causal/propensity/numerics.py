"""Pure finite numerical helpers for propensity-score diagnostics."""

from __future__ import annotations

import math

from ..estimands import CausalEstimandKind
from .encoding import EncodedPropensityData
from .models import (
    BalanceDiagnostics,
    BalanceStatus,
    CommonSupportDiagnostic,
    CommonSupportStatus,
    CovariateBalanceDiagnostic,
    DistributionSummary,
    EffectiveSampleSizeDiagnostic,
    EffectiveSampleSizeStatus,
    OverlapDiagnostic,
    OverlapStatus,
    PropensityConfig,
    PropensityModelFit,
    PropensityScoreDiagnostics,
    PropensityWeight,
    PropensityWeightDiagnostics,
    QuantileValue,
    StandardizedMeanDifference,
)


class PropensityNumericalError(ValueError):
    """Raised when inputs cannot produce valid finite propensity diagnostics."""


def compute_weight_values(
    scores: tuple[float, ...],
    treated: tuple[bool, ...],
    estimand: CausalEstimandKind,
) -> tuple[float, ...]:
    """Compute uncapped, unnormalized ATE or ATT diagnostic weights."""
    if len(scores) != len(treated):
        raise PropensityNumericalError("scores and treatment indicators must align")
    if estimand not in {CausalEstimandKind.ATE, CausalEstimandKind.ATT}:
        raise PropensityNumericalError("only ATE and ATT diagnostic weights are supported")
    weights: list[float] = []
    for score, is_treated in zip(scores, treated, strict=True):
        _require_probability(score)
        denominator = score if is_treated else 1.0 - score
        if estimand is CausalEstimandKind.ATT and is_treated:
            weight = 1.0
        elif denominator == 0.0:
            raise PropensityNumericalError("weight denominator must not be zero")
        elif estimand is CausalEstimandKind.ATE:
            weight = 1.0 / denominator
        else:
            weight = score / denominator
        if not math.isfinite(weight) or weight < 0.0:
            raise PropensityNumericalError("weights must be finite and nonnegative")
        weights.append(weight)
    return tuple(weights)


def effective_sample_size(weights: tuple[float, ...]) -> float | None:
    """Return Kish weighted ESS, or unavailable for an empty population."""
    if not weights:
        return None
    _require_weights(weights)
    total = math.fsum(weights)
    sum_squares = math.fsum(weight * weight for weight in weights)
    if total == 0.0 or sum_squares == 0.0:
        raise PropensityNumericalError("effective sample size denominator must be positive")
    result = total * total / sum_squares
    if not math.isfinite(result) or result < 0.0:
        raise PropensityNumericalError("effective sample size must be finite and nonnegative")
    return result


def common_support_diagnostic(
    scores: tuple[float, ...],
    treated: tuple[bool, ...],
) -> CommonSupportDiagnostic:
    """Compute intersection of the observed treated and control score ranges."""
    if len(scores) != len(treated):
        raise PropensityNumericalError("scores and treatment indicators must align")
    for score in scores:
        _require_probability(score)
    treated_scores = tuple(score for score, arm in zip(scores, treated, strict=True) if arm)
    control_scores = tuple(score for score, arm in zip(scores, treated, strict=True) if not arm)
    if not treated_scores or not control_scores:
        return CommonSupportDiagnostic(status=CommonSupportStatus.UNAVAILABLE)
    lower = max(min(treated_scores), min(control_scores))
    upper = min(max(treated_scores), max(control_scores))
    if lower > upper:
        return CommonSupportDiagnostic(
            status=CommonSupportStatus.EMPTY,
            lower=lower,
            upper=upper,
            treated_outside=len(treated_scores),
            control_outside=len(control_scores),
            total_outside=len(scores),
        )
    treated_inside = sum(lower <= score <= upper for score in treated_scores)
    control_inside = sum(lower <= score <= upper for score in control_scores)
    treated_outside = len(treated_scores) - treated_inside
    control_outside = len(control_scores) - control_inside
    return CommonSupportDiagnostic(
        status=CommonSupportStatus.AVAILABLE,
        lower=lower,
        upper=upper,
        width=upper - lower,
        treated_inside=treated_inside,
        control_inside=control_inside,
        treated_outside=treated_outside,
        control_outside=control_outside,
        total_outside=treated_outside + control_outside,
        treated_inside_proportion=treated_inside / len(treated_scores),
        control_inside_proportion=control_inside / len(control_scores),
    )


def standardized_mean_difference(
    *,
    treated_values: tuple[float, ...],
    control_values: tuple[float, ...],
    treated_weights: tuple[float, ...],
    control_weights: tuple[float, ...],
) -> StandardizedMeanDifference:
    """Compute a weighted SMD using pooled within-arm population variances."""
    if not treated_values or not control_values:
        raise PropensityNumericalError("both arms require values for balance diagnostics")
    if len(treated_values) != len(treated_weights) or len(control_values) != len(control_weights):
        raise PropensityNumericalError("balance values and weights must align")
    treated_mean, treated_variance = _weighted_moments(treated_values, treated_weights)
    control_mean, control_variance = _weighted_moments(control_values, control_weights)
    pooled_variance = (treated_variance + control_variance) / 2.0
    difference = treated_mean - control_mean
    if pooled_variance == 0.0:
        if difference == 0.0:
            return StandardizedMeanDifference(
                available=True,
                treated_mean=treated_mean,
                control_mean=control_mean,
                treated_variance=treated_variance,
                control_variance=control_variance,
                smd=0.0,
            )
        return StandardizedMeanDifference(
            available=False,
            treated_mean=treated_mean,
            control_mean=control_mean,
            treated_variance=treated_variance,
            control_variance=control_variance,
            smd=None,
            warning_code="balance.zero_pooled_variance",
        )
    smd = difference / math.sqrt(pooled_variance)
    _require_finite(smd)
    return StandardizedMeanDifference(
        available=True,
        treated_mean=treated_mean,
        control_mean=control_mean,
        treated_variance=treated_variance,
        control_variance=control_variance,
        smd=smd,
    )


def summarize_distribution(
    values: tuple[float, ...],
    quantile_levels: tuple[float, ...],
) -> DistributionSummary:
    """Summarize a non-empty finite distribution with sample standard deviation."""
    if not values:
        raise PropensityNumericalError("a distribution summary requires observations")
    for value in values:
        _require_finite(value)
    ordered = tuple(sorted(values))
    mean = math.fsum(values) / len(values)
    standard_deviation = None
    if len(values) > 1:
        variance = math.fsum((value - mean) ** 2 for value in values) / (len(values) - 1)
        standard_deviation = math.sqrt(variance)
    return DistributionSummary(
        count=len(values),
        mean=mean,
        standard_deviation=standard_deviation,
        minimum=ordered[0],
        maximum=ordered[-1],
        median=_linear_quantile(ordered, 0.5),
        quantiles=tuple(
            QuantileValue(level=level, value=_linear_quantile(ordered, level))
            for level in quantile_levels
        ),
        total=math.fsum(values),
    )


def build_score_diagnostics(
    scores: tuple[float, ...],
    treated: tuple[bool, ...],
    config: PropensityConfig,
) -> PropensityScoreDiagnostics:
    """Build aggregate score distributions without exposing raw values to telemetry."""
    treated_scores = tuple(score for score, arm in zip(scores, treated, strict=True) if arm)
    control_scores = tuple(score for score, arm in zip(scores, treated, strict=True) if not arm)
    return PropensityScoreDiagnostics(
        overall=summarize_distribution(scores, config.score_quantiles),
        treated=summarize_distribution(treated_scores, config.score_quantiles),
        control=summarize_distribution(control_scores, config.score_quantiles),
    )


def build_weight_diagnostics(
    raw: tuple[PropensityWeight, ...],
    estimand: CausalEstimandKind,
    config: PropensityConfig,
) -> PropensityWeightDiagnostics:
    """Summarize raw estimand weights and configured ESS adequacy."""
    values = tuple(item.value for item in raw)
    treated_values = tuple(item.value for item in raw if item.treated)
    control_values = tuple(item.value for item in raw if not item.treated)
    extreme_count = sum(value > config.extreme_weight_threshold for value in values)
    ess = build_ess_diagnostic(values, tuple(item.treated for item in raw), config)
    return PropensityWeightDiagnostics(
        estimand=estimand,
        raw=raw,
        overall=summarize_distribution(values, config.weight_quantiles),
        treated=summarize_distribution(treated_values, config.weight_quantiles),
        control=summarize_distribution(control_values, config.weight_quantiles),
        extreme_weight_count=extreme_count,
        extreme_weight_proportion=extreme_count / len(values),
        ess=ess,
    )


def build_ess_diagnostic(
    weights: tuple[float, ...],
    treated: tuple[bool, ...],
    config: PropensityConfig,
) -> EffectiveSampleSizeDiagnostic:
    """Compute ESS overall/by arm and apply absolute and relative policy."""
    treated_weights = tuple(weight for weight, arm in zip(weights, treated, strict=True) if arm)
    control_weights = tuple(weight for weight, arm in zip(weights, treated, strict=True) if not arm)
    overall = effective_sample_size(weights)
    treated_ess = effective_sample_size(treated_weights)
    control_ess = effective_sample_size(control_weights)
    if overall is None or treated_ess is None or control_ess is None:
        status = EffectiveSampleSizeStatus.UNAVAILABLE
    else:
        values = (
            (overall, len(weights)),
            (treated_ess, len(treated_weights)),
            (control_ess, len(control_weights)),
        )
        collapsed = any(
            ess < config.minimum_effective_sample_size or ess / count < config.minimum_ess_ratio
            for ess, count in values
        )
        status = (
            EffectiveSampleSizeStatus.COLLAPSED
            if collapsed
            else EffectiveSampleSizeStatus.ACCEPTABLE
        )
    return EffectiveSampleSizeDiagnostic(
        status=status,
        overall=overall,
        treated=treated_ess,
        control=control_ess,
        raw_count=len(weights),
        treated_raw_count=len(treated_weights),
        control_raw_count=len(control_weights),
        overall_ratio=overall / len(weights) if overall is not None and weights else None,
        treated_ratio=(
            treated_ess / len(treated_weights)
            if treated_ess is not None and treated_weights
            else None
        ),
        control_ratio=(
            control_ess / len(control_weights)
            if control_ess is not None and control_weights
            else None
        ),
    )


def build_balance_diagnostics(
    encoded: EncodedPropensityData,
    raw_weights: tuple[float, ...],
    config: PropensityConfig,
) -> BalanceDiagnostics:
    """Compare raw and weighted SMD for every deterministic balance feature."""
    features: list[CovariateBalanceDiagnostic] = []
    for index, feature_name in enumerate(encoded.metadata.balance_feature_names):
        values = tuple(row[index] for row in encoded.balance_matrix)
        treated_values = tuple(
            value for value, arm in zip(values, encoded.treated, strict=True) if arm
        )
        control_values = tuple(
            value for value, arm in zip(values, encoded.treated, strict=True) if not arm
        )
        treated_weights = tuple(
            weight for weight, arm in zip(raw_weights, encoded.treated, strict=True) if arm
        )
        control_weights = tuple(
            weight for weight, arm in zip(raw_weights, encoded.treated, strict=True) if not arm
        )
        raw = standardized_mean_difference(
            treated_values=treated_values,
            control_values=control_values,
            treated_weights=tuple(1.0 for _ in treated_values),
            control_weights=tuple(1.0 for _ in control_values),
        )
        weighted = standardized_mean_difference(
            treated_values=treated_values,
            control_values=control_values,
            treated_weights=treated_weights,
            control_weights=control_weights,
        )
        status = BalanceStatus.UNAVAILABLE
        if weighted.smd is not None:
            status = (
                BalanceStatus.BALANCED
                if abs(weighted.smd) <= config.balance_threshold
                else BalanceStatus.IMBALANCED
            )
        warnings = tuple(
            code for code in (raw.warning_code, weighted.warning_code) if code is not None
        )
        features.append(
            CovariateBalanceDiagnostic(
                variable_id=feature_name.split("==", maxsplit=1)[0],
                feature_name=feature_name,
                raw=raw,
                weighted=weighted,
                status=status,
                warnings=warnings,
            )
        )

    raw_values = tuple(abs(item.raw.smd) for item in features if item.raw.smd is not None)
    weighted_values = tuple(
        abs(item.weighted.smd) for item in features if item.weighted.smd is not None
    )
    improved = sum(
        item.raw.smd is not None
        and item.weighted.smd is not None
        and abs(item.weighted.smd) < abs(item.raw.smd)
        for item in features
    )
    worsened = sum(
        item.raw.smd is not None
        and item.weighted.smd is not None
        and abs(item.weighted.smd) > abs(item.raw.smd)
        for item in features
    )
    return BalanceDiagnostics(
        features=tuple(features),
        raw_max_absolute_smd=max(raw_values, default=0.0),
        weighted_max_absolute_smd=max(weighted_values, default=0.0),
        raw_above_threshold_count=sum(value > config.balance_threshold for value in raw_values),
        weighted_above_threshold_count=sum(
            value > config.balance_threshold for value in weighted_values
        ),
        improved_count=improved,
        worsened_count=worsened,
    )


def assess_overlap(
    *,
    scores: tuple[float, ...],
    treated: tuple[bool, ...],
    support: CommonSupportDiagnostic,
    model_fit: PropensityModelFit,
    weights: PropensityWeightDiagnostics,
    estimand: CausalEstimandKind,
    config: PropensityConfig,
) -> OverlapDiagnostic:
    """Classify overlap using centralized, estimand-specific deterministic thresholds."""
    threshold = config.extreme_score_threshold
    extreme_count = sum(score <= threshold or score >= 1.0 - threshold for score in scores)
    extreme_fraction = extreme_count / len(scores)
    if estimand is CausalEstimandKind.ATT:
        treated_count = sum(treated)
        target_outside = support.treated_outside / treated_count if treated_count else None
        comparator_inside_count = support.control_inside
        comparator_inside_fraction = support.control_inside_proportion
    else:
        target_outside = support.total_outside / len(scores) if scores else None
        comparator_inside_count = None
        comparator_inside_fraction = None
    separation = bool(
        model_fit.training_accuracy is not None
        and model_fit.training_accuracy >= config.separation_accuracy_threshold
        and (
            (model_fit.extreme_score_fraction or 0.0) >= config.separation_extreme_fraction
            or (model_fit.maximum_absolute_coefficient or 0.0)
            >= config.separation_coefficient_threshold
        )
    )
    codes: list[str] = []
    severe = False
    weak = False
    if support.status is CommonSupportStatus.EMPTY:
        severe = True
        codes.append("overlap.empty_common_support")
    elif support.status is CommonSupportStatus.UNAVAILABLE:
        return OverlapDiagnostic(
            status=OverlapStatus.UNAVAILABLE,
            target_outside_support_fraction=None,
            comparator_inside_support_count=comparator_inside_count,
            comparator_inside_support_fraction=comparator_inside_fraction,
            extreme_score_count=extreme_count,
            extreme_score_fraction=extreme_fraction,
            separation_detected=separation,
            diagnostic_codes=("overlap.unavailable",),
        )
    elif support.width <= config.severe_support_width:
        severe = True
        codes.append("overlap.severe_narrow_support")
    elif support.width <= config.weak_support_width:
        weak = True
        codes.append("overlap.weak_narrow_support")
    if target_outside is not None:
        if target_outside >= config.severe_outside_support_fraction:
            severe = True
            codes.append("overlap.severe_outside_support")
        elif target_outside >= config.weak_outside_support_fraction:
            weak = True
            codes.append("overlap.weak_outside_support")
    if extreme_fraction >= config.severe_extreme_score_fraction:
        severe = True
        codes.append("overlap.severe_extreme_scores")
    elif extreme_fraction >= config.weak_extreme_score_fraction:
        weak = True
        codes.append("overlap.weak_extreme_scores")
    if estimand is CausalEstimandKind.ATT and (
        support.control_inside < config.minimum_att_control_support_count
        or support.control_inside_proportion < config.minimum_att_control_support_proportion
    ):
        severe = True
        codes.append("overlap.insufficient_att_controls")
    if separation:
        severe = True
        codes.append("model.separation")
    if weights.ess.status is EffectiveSampleSizeStatus.COLLAPSED:
        severe = True
        codes.append("weight.ess_collapse")
    if weights.extreme_weight_proportion >= config.severe_extreme_weight_fraction:
        severe = True
        codes.append("weight.severe_extreme_tail")
    elif weights.extreme_weight_proportion >= config.weak_extreme_weight_fraction:
        weak = True
        codes.append("weight.extreme_tail")
    status = (
        OverlapStatus.SEVERE if severe else OverlapStatus.WEAK if weak else OverlapStatus.ACCEPTABLE
    )
    return OverlapDiagnostic(
        status=status,
        target_outside_support_fraction=target_outside,
        comparator_inside_support_count=comparator_inside_count,
        comparator_inside_support_fraction=comparator_inside_fraction,
        extreme_score_count=extreme_count,
        extreme_score_fraction=extreme_fraction,
        separation_detected=separation,
        diagnostic_codes=tuple(sorted(set(codes))),
    )


def _weighted_moments(
    values: tuple[float, ...],
    weights: tuple[float, ...],
) -> tuple[float, float]:
    for value in values:
        _require_finite(value)
    _require_weights(weights)
    total_weight = math.fsum(weights)
    if total_weight == 0.0:
        raise PropensityNumericalError("weighted moments require positive total weight")
    mean = math.fsum(weight * value for value, weight in zip(values, weights, strict=True))
    mean /= total_weight
    variance = math.fsum(
        weight * (value - mean) ** 2 for value, weight in zip(values, weights, strict=True)
    )
    variance /= total_weight
    _require_finite(mean)
    _require_finite(variance)
    return mean, variance


def _linear_quantile(values: tuple[float, ...], level: float) -> float:
    _require_probability(level)
    position = (len(values) - 1) * level
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    fraction = position - lower
    result = values[lower] + (values[upper] - values[lower]) * fraction
    _require_finite(result)
    return result


def _require_weights(weights: tuple[float, ...]) -> None:
    for weight in weights:
        _require_finite(weight)
        if weight < 0.0:
            raise PropensityNumericalError("weights must be nonnegative")


def _require_probability(value: float) -> None:
    _require_finite(value)
    if value < 0.0 or value > 1.0:
        raise PropensityNumericalError("scores and quantiles must be within [0, 1]")


def _require_finite(value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise PropensityNumericalError("numerical inputs must be finite real values")


__all__ = [
    "PropensityNumericalError",
    "common_support_diagnostic",
    "assess_overlap",
    "build_balance_diagnostics",
    "build_ess_diagnostic",
    "build_score_diagnostics",
    "build_weight_diagnostics",
    "compute_weight_values",
    "effective_sample_size",
    "standardized_mean_difference",
    "summarize_distribution",
]
