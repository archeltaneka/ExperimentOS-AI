"""Unadjusted Welch t estimates for continuous randomized outcomes."""

from __future__ import annotations

import math
from collections.abc import Sequence

from ..estimands import EstimandDefinition
from ..metrics import MeasuredValue, MetricDefinition
from ..provenance import (
    AnalysisWarning,
    AssumptionAssessment,
    AssumptionStatus,
    DiagnosticSeverity,
    ProvenanceRecord,
)
from ..uncertainty import ConfidenceInterval
from .config import RandomizedAnalysisConfig
from .descriptive import RandomizedDescriptiveError, summarize_continuous_arm
from .models import (
    AlternativeHypothesis,
    ComputationStatus,
    Conclusion,
    EvidenceCategory,
    PointEffect,
    PracticalSignificance,
    RandomizedAbstentionReason,
    RandomizedAnalysisResult,
    RandomizedDiagnostic,
    RandomizedDiagnosticCategory,
    RandomizedDiagnosticStatus,
    RandomizedHypothesis,
    RandomizedTestResult,
    RandomizedTestType,
    RelativeEffectAvailability,
    RelativeEffectReason,
)
from .numerics import RandomizedNumericalError, t_critical_value, two_sided_t_p_value


def analyze_continuous_welch(
    *,
    request_id: str,
    metric: MetricDefinition,
    estimand: EstimandDefinition,
    treatment_arm_id: str,
    treatment_values: Sequence[object],
    control_arm_id: str,
    control_values: Sequence[object],
    provenance: tuple[ProvenanceRecord, ...],
    configuration: RandomizedAnalysisConfig | None = None,
    alternative: AlternativeHypothesis = AlternativeHypothesis.TWO_SIDED,
) -> RandomizedAnalysisResult:
    """Estimate treatment minus control with an unadjusted two-sided Welch t procedure."""
    config = configuration or RandomizedAnalysisConfig()

    if alternative is not AlternativeHypothesis.TWO_SIDED:
        return _unsupported_alternative_result(
            request_id=request_id,
            metric=metric,
            estimand=estimand,
            provenance=provenance,
            configuration=config,
            alternative=alternative,
        )

    invalid_input = _invalid_input_result(
        request_id=request_id,
        metric=metric,
        estimand=estimand,
        treatment_arm_id=treatment_arm_id,
        treatment_values=treatment_values,
        control_arm_id=control_arm_id,
        control_values=control_values,
        provenance=provenance,
        configuration=config,
    )
    if invalid_input is not None:
        return invalid_input

    if treatment_arm_id == control_arm_id:
        return _abstained_result(
            request_id=request_id,
            metric=metric,
            estimand=estimand,
            provenance=provenance,
            configuration=config,
            code="duplicate_arm_identifier",
            category=RandomizedDiagnosticCategory.INPUT,
            message="Treatment and control arm identifiers must differ.",
        )

    if len(treatment_values) < 2 or len(control_values) < 2:
        code = (
            "one_observation_arm"
            if len(treatment_values) == 1 or len(control_values) == 1
            else "insufficient_observations"
        )
        return _abstained_result(
            request_id=request_id,
            metric=metric,
            estimand=estimand,
            provenance=provenance,
            configuration=config,
            code=code,
            category=RandomizedDiagnosticCategory.SAMPLE,
            message="Each continuous arm requires at least two observations.",
            context={"control_n": len(control_values), "treatment_n": len(treatment_values)},
        )

    if (
        len(treatment_values) < config.minimum_observations_per_arm
        or len(control_values) < config.minimum_observations_per_arm
    ):
        return _abstained_result(
            request_id=request_id,
            metric=metric,
            estimand=estimand,
            provenance=provenance,
            configuration=config,
            code="minimum_observations_not_met",
            category=RandomizedDiagnosticCategory.SAMPLE,
            message="At least the configured minimum observations are required in each arm.",
            context={
                "control_n": len(control_values),
                "minimum_observations_per_arm": config.minimum_observations_per_arm,
                "treatment_n": len(treatment_values),
            },
        )

    try:
        treatment_summary = summarize_continuous_arm(treatment_arm_id, treatment_values)
        control_summary = summarize_continuous_arm(control_arm_id, control_values)
        standard_error, degrees_of_freedom = _welch_uncertainty(
            treatment_variance=treatment_summary.sample_variance,
            treatment_n=treatment_summary.n,
            control_variance=control_summary.sample_variance,
            control_n=control_summary.n,
        )
    except RandomizedDescriptiveError:
        return _abstained_result(
            request_id=request_id,
            metric=metric,
            estimand=estimand,
            provenance=provenance,
            configuration=config,
            code="nonfinite_continuous_outcome",
            category=RandomizedDiagnosticCategory.INPUT,
            message="Continuous outcomes must be finite real numbers with a finite summary.",
        )
    except (ArithmeticError, ValueError):
        return _abstained_result(
            request_id=request_id,
            metric=metric,
            estimand=estimand,
            provenance=provenance,
            configuration=config,
            code="continuous_computation_error",
            category=RandomizedDiagnosticCategory.COMPUTATION,
            message="Welch uncertainty could not be computed as finite values.",
        )

    if standard_error == 0.0:
        return _abstained_result(
            request_id=request_id,
            metric=metric,
            estimand=estimand,
            provenance=provenance,
            configuration=config,
            code="zero_standard_error",
            category=RandomizedDiagnosticCategory.COMPUTATION,
            message="Zero within-arm variance makes the Welch t statistic undefined.",
            context={
                "control_sample_variance": control_summary.sample_variance,
                "treatment_sample_variance": treatment_summary.sample_variance,
            },
        )

    effect = treatment_summary.mean - control_summary.mean
    try:
        statistic = effect / standard_error
        p_value = two_sided_t_p_value(statistic, degrees_of_freedom)
        critical_value = t_critical_value(config.alpha, degrees_of_freedom)
        margin = critical_value * standard_error
        interval = ConfidenceInterval(
            lower=effect - margin,
            upper=effect + margin,
            confidence_level=config.confidence_level,
        )
    except (ArithmeticError, RandomizedNumericalError, ValueError):
        return _abstained_result(
            request_id=request_id,
            metric=metric,
            estimand=estimand,
            provenance=provenance,
            configuration=config,
            code="continuous_computation_error",
            category=RandomizedDiagnosticCategory.COMPUTATION,
            message="Welch test statistics or confidence interval were not finite.",
        )

    (
        relative_effect,
        relative_availability,
        relative_reason,
        diagnostics,
        warnings,
    ) = _relative_effect(effect, control_summary.mean)
    if relative_effect is not None and not math.isfinite(relative_effect):
        return _abstained_result(
            request_id=request_id,
            metric=metric,
            estimand=estimand,
            provenance=provenance,
            configuration=config,
            code="nonfinite_relative_effect",
            category=RandomizedDiagnosticCategory.RESULT,
            message="Relative lift is not representable as a finite value.",
            context={
                "absolute_effect": effect,
                "control_mean": control_summary.mean,
            },
        )
    return RandomizedAnalysisResult(
        request_id=request_id,
        metric=metric,
        estimand=estimand,
        status=ComputationStatus.COMPLETED,
        conclusion=(
            Conclusion.STATISTICALLY_SIGNIFICANT
            if p_value <= config.alpha
            else Conclusion.NOT_STATISTICALLY_SIGNIFICANT
        ),
        practical_significance=PracticalSignificance.NOT_ASSESSED,
        evidence_category=EvidenceCategory.RANDOMIZED_DESIGN_WITH_LIMITED_ASSUMPTIONS,
        treatment_summary=treatment_summary,
        control_summary=control_summary,
        point_effect=PointEffect(
            absolute_effect=MeasuredValue(value=effect, unit=metric.unit),
            relative_effect=relative_effect,
            relative_effect_availability=relative_availability,
            relative_effect_reason=relative_reason,
        ),
        test_result=RandomizedTestResult(
            test_type=RandomizedTestType.WELCH_T,
            standard_error=standard_error,
            statistic=statistic,
            degrees_of_freedom=degrees_of_freedom,
            p_value=p_value,
            confidence_interval=interval,
        ),
        assumptions=_assumptions(),
        diagnostics=diagnostics,
        warnings=warnings,
        provenance=provenance,
        configuration=config,
    )


def _invalid_input_result(
    *,
    request_id: str,
    metric: MetricDefinition,
    estimand: EstimandDefinition,
    treatment_arm_id: str,
    treatment_values: Sequence[object],
    control_arm_id: str,
    control_values: Sequence[object],
    provenance: tuple[ProvenanceRecord, ...],
    configuration: RandomizedAnalysisConfig,
) -> RandomizedAnalysisResult | None:
    for values in (treatment_values, control_values):
        for value in values:
            if not _is_finite_real(value):
                return _abstained_result(
                    request_id=request_id,
                    metric=metric,
                    estimand=estimand,
                    provenance=provenance,
                    configuration=configuration,
                    code="nonfinite_continuous_outcome",
                    category=RandomizedDiagnosticCategory.INPUT,
                    message="Continuous outcomes must be finite real numbers.",
                )
    return None


def _is_finite_real(value: object) -> bool:
    if isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def _welch_uncertainty(
    *,
    treatment_variance: float,
    treatment_n: int,
    control_variance: float,
    control_n: int,
) -> tuple[float, float]:
    treatment_component = treatment_variance / treatment_n
    control_component = control_variance / control_n
    variance_of_effect = treatment_component + control_component
    standard_error = math.sqrt(variance_of_effect)
    denominator = (treatment_component**2) / (treatment_n - 1) + (control_component**2) / (
        control_n - 1
    )
    degrees_of_freedom = (variance_of_effect**2) / denominator if denominator else 0.0
    if not math.isfinite(standard_error) or not math.isfinite(degrees_of_freedom):
        raise ValueError("Welch uncertainty must be finite")
    return standard_error, degrees_of_freedom


def _relative_effect(
    effect: float,
    control_mean: float,
) -> tuple[
    float | None,
    RelativeEffectAvailability,
    RelativeEffectReason | None,
    tuple[RandomizedDiagnostic, ...],
    tuple[AnalysisWarning, ...],
]:
    if control_mean != 0.0:
        return effect / control_mean, RelativeEffectAvailability.AVAILABLE, None, (), ()

    diagnostic = RandomizedDiagnostic(
        code="zero_control_baseline",
        category=RandomizedDiagnosticCategory.RESULT,
        severity=DiagnosticSeverity.WARNING,
        status=RandomizedDiagnosticStatus.UNAVAILABLE,
        message="Relative lift is unavailable because the control mean is zero.",
        context={"control_mean": control_mean},
    )
    warning = AnalysisWarning(
        code="zero_control_baseline",
        message="Relative lift was not reported because the control mean is zero.",
        scope="point_effect",
    )
    return (
        None,
        RelativeEffectAvailability.UNAVAILABLE,
        RelativeEffectReason.ZERO_CONTROL_BASELINE,
        (diagnostic,),
        (warning,),
    )


def _abstained_result(
    *,
    request_id: str,
    metric: MetricDefinition,
    estimand: EstimandDefinition,
    provenance: tuple[ProvenanceRecord, ...],
    configuration: RandomizedAnalysisConfig,
    code: str,
    category: RandomizedDiagnosticCategory,
    message: str,
    context: dict[str, int | float] | None = None,
) -> RandomizedAnalysisResult:
    return RandomizedAnalysisResult(
        request_id=request_id,
        metric=metric,
        estimand=estimand,
        status=ComputationStatus.ABSTAINED,
        conclusion=Conclusion.INCONCLUSIVE,
        practical_significance=PracticalSignificance.NOT_ASSESSED,
        evidence_category=EvidenceCategory.RANDOMIZED_DESIGN_WITH_LIMITED_ASSUMPTIONS,
        assumptions=_assumptions(),
        diagnostics=(
            RandomizedDiagnostic(
                code=code,
                category=category,
                severity=DiagnosticSeverity.ERROR,
                status=RandomizedDiagnosticStatus.FAILED,
                message=message,
                context=context or (),
                recommended_action=(
                    "Provide finite continuous outcomes with adequate variation per arm."
                ),
            ),
        ),
        warnings=(),
        provenance=provenance,
        configuration=configuration,
        abstention_reason=RandomizedAbstentionReason(
            code=code,
            message=message,
            missing_or_invalid_information=(code,),
        ),
    )


def _unsupported_alternative_result(
    *,
    request_id: str,
    metric: MetricDefinition,
    estimand: EstimandDefinition,
    provenance: tuple[ProvenanceRecord, ...],
    configuration: RandomizedAnalysisConfig,
    alternative: AlternativeHypothesis,
) -> RandomizedAnalysisResult:
    code = "unsupported_alternative_hypothesis"
    message = "Only a declared two-sided alternative hypothesis is supported."
    return RandomizedAnalysisResult(
        request_id=request_id,
        metric=metric,
        estimand=estimand,
        hypothesis=RandomizedHypothesis(alternative=alternative),
        status=ComputationStatus.UNSUPPORTED,
        conclusion=Conclusion.UNSUPPORTED,
        practical_significance=PracticalSignificance.NOT_ASSESSED,
        evidence_category=EvidenceCategory.NO_RANDOMIZED_EVIDENCE,
        assumptions=_assumptions(),
        diagnostics=(
            RandomizedDiagnostic(
                code=code,
                category=RandomizedDiagnosticCategory.CONFIGURATION,
                severity=DiagnosticSeverity.ERROR,
                status=RandomizedDiagnosticStatus.FAILED,
                message=message,
                recommended_action="Declare a two-sided alternative hypothesis for v1 analysis.",
            ),
        ),
        warnings=(),
        provenance=provenance,
        configuration=configuration,
        abstention_reason=RandomizedAbstentionReason(
            code=code,
            message=message,
            missing_or_invalid_information=(code,),
        ),
    )


def _assumptions() -> tuple[AssumptionAssessment, ...]:
    return (
        AssumptionAssessment(
            code="random_assignment",
            statement="Treatment assignment is randomized for the analyzed population.",
            status=AssumptionStatus.UNASSESSED,
        ),
        AssumptionAssessment(
            code="independent_observations",
            statement="Observed outcomes are independent within and between analysis arms.",
            status=AssumptionStatus.UNASSESSED,
        ),
    )


__all__ = ["analyze_continuous_welch"]
