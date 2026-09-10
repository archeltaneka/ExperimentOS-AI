"""Finite-safe orthogonal subgroup interaction calculations."""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.stats import chi2, norm  # type: ignore[import-untyped]


class HTENumericalError(ValueError):
    """Raised when subgroup interaction inference is not numerically supportable."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class HTEGroupComputation:
    subgroup_id: str
    sample_size: int
    estimate: float
    standard_error: float
    statistic: float
    p_value: float
    confidence_interval_lower: float
    confidence_interval_upper: float
    estimate_variance: float


@dataclass(frozen=True)
class HTEContrastComputation:
    reference_subgroup_id: str
    comparison_subgroup_id: str
    estimate: float
    standard_error: float
    statistic: float
    p_value: float
    confidence_interval_lower: float
    confidence_interval_upper: float


@dataclass(frozen=True)
class HTEGlobalComputation:
    statistic: float
    degrees_of_freedom: int
    p_value: float
    detected: bool


@dataclass(frozen=True)
class HTEComputation:
    groups: tuple[HTEGroupComputation, ...]
    contrasts: tuple[HTEContrastComputation, ...]
    global_heterogeneity: HTEGlobalComputation


def estimate_grouped_orthogonal_effects(
    *,
    outcomes: tuple[float, ...],
    treatments: tuple[float, ...],
    outcome_predictions: tuple[float, ...],
    treatment_predictions: tuple[float, ...],
    subgroup_ids: tuple[str, ...],
    confidence_level: float,
    residual_tolerance: float,
) -> HTEComputation:
    """Estimate discrete subgroup slopes and direct cross-group differences."""
    _validate_inputs(
        outcomes,
        treatments,
        outcome_predictions,
        treatment_predictions,
        subgroup_ids,
        confidence_level,
        residual_tolerance,
    )
    outcome_residuals = tuple(
        observed - predicted
        for observed, predicted in zip(outcomes, outcome_predictions, strict=True)
    )
    treatment_residuals = tuple(
        observed - predicted
        for observed, predicted in zip(treatments, treatment_predictions, strict=True)
    )
    ordered_ids = tuple(dict.fromkeys(subgroup_ids))
    critical = _finite(
        float(norm.ppf(1.0 - (1.0 - confidence_level) / 2.0)),
        "hte.inference.nonfinite_critical_value",
    )
    groups = tuple(
        _estimate_group(
            subgroup_id,
            subgroup_ids,
            outcome_residuals,
            treatment_residuals,
            residual_tolerance,
            critical,
        )
        for subgroup_id in ordered_ids
    )
    if len(groups) < 2:
        raise HTENumericalError(
            "hte.heterogeneity.insufficient_groups",
            "Direct heterogeneity inference requires at least two supported groups.",
        )
    reference = groups[0]
    contrasts = tuple(_contrast(reference, group, critical) for group in groups[1:])
    global_evidence = _global_test(groups, confidence_level)
    return HTEComputation(
        groups=groups,
        contrasts=contrasts,
        global_heterogeneity=global_evidence,
    )


def holm_adjust(p_values: tuple[float, ...]) -> tuple[float, ...]:
    """Return Holm-adjusted p-values in their original deterministic order."""
    if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in p_values):
        raise HTENumericalError(
            "hte.multiplicity.invalid_p_value",
            "Holm adjustment requires finite probabilities.",
        )
    ordered = sorted(enumerate(p_values), key=lambda item: (item[1], item[0]))
    adjusted = [0.0] * len(p_values)
    running = 0.0
    count = len(p_values)
    for rank, (original_index, p_value) in enumerate(ordered):
        running = max(running, min(1.0, (count - rank) * p_value))
        adjusted[original_index] = running
    return tuple(adjusted)


def estimate_orthogonal_group(
    *,
    outcomes: tuple[float, ...],
    treatments: tuple[float, ...],
    outcome_predictions: tuple[float, ...],
    treatment_predictions: tuple[float, ...],
    subgroup_id: str,
    confidence_level: float,
    residual_tolerance: float,
) -> HTEGroupComputation:
    """Estimate one subgroup without implying global heterogeneity evidence."""
    subgroup_ids = (subgroup_id,) * len(outcomes)
    _validate_inputs(
        outcomes,
        treatments,
        outcome_predictions,
        treatment_predictions,
        subgroup_ids,
        confidence_level,
        residual_tolerance,
    )
    critical = _finite(
        float(norm.ppf(1.0 - (1.0 - confidence_level) / 2.0)),
        "hte.inference.nonfinite_critical_value",
    )
    return _estimate_group(
        subgroup_id,
        subgroup_ids,
        tuple(
            value - predicted
            for value, predicted in zip(outcomes, outcome_predictions, strict=True)
        ),
        tuple(
            value - predicted
            for value, predicted in zip(treatments, treatment_predictions, strict=True)
        ),
        residual_tolerance,
        critical,
    )


def _estimate_group(
    subgroup_id: str,
    subgroup_ids: tuple[str, ...],
    outcome_residuals: tuple[float, ...],
    treatment_residuals: tuple[float, ...],
    tolerance: float,
    critical: float,
) -> HTEGroupComputation:
    indices = tuple(index for index, value in enumerate(subgroup_ids) if value == subgroup_id)
    sample_size = len(indices)
    if sample_size < 2:
        raise HTENumericalError(
            "hte.subgroup.insufficient_rows",
            "Subgroup uncertainty requires at least two retained observations.",
        )
    denominator = math.fsum(treatment_residuals[index] ** 2 for index in indices)
    if denominator <= tolerance:
        raise HTENumericalError(
            "hte.subgroup.degenerate_treatment_residual",
            "A subgroup has insufficient residual treatment variation.",
        )
    numerator = math.fsum(
        treatment_residuals[index] * outcome_residuals[index] for index in indices
    )
    estimate = _finite(numerator / denominator, "hte.inference.nonfinite_estimate")
    mean_squared_treatment_residual = denominator / sample_size
    influences = tuple(
        treatment_residuals[index]
        * (outcome_residuals[index] - estimate * treatment_residuals[index])
        / mean_squared_treatment_residual
        for index in indices
    )
    variance = _finite(
        math.fsum(value * value for value in influences) / (sample_size * (sample_size - 1)),
        "hte.inference.nonfinite_variance",
    )
    standard_error = _finite(math.sqrt(variance), "hte.inference.nonfinite_standard_error")
    if standard_error <= 0.0:
        raise HTENumericalError(
            "hte.inference.degenerate_standard_error",
            "Subgroup inference requires positive uncertainty.",
        )
    statistic = _finite(estimate / standard_error, "hte.inference.nonfinite_statistic")
    p_value = _probability(2.0 * float(norm.sf(abs(statistic))))
    return HTEGroupComputation(
        subgroup_id=subgroup_id,
        sample_size=sample_size,
        estimate=estimate,
        standard_error=standard_error,
        statistic=statistic,
        p_value=p_value,
        confidence_interval_lower=_finite(
            estimate - critical * standard_error,
            "hte.inference.nonfinite_interval",
        ),
        confidence_interval_upper=_finite(
            estimate + critical * standard_error,
            "hte.inference.nonfinite_interval",
        ),
        estimate_variance=variance,
    )


def _contrast(
    reference: HTEGroupComputation,
    comparison: HTEGroupComputation,
    critical: float,
) -> HTEContrastComputation:
    estimate = comparison.estimate - reference.estimate
    standard_error = math.sqrt(reference.estimate_variance + comparison.estimate_variance)
    statistic = _finite(estimate / standard_error, "hte.interaction.nonfinite_statistic")
    return HTEContrastComputation(
        reference_subgroup_id=reference.subgroup_id,
        comparison_subgroup_id=comparison.subgroup_id,
        estimate=estimate,
        standard_error=standard_error,
        statistic=statistic,
        p_value=_probability(2.0 * float(norm.sf(abs(statistic)))),
        confidence_interval_lower=estimate - critical * standard_error,
        confidence_interval_upper=estimate + critical * standard_error,
    )


def _global_test(
    groups: tuple[HTEGroupComputation, ...],
    confidence_level: float,
) -> HTEGlobalComputation:
    reference = groups[0]
    comparisons = groups[1:]
    differences = tuple(group.estimate - reference.estimate for group in comparisons)
    inverse_diagonal = tuple(1.0 / group.estimate_variance for group in comparisons)
    weighted_square = math.fsum(
        difference * difference * inverse
        for difference, inverse in zip(differences, inverse_diagonal, strict=True)
    )
    weighted_sum = math.fsum(
        difference * inverse
        for difference, inverse in zip(differences, inverse_diagonal, strict=True)
    )
    inverse_sum = math.fsum(inverse_diagonal)
    statistic = _finite(
        weighted_square
        - reference.estimate_variance
        * weighted_sum**2
        / (1.0 + reference.estimate_variance * inverse_sum),
        "hte.heterogeneity.nonfinite_statistic",
    )
    statistic = max(0.0, statistic)
    degrees_of_freedom = len(comparisons)
    p_value = _probability(float(chi2.sf(statistic, degrees_of_freedom)))
    return HTEGlobalComputation(
        statistic=statistic,
        degrees_of_freedom=degrees_of_freedom,
        p_value=p_value,
        detected=p_value < 1.0 - confidence_level,
    )


def _validate_inputs(
    outcomes: tuple[float, ...],
    treatments: tuple[float, ...],
    outcome_predictions: tuple[float, ...],
    treatment_predictions: tuple[float, ...],
    subgroup_ids: tuple[str, ...],
    confidence_level: float,
    residual_tolerance: float,
) -> None:
    lengths = {
        len(outcomes),
        len(treatments),
        len(outcome_predictions),
        len(treatment_predictions),
        len(subgroup_ids),
    }
    if len(lengths) != 1 or not outcomes:
        raise HTENumericalError(
            "hte.inference.invalid_shape",
            "Orthogonal interaction inputs must align and be non-empty.",
        )
    numeric = (*outcomes, *treatments, *outcome_predictions, *treatment_predictions)
    if any(not math.isfinite(value) for value in numeric):
        raise HTENumericalError(
            "hte.inference.nonfinite_input",
            "Orthogonal interaction inputs must be finite.",
        )
    if not 0.0 < confidence_level < 1.0 or residual_tolerance < 0.0:
        raise HTENumericalError(
            "hte.inference.invalid_configuration",
            "Confidence and residual-tolerance settings are invalid.",
        )
    if any(not subgroup_id for subgroup_id in subgroup_ids):
        raise HTENumericalError(
            "hte.inference.invalid_subgroup",
            "Every retained observation requires a subgroup identifier.",
        )


def _finite(value: float, code: str) -> float:
    if not math.isfinite(value):
        raise HTENumericalError(code, "Heterogeneous-effect inference produced a non-finite value.")
    return value


def _probability(value: float) -> float:
    checked = _finite(value, "hte.inference.nonfinite_p_value")
    if not 0.0 <= checked <= 1.0:
        raise HTENumericalError(
            "hte.inference.invalid_p_value",
            "Heterogeneous-effect inference produced an invalid probability.",
        )
    return max(math.nextafter(0.0, 1.0), min(1.0, checked))


__all__ = [
    "HTEComputation",
    "HTEContrastComputation",
    "HTEGlobalComputation",
    "HTEGroupComputation",
    "HTENumericalError",
    "estimate_grouped_orthogonal_effects",
    "estimate_orthogonal_group",
    "holm_adjust",
]
