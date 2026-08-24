"""Finite-safe manual and regression numerics for bounded DiD analysis."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real

import scipy.stats as _stats  # type: ignore[import-untyped]

from ...metrics import AnalysisUnit
from ...provenance import DiagnosticSeverity
from ...uncertainty import ConfidenceInterval
from .models import (
    DidCellMeans,
    DidDiagnostic,
    DidDiagnosticCategory,
    DidDiagnosticStatus,
    DidSampleCounts,
    DidTestResult,
    DidVarianceEstimator,
    DifferenceInDifferencesConfig,
)
from .validation import DidObservation, DidPretrendObservation

_COEFFICIENT_NAMES = ("intercept", "treated", "post", "treated_post")


class DidNumericalError(ValueError):
    """Raised when owned DiD numerical helpers cannot return finite results."""


@dataclass(frozen=True, slots=True)
class DidRegressionFit:
    """Internal OLS values required for owned clustered inference."""

    coefficient_names: tuple[str, str, str, str]
    coefficients: tuple[float, float, float, float]
    design_matrix: tuple[tuple[float, float, float, float], ...]
    outcomes: tuple[float, ...]
    residuals: tuple[float, ...]
    clusters: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class DidClusterPolicyAssessment:
    """Central few-cluster policy outcome used before numerical inference."""

    inference_supported: bool
    diagnostics: tuple[DidDiagnostic, ...]


def manual_did(observations: tuple[DidObservation, ...]) -> DidCellMeans:
    """Calculate the four-cell DiD ATT contrast without regression interpretation."""
    cells: dict[tuple[bool, bool], list[float]] = {
        (True, False): [],
        (True, True): [],
        (False, False): [],
        (False, True): [],
    }
    for observation in observations:
        cells[(observation.treated, observation.post)].append(observation.outcome)
    if any(not values for values in cells.values()):
        raise DidNumericalError("all four canonical DiD cells require observations")

    treated_pre = _mean(cells[(True, False)])
    treated_post = _mean(cells[(True, True)])
    control_pre = _mean(cells[(False, False)])
    control_post = _mean(cells[(False, True)])
    treated_change = _subtract(treated_post, treated_pre)
    control_change = _subtract(control_post, control_pre)
    estimate = _subtract(treated_change, control_change)
    return DidCellMeans(
        treated_pre_mean=treated_pre,
        treated_post_mean=treated_post,
        control_pre_mean=control_pre,
        control_post_mean=control_post,
        treated_change=treated_change,
        control_change=control_change,
        did_estimate=estimate,
        treated_pre_count=len(cells[(True, False)]),
        treated_post_count=len(cells[(True, True)]),
        control_pre_count=len(cells[(False, False)]),
        control_post_count=len(cells[(False, True)]),
    )


def fit_interaction_ols(observations: tuple[DidObservation, ...]) -> DidRegressionFit:
    """Fit ``Y ~ 1 + treated + post + treated:post`` using owned matrix helpers."""
    if len(observations) < 4:
        raise DidNumericalError("canonical interaction regression requires at least four rows")
    design = tuple(_design_row(item) for item in observations)
    outcomes = tuple(_finite(item.outcome, name="outcome") for item in observations)
    xtx = tuple(
        tuple(math.fsum(row[left] * row[right] for row in design) for right in range(4))
        for left in range(4)
    )
    xty = tuple(
        math.fsum(row[column] * outcome for row, outcome in zip(design, outcomes, strict=True))
        for column in range(4)
    )
    solved = _solve(xtx, xty)
    coefficients = (solved[0], solved[1], solved[2], solved[3])
    residuals = tuple(
        _subtract(
            outcome,
            math.fsum(
                value * coefficient for value, coefficient in zip(row, coefficients, strict=True)
            ),
        )
        for row, outcome in zip(design, outcomes, strict=True)
    )
    return DidRegressionFit(
        coefficient_names=_COEFFICIENT_NAMES,
        coefficients=coefficients,
        design_matrix=design,
        outcomes=outcomes,
        residuals=residuals,
        clusters=tuple(item.unit_id for item in observations),
    )


def fit_pretrend_ols(
    observations: tuple[DidPretrendObservation, ...],
) -> DidRegressionFit:
    """Fit the diagnostic ``Y ~ 1 + treated + period + treated:period`` model."""
    if len(observations) < 4:
        raise DidNumericalError("pre-trend regression requires at least four rows")
    design = tuple(
        (
            1.0,
            1.0 if item.treated else 0.0,
            float(item.period_index),
            (1.0 if item.treated else 0.0) * float(item.period_index),
        )
        for item in observations
    )
    outcomes = tuple(_finite(item.outcome, name="pre-trend outcome") for item in observations)
    xtx = tuple(
        tuple(math.fsum(row[left] * row[right] for row in design) for right in range(4))
        for left in range(4)
    )
    xty = tuple(
        math.fsum(row[column] * outcome for row, outcome in zip(design, outcomes, strict=True))
        for column in range(4)
    )
    solved = _solve(xtx, xty)
    coefficients = (solved[0], solved[1], solved[2], solved[3])
    residuals = tuple(
        _subtract(
            outcome,
            math.fsum(
                value * coefficient for value, coefficient in zip(row, coefficients, strict=True)
            ),
        )
        for row, outcome in zip(design, outcomes, strict=True)
    )
    return DidRegressionFit(
        coefficient_names=("intercept", "treated", "period", "treated_period"),
        coefficients=coefficients,
        design_matrix=design,
        outcomes=outcomes,
        residuals=residuals,
        clusters=tuple(item.unit_id for item in observations),
    )


def assess_cluster_policy(
    counts: DidSampleCounts,
    config: DifferenceInDifferencesConfig,
) -> DidClusterPolicyAssessment:
    """Apply the one centralized minimum/few-cluster policy."""
    diagnostics: list[DidDiagnostic] = []
    enough_total = counts.retained_units >= config.minimum_cluster_count
    enough_groups = (
        counts.treated_retained_units >= config.minimum_cluster_count_per_group
        and counts.control_retained_units >= config.minimum_cluster_count_per_group
    )
    if not enough_total:
        diagnostics.append(
            _inference_diagnostic(
                "did.insufficient_clusters",
                "The retained unit-cluster count is below the configured minimum.",
                DiagnosticSeverity.ERROR,
                unavailable=True,
                context={"cluster_count": counts.retained_units},
            )
        )
    if not enough_groups:
        diagnostics.append(
            _inference_diagnostic(
                "did.insufficient_group_clusters",
                "Each group must meet the configured minimum unit-cluster count.",
                DiagnosticSeverity.ERROR,
                unavailable=True,
                context={
                    "control_cluster_count": counts.control_retained_units,
                    "treated_cluster_count": counts.treated_retained_units,
                },
            )
        )
    if enough_total and counts.retained_units < config.few_cluster_warning_threshold:
        diagnostics.append(
            _inference_diagnostic(
                "did.few_clusters",
                "Cluster-robust inference uses fewer clusters than the warning threshold.",
                DiagnosticSeverity.WARNING,
                context={"cluster_count": counts.retained_units},
            )
        )
    return DidClusterPolicyAssessment(
        inference_supported=enough_total and enough_groups,
        diagnostics=tuple(sorted(diagnostics, key=lambda item: item.code)),
    )


def cluster_robust_inference(
    fit: DidRegressionFit,
    *,
    cluster_unit: AnalysisUnit,
    config: DifferenceInDifferencesConfig,
) -> DidTestResult:
    """Return CR1 unit-clustered Student-t inference for the interaction coefficient."""
    row_count = len(fit.outcomes)
    parameter_count = len(fit.coefficients)
    if row_count <= parameter_count:
        raise DidNumericalError("CR1 inference requires more rows than coefficients")
    cluster_rows: dict[object, list[int]] = {}
    for index, cluster in enumerate(fit.clusters):
        cluster_rows.setdefault(cluster, []).append(index)
    cluster_count = len(cluster_rows)
    if cluster_count < 2:
        raise DidNumericalError("CR1 inference requires at least two unit clusters")

    xtx = tuple(
        tuple(
            math.fsum(row[left] * row[right] for row in fit.design_matrix)
            for right in range(parameter_count)
        )
        for left in range(parameter_count)
    )
    bread = _inverse(xtx)
    scores = tuple(
        tuple(
            math.fsum(fit.design_matrix[index][column] * fit.residuals[index] for index in indexes)
            for column in range(parameter_count)
        )
        for indexes in cluster_rows.values()
    )
    meat = tuple(
        tuple(
            math.fsum(score[left] * score[right] for score in scores)
            for right in range(parameter_count)
        )
        for left in range(parameter_count)
    )
    raw_covariance = _matmul(_matmul(bread, meat), bread)
    correction = (cluster_count / (cluster_count - 1)) * (
        (row_count - 1) / (row_count - parameter_count)
    )
    covariance = tuple(
        tuple(_finite(correction * value, name="CR1 covariance") for value in row)
        for row in raw_covariance
    )
    interaction_variance = covariance[3][3]
    if interaction_variance < -1e-12:
        raise DidNumericalError("clustered interaction variance must not be negative")
    standard_error = _finite(math.sqrt(max(0.0, interaction_variance)), name="standard error")
    effect = fit.coefficients[3]
    degrees_of_freedom = cluster_count - 1
    if standard_error == 0.0:
        if effect != 0.0:
            raise DidNumericalError("nonzero effect has zero clustered uncertainty")
        statistic = 0.0
        p_value = 1.0
        lower = effect
        upper = effect
    else:
        statistic = _finite(effect / standard_error, name="test statistic")
        p_value = _probability(
            2.0 * _stats.t.sf(abs(statistic), degrees_of_freedom),
            name="two-sided p-value",
        )
        alpha = 1.0 - config.confidence_level
        critical = _finite(
            _stats.t.isf(alpha / 2.0, degrees_of_freedom),
            name="t critical value",
        )
        lower = _finite(effect - critical * standard_error, name="confidence lower bound")
        upper = _finite(effect + critical * standard_error, name="confidence upper bound")
    return DidTestResult(
        variance_estimator=DidVarianceEstimator.CLUSTER_ROBUST_CR1,
        cluster_unit=cluster_unit,
        cluster_count=cluster_count,
        standard_error=standard_error,
        statistic=statistic,
        degrees_of_freedom=degrees_of_freedom,
        p_value=p_value,
        confidence_interval=ConfidenceInterval(
            lower=lower,
            upper=upper,
            confidence_level=config.confidence_level,
        ),
    )


def _design_row(observation: DidObservation) -> tuple[float, float, float, float]:
    treated = 1.0 if observation.treated else 0.0
    post = 1.0 if observation.post else 0.0
    return (1.0, treated, post, treated * post)


def _solve(
    matrix: tuple[tuple[float, ...], ...],
    vector: tuple[float, ...],
) -> tuple[float, ...]:
    size = len(vector)
    if len(matrix) != size or any(len(row) != size for row in matrix):
        raise DidNumericalError("linear system must be square")
    augmented = [
        [_finite(value, name="matrix value") for value in row]
        + [_finite(vector[index], name="vector value")]
        for index, row in enumerate(matrix)
    ]
    for column in range(size):
        pivot_index = max(range(column, size), key=lambda index: abs(augmented[index][column]))
        pivot = augmented[pivot_index][column]
        if abs(pivot) <= 1e-12:
            raise DidNumericalError("canonical interaction design matrix is rank deficient")
        augmented[column], augmented[pivot_index] = augmented[pivot_index], augmented[column]
        augmented[column] = [
            _finite(value / pivot, name="normalized row") for value in augmented[column]
        ]
        for row_index in range(size):
            if row_index == column:
                continue
            factor = augmented[row_index][column]
            augmented[row_index] = [
                _finite(current - factor * pivot_value, name="eliminated row")
                for current, pivot_value in zip(
                    augmented[row_index],
                    augmented[column],
                    strict=True,
                )
            ]
    return tuple(_finite(row[-1], name="coefficient") for row in augmented)


def _inverse(matrix: tuple[tuple[float, ...], ...]) -> tuple[tuple[float, ...], ...]:
    size = len(matrix)
    columns = tuple(
        _solve(matrix, tuple(1.0 if row == column else 0.0 for row in range(size)))
        for column in range(size)
    )
    return tuple(tuple(columns[column][row] for column in range(size)) for row in range(size))


def _matmul(
    left: tuple[tuple[float, ...], ...],
    right: tuple[tuple[float, ...], ...],
) -> tuple[tuple[float, ...], ...]:
    if not left or not right or len(left[0]) != len(right):
        raise DidNumericalError("matrix dimensions are incompatible")
    return tuple(
        tuple(
            _finite(
                math.fsum(left_row[index] * right[index][column] for index in range(len(right))),
                name="matrix product",
            )
            for column in range(len(right[0]))
        )
        for left_row in left
    )


def _mean(values: list[float]) -> float:
    return _finite(math.fsum(values) / len(values), name="cell mean")


def _subtract(left: float, right: float) -> float:
    return _finite(left - right, name="difference")


def _finite(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise DidNumericalError(f"{name} must be a finite real number")
    converted = float(value)
    if not math.isfinite(converted):
        raise DidNumericalError(f"{name} must be a finite real number")
    return converted


def _probability(value: object, *, name: str) -> float:
    converted = _finite(value, name=name)
    if not 0.0 <= converted <= 1.0:
        raise DidNumericalError(f"{name} must be between zero and one")
    return math.nextafter(0.0, 1.0) if converted == 0.0 else converted


def _inference_diagnostic(
    code: str,
    message: str,
    severity: DiagnosticSeverity,
    *,
    unavailable: bool = False,
    context: dict[str, object],
) -> DidDiagnostic:
    return DidDiagnostic.model_validate(
        {
            "code": code,
            "category": DidDiagnosticCategory.INFERENCE,
            "severity": severity,
            "status": (
                DidDiagnosticStatus.UNAVAILABLE if unavailable else DidDiagnosticStatus.FAILED
            ),
            "message": message,
            "context": context,
        }
    )


__all__ = [
    "DidNumericalError",
    "DidClusterPolicyAssessment",
    "DidRegressionFit",
    "assess_cluster_policy",
    "cluster_robust_inference",
    "fit_interaction_ols",
    "fit_pretrend_ols",
    "manual_did",
]
