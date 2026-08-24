"""Diagnostic-only differential pre-trend evaluation for bounded DiD."""

from __future__ import annotations

import math
from numbers import Real

from .models import (
    DidPretrendAvailability,
    DidPretrendDiagnostic,
    DifferenceInDifferencesExecutionRequest,
)
from .numerics import (
    DidNumericalError,
    assess_cluster_policy,
    cluster_robust_inference,
    fit_pretrend_ols,
)
from .validation import DidPretrendObservation, DidValidationResult


def evaluate_pretrend(
    validated: DidValidationResult,
    execution: DifferenceInDifferencesExecutionRequest,
) -> DidPretrendDiagnostic:
    """Return diagnostic evidence without changing the canonical DiD ATT estimand."""
    extra_count = len(execution.extra_pre_periods)
    if extra_count == 0:
        return DidPretrendDiagnostic(
            availability=DidPretrendAvailability.NOT_REQUESTED,
            message="No extra pre-treatment periods were requested.",
        )
    period_count = extra_count + 1
    if period_count < 3:
        return _unavailable(
            period_count,
            "At least three total pre-treatment periods are required for diagnostic evidence.",
        )

    expected_units = {item.unit_id for item in validated.observations}
    by_key: dict[tuple[object, int], list[DidPretrendObservation]] = {}
    for observation in validated.pretrend_observations:
        by_key.setdefault((observation.unit_id, observation.period_index), []).append(observation)
    expected_keys = {
        (unit_id, period_index)
        for unit_id in expected_units
        for period_index in range(period_count)
    }
    if set(by_key) != expected_keys or any(len(items) != 1 for items in by_key.values()):
        return _unavailable(
            period_count,
            "Complete one-row-per-unit coverage is required across diagnostic pre-periods.",
        )
    observations = tuple(items[0] for items in by_key.values())
    if any(item.treated is None or not _finite_real(item.outcome) for item in observations):
        return _unavailable(
            period_count,
            "Complete finite outcomes and stable groups are required for pre-trend evidence.",
        )
    policy = assess_cluster_policy(validated.sample_counts, execution.configuration)
    if not policy.inference_supported:
        return _unavailable(
            period_count,
            "The cluster count cannot support the configured pre-trend inference policy.",
        )
    units = execution.analysis_request.identification.units
    if units is None:
        return _unavailable(period_count, "Analysis-unit semantics are unavailable.")
    try:
        fit = fit_pretrend_ols(observations)
        inference = cluster_robust_inference(
            fit,
            cluster_unit=units.analysis_unit,
            config=execution.configuration,
        )
    except DidNumericalError:
        return _unavailable(
            period_count,
            "Finite clustered pre-trend inference is unavailable for the supplied data.",
        )
    concern = inference.p_value < 1.0 - execution.configuration.confidence_level
    message = (
        "Diagnostic evidence indicates differential pre-treatment trends; this concerns parallel "
        "trends but does not establish the identifying assumption."
        if concern
        else "Diagnostic evidence did not detect differential pre-treatment trends; this does not "
        "establish the parallel-trends assumption."
    )
    return DidPretrendDiagnostic(
        availability=DidPretrendAvailability.AVAILABLE,
        message=message,
        period_count=period_count,
        trend_difference=fit.coefficients[3],
        standard_error=inference.standard_error,
        statistic=inference.statistic,
        degrees_of_freedom=inference.degrees_of_freedom,
        p_value=inference.p_value,
        confidence_interval=inference.confidence_interval,
        evidence_concern=concern,
    )


def _unavailable(period_count: int, message: str) -> DidPretrendDiagnostic:
    return DidPretrendDiagnostic(
        availability=DidPretrendAvailability.UNAVAILABLE,
        message=message,
        period_count=period_count,
    )


def _finite_real(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, Real) and math.isfinite(float(value))


__all__ = ["evaluate_pretrend"]
