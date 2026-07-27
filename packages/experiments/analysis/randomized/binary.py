"""Unadjusted two-proportion z estimates for binary randomized outcomes."""

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
from .descriptive import RandomizedDescriptiveError, summarize_binary_arm
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
from .numerics import (
    RandomizedNumericalError,
    normal_critical_value,
    two_sided_normal_p_value,
)


def analyze_binary_two_proportion_z(
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
    """Estimate treatment minus control with an unadjusted two-sided z procedure.

    Hypothesis-test uncertainty uses the pooled null proportion.  The confidence
    interval uses the unpooled sampling standard error for the observed effect.
    """
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
        treatment_summary = summarize_binary_arm(treatment_arm_id, treatment_values)
        control_summary = summarize_binary_arm(control_arm_id, control_values)
        pooled_rate, pooled_standard_error = _pooled_null_uncertainty(
            treatment_successes=treatment_summary.successes,
            treatment_n=treatment_summary.n,
            control_successes=control_summary.successes,
            control_n=control_summary.n,
        )
    except (ArithmeticError, RandomizedDescriptiveError, ValueError):
        return _abstained_result(
            request_id=request_id,
            metric=metric,
            estimand=estimand,
            provenance=provenance,
            configuration=config,
            code="invalid_binary_outcome",
            category=RandomizedDiagnosticCategory.INPUT,
            message="Binary outcomes must be explicit boolean or integer zero/one values.",
        )

    if pooled_standard_error == 0.0:
        return _abstained_result(
            request_id=request_id,
            metric=metric,
            estimand=estimand,
            provenance=provenance,
            configuration=config,
            code="zero_standard_error",
            category=RandomizedDiagnosticCategory.COMPUTATION,
            message="A degenerate pooled null proportion makes the z statistic undefined.",
            context={"pooled_rate": pooled_rate},
        )

    expected_cells = _expected_cells(
        pooled_rate=pooled_rate,
        treatment_n=treatment_summary.n,
        control_n=control_summary.n,
    )
    if min(expected_cells.values()) < config.sparse_cell_threshold:
        return _abstained_result(
            request_id=request_id,
            metric=metric,
            estimand=estimand,
            provenance=provenance,
            configuration=config,
            code="sparse_cell",
            category=RandomizedDiagnosticCategory.ASSUMPTION,
            message="The two-proportion normal approximation requires adequate expected cells.",
            context={
                **expected_cells,
                "sparse_cell_threshold": config.sparse_cell_threshold,
            },
        )

    effect = treatment_summary.rate - control_summary.rate
    try:
        statistic = effect / pooled_standard_error
        p_value = two_sided_normal_p_value(statistic)
        interval_standard_error = _unpooled_interval_standard_error(
            treatment_rate=treatment_summary.rate,
            treatment_n=treatment_summary.n,
            control_rate=control_summary.rate,
            control_n=control_summary.n,
        )
        margin = normal_critical_value(config.alpha) * interval_standard_error
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
            code="binary_computation_error",
            category=RandomizedDiagnosticCategory.COMPUTATION,
            message="Two-proportion z statistics or confidence interval were not finite.",
        )

    (
        relative_effect,
        relative_availability,
        relative_reason,
        diagnostics,
        warnings,
    ) = _relative_effect(effect, control_summary.rate)
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
                "control_rate": control_summary.rate,
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
            test_type=RandomizedTestType.TWO_PROPORTION_Z,
            standard_error=pooled_standard_error,
            statistic=statistic,
            p_value=p_value,
            confidence_interval=interval,
        ),
        assumptions=_assumptions(),
        diagnostics=diagnostics,
        warnings=warnings,
        provenance=provenance,
        configuration=config,
    )


def _pooled_null_uncertainty(
    *,
    treatment_successes: int,
    treatment_n: int,
    control_successes: int,
    control_n: int,
) -> tuple[float, float]:
    pooled_rate = (treatment_successes + control_successes) / (treatment_n + control_n)
    variance = pooled_rate * (1.0 - pooled_rate) * (
        (1.0 / treatment_n) + (1.0 / control_n)
    )
    standard_error = math.sqrt(variance)
    if not math.isfinite(pooled_rate) or not math.isfinite(standard_error):
        raise ValueError("pooled null uncertainty must be finite")
    return pooled_rate, standard_error


def _unpooled_interval_standard_error(
    *,
    treatment_rate: float,
    treatment_n: int,
    control_rate: float,
    control_n: int,
) -> float:
    variance = (
        (treatment_rate * (1.0 - treatment_rate) / treatment_n)
        + (control_rate * (1.0 - control_rate) / control_n)
    )
    standard_error = math.sqrt(variance)
    if not math.isfinite(standard_error):
        raise ValueError("unpooled interval standard error must be finite")
    return standard_error


def _expected_cells(
    *,
    pooled_rate: float,
    treatment_n: int,
    control_n: int,
) -> dict[str, float]:
    return {
        "control_expected_failures": control_n * (1.0 - pooled_rate),
        "control_expected_successes": control_n * pooled_rate,
        "treatment_expected_failures": treatment_n * (1.0 - pooled_rate),
        "treatment_expected_successes": treatment_n * pooled_rate,
    }


def _relative_effect(
    effect: float,
    control_rate: float,
) -> tuple[
    float | None,
    RelativeEffectAvailability,
    RelativeEffectReason | None,
    tuple[RandomizedDiagnostic, ...],
    tuple[AnalysisWarning, ...],
]:
    if control_rate != 0.0:
        return effect / control_rate, RelativeEffectAvailability.AVAILABLE, None, (), ()

    diagnostic = RandomizedDiagnostic(
        code="zero_control_baseline",
        category=RandomizedDiagnosticCategory.RESULT,
        severity=DiagnosticSeverity.WARNING,
        status=RandomizedDiagnosticStatus.UNAVAILABLE,
        message="Relative lift is unavailable because the control rate is zero.",
        context={"control_rate": control_rate},
    )
    warning = AnalysisWarning(
        code="zero_control_baseline",
        message="Relative lift was not reported because the control rate is zero.",
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
                    "Provide valid binary outcomes with adequate expected cell counts per arm."
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


__all__ = ["analyze_binary_two_proportion_z"]
