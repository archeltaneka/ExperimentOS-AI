"""Common and capability-specific assertions on original owned results."""

from __future__ import annotations

import math

from pydantic import BaseModel

from packages.experiments.analysis.causal.advanced.quality import evaluate_advanced_quality
from packages.experiments.analysis.causal.dowhy.quality import evaluate_dowhy_quality
from packages.experiments.analysis.causal.hte.quality import evaluate_hte_quality

from ..models import CheckStatus, StatisticalCheck, StatisticalReferenceCase
from .checks import REPLAY_TOLERANCE, boundary_violations, check
from .registry import REGISTRY


def path_value(value, path):
    for part in path.split("."):
        value = (
            value[int(part)]
            if isinstance(value, (list, tuple))
            else value.get(part)
            if isinstance(value, dict)
            else getattr(value, part, None)
        )
        if value is None:
            break
    return value


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def valid_uncertainty(estimate, standard_error, interval, method):
    return bool(
        finite(estimate)
        and finite(standard_error)
        and standard_error >= 0
        and interval is not None
        and finite(interval.lower)
        and finite(interval.upper)
        and interval.lower <= estimate <= interval.upper
        and 0 < interval.confidence_level < 1
        and method
    )


def result_checks(case: StatisticalReferenceCase, result: object) -> list[StatisticalCheck]:
    """Never dump unowned objects into checks, diagnostics, or artifacts."""
    violations = boundary_violations(result)
    checks = [check("interface", "interface_leakage", not violations)]
    if violations or not isinstance(result, BaseModel):
        return checks
    try:
        type(result).model_validate(result.model_dump(mode="python"))
        valid = True
    except Exception:
        valid = False
    checks.append(check("contract", "status", valid))
    assert case.advanced is not None
    capability = REGISTRY[case.advanced.capability_id]
    codes = tuple(d.code for d in result.diagnostics)
    status = result.status.value
    success = status == "completed"
    checks.append(check("status", "status", status == case.expected_status))
    checks.append(
        check("diagnostics", "diagnostics", set(case.expected_diagnostic_codes) <= set(codes))
    )
    checks.append(check("provenance", "provenance", bool(result.provenance)))
    unsupported = (
        "UNSUPPORTED_INFERENCE" in codes or case.advanced.scenario == "unsupported_inference"
    )
    checks.append(
        check("unsupported_inference", "unsupported_inference", not (success and unsupported))
    )
    if not success:
        reason = result.abstention_reason
        normalized_reason = getattr(reason, "code", getattr(reason, "value", reason))
        checks.append(
            check(
                "abstention_reason",
                "abstention",
                normalized_reason == case.expected_abstention_reason,
            )
        )
        no_effect = (
            getattr(result, "point_estimate", None) is None
            and getattr(result, "estimate", None) is None
            and getattr(result, "inference", None) is None
            and getattr(result, "test_result", None) is None
        )
        groups = getattr(result, "subgroup_results", ())
        no_effect &= all(
            g.status.value == "completed"
            or (g.estimate is None and g.confidence_interval is None and g.abstention_reason)
            for g in groups
        )
        checks.append(
            check(
                "abstention", "abstention", bool(no_effect and result.abstention_reason and codes)
            )
        )
        checks.append(
            check(
                "uncertainty",
                "uncertainty",
                True,
                status=CheckStatus.SKIPPED,
                message="No primary successful estimate; uncertainty is not fabricated.",
            )
        )
        return checks
    identification = getattr(result, "execution_request", None)
    if identification is not None:
        identification = identification.identification_result
        checks.append(
            check("identification", "identification", identification.status.value == "identified")
        )
        checks.append(
            check(
                "estimand",
                "estimand",
                identification.estimand is not None
                and identification.estimand.estimand_type.value == case.estimand,
            )
        )
    else:
        from packages.experiments.analysis.causal.service import CausalIdentificationService

        checked_identification = CausalIdentificationService().identify(result.analysis_request)
        checks.append(
            check(
                "identification",
                "identification",
                checked_identification.status.value == "identified",
            )
        )
        checks.append(
            check(
                "target_population",
                "estimand",
                result.target_population == result.estimand.target_population
                if result.estimand
                else False,
            )
        )
        checks.append(
            check(
                "estimand",
                "estimand",
                result.estimand is not None
                and result.estimand.estimand_type.value == case.estimand,
            )
        )
    checks.append(check("invalid_success", "status", not result.abstention_reason))
    if capability.dependency:
        provenance = result.adapter_provenance
        checks.append(
            check(
                "adapter_provenance",
                "provenance",
                provenance is not None
                and provenance.adapter_id == capability.adapter_id
                and provenance.adapter_version == capability.adapter_version,
            )
        )
    if capability.capability_id.startswith("dowhy"):
        evidence = result.identification
        checks.append(
            check(
                "graph",
                "identification",
                evidence.status.value == "completed"
                and len(evidence.graph_fingerprint) == 64
                and bool(evidence.interpretation)
                and "conditional" in evidence.interpretation.lower(),
            )
        )
        source = result.execution_request.identification_result
        from packages.experiments.analysis.causal.dowhy.graph import graph_fingerprint

        checks.append(
            check(
                "graph_provenance",
                "provenance",
                source.causal_graph is not None
                and graph_fingerprint(source.causal_graph) == evidence.graph_fingerprint,
            )
        )
        checks.append(
            check(
                "adjustment",
                "estimand",
                source.adjustment_set is not None
                and evidence.adjustment_set == source.adjustment_set.variable_ids,
            )
        )
        for refuter in result.refutations:
            checks.append(
                check(
                    "refuter",
                    "reference_accuracy",
                    refuter.method.value == capability.method
                    and refuter.seed == case.advanced.seed
                    and finite(refuter.delta)
                    and finite(refuter.original_estimate)
                    and finite(refuter.new_estimate)
                    and REPLAY_TOLERANCE.accepts(
                        refuter.delta, refuter.new_estimate - refuter.original_estimate
                    ),
                )
            )
        if capability.capability_id in {"dowhy_placebo", "dowhy_common_cause", "dowhy_subset"}:
            checks.append(check("refuter_present", "status", len(result.refutations) == 1))
        checks.append(
            check(
                "uncertainty",
                "uncertainty",
                True,
                status=CheckStatus.SKIPPED,
                message="NOT_APPLICABLE to identification/refutation; "
                "handoff intervals explicitly unsupported.",
            )
        )
        quality = evaluate_dowhy_quality(result)
    else:
        checks.append(check("method", "status", result.method == capability.method))
        plan = result.fold_plan
        fits = result.fold_fits
        checks.append(
            check(
                "cross_fitting",
                "data_leakage",
                plan is not None
                and plan.fold_count >= 2
                and len(fits) == plan.fold_count
                and all(f.train_count + f.score_count == len(plan.assignments) for f in fits),
            )
        )
        checks.append(
            check(
                "fold_seed",
                "provenance",
                plan is not None
                and plan.random_seed == case.advanced.seed
                and len(plan.fingerprint_sha256) == 64,
            )
        )
        checks.append(
            check(
                "nuisance",
                "provenance",
                bool(fits)
                and result.nuisance_diagnostics is not None
                and all(
                    f.outcome_fit.converged
                    and f.treatment_fit.converged
                    and f.outcome_adapter.configuration_fingerprint_sha256
                    and f.treatment_adapter.configuration_fingerprint_sha256
                    for f in fits
                ),
            )
        )
        if "hte" in capability.capability_id:
            checks.append(
                check(
                    "modifier",
                    "data_leakage",
                    result.modifier.measurement_timing.value == "pre_treatment",
                )
            )
            checks.append(
                check("group_assignment", "provenance", bool(result.assignment_fingerprint_sha256))
            )
            completed = [g for g in result.subgroup_results if g.status.value == "completed"]
            checks.append(
                check(
                    "uncertainty",
                    "uncertainty",
                    bool(completed)
                    and all(
                        valid_uncertainty(
                            g.estimate,
                            g.standard_error,
                            g.confidence_interval,
                            g.uncertainty_method,
                        )
                        for g in completed
                    ),
                )
            )
            checks.append(
                check(
                    "multiplicity",
                    "heterogeneity_safety",
                    result.multiplicity.correction_method.value == "holm"
                    and all(
                        g.adjusted_p_value is not None and g.adjusted_p_value >= g.p_value
                        for g in completed
                    ),
                )
            )
            quality = evaluate_hte_quality(result)
        else:
            inference = getattr(result, "inference", None) or getattr(result, "test_result", None)
            checks.append(
                check(
                    "uncertainty",
                    "uncertainty",
                    inference is not None
                    and valid_uncertainty(
                        result.point_estimate,
                        inference.standard_error,
                        inference.confidence_interval,
                        getattr(inference, "method", None)
                        or getattr(inference, "interval_method", None),
                    ),
                )
            )
            checks.append(
                check(
                    "overlap",
                    "data_leakage",
                    result.overlap is not None
                    and result.overlap.status.value not in {"severe", "unavailable"},
                )
            )
            quality = evaluate_advanced_quality(result) if capability.dependency else None
            if not capability.dependency:
                checks.append(
                    check(
                        "residuals",
                        "reference_accuracy",
                        result.outcome_residual_diagnostics is not None
                        and result.treatment_residual_diagnostics is not None,
                    )
                )
    if quality is not None:
        checks.append(check("capability_quality", "status", not quality.blocking_findings))
        if getattr(quality, "advisory_findings", ()):
            checks.append(
                check(
                    "limited_evidence",
                    "evidence",
                    True,
                    status=CheckStatus.ADVISORY,
                    message="Capability reports limited evidence or sensitivity; "
                    "causal validity is not established.",
                )
            )
    for expected in case.expected_values:
        actual = path_value(result, expected.path)
        tolerance = expected.tolerance
        passed = (
            finite(actual) and tolerance is not None and tolerance.accepts(actual, expected.value)
        )
        checks.append(
            StatisticalCheck(
                check_id=expected.path,
                rule_id="statistics.advanced.plausibility",
                dimension="reference_accuracy",
                status=CheckStatus.PASS if passed else CheckStatus.FAIL,
                expected=expected.value,
                actual=actual if finite(actual) else None,
                tolerance=tolerance.absolute if tolerance else None,
                relative_tolerance=tolerance.relative if tolerance else None,
                tolerance_rationale=tolerance.rationale if tolerance else None,
                tolerance_provenance=tolerance.provenance if tolerance else None,
                message="Independent known-effect fixture plausibility.",
            )
        )
    return checks
