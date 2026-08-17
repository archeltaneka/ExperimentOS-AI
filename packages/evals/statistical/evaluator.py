"""Cross-cutting deterministic checks for the implemented Phase 4 surface."""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from .fixtures import run_statistical_fixture
from .models import (
    CheckStatus,
    StatisticalBaselineReport,
    StatisticalCapability,
    StatisticalCapabilityResult,
    StatisticalCaseCategory,
    StatisticalCaseResult,
    StatisticalCheck,
    StatisticalExpectedValue,
    StatisticalReferenceCase,
    StatisticalReferenceDataset,
)
from .telemetry import evaluate_fixture_telemetry_privacy

STATISTICAL_POLICY_VERSION = "2026-08-11"
LIMITATIONS = (
    "Difference-in-Differences, propensity scores, and observational ATE/ATT are not covered.",
    "Inverse-probability weighting, DML, HTE, EconML, and DoWhy are not covered.",
    "Business-impact conversion, auto-stop actions, rollout automation, and dashboards are "
    "not covered.",
    "Bayesian v1 uses deterministic quadrature and has no seeded sampling path to evaluate.",
)
_MISSING = object()
_FIXTURE_CACHE: dict[tuple[str, bool, str], Any] = {}
_TELEMETRY_PRIVACY_CACHE: dict[str, tuple[bool, tuple[str, ...]]] = {}


class StatisticalBaselineEvaluator:
    """Evaluate typed references without external services or generated expectations."""

    def evaluate(self, dataset: StatisticalReferenceDataset) -> StatisticalBaselineReport:
        case_results = tuple(self._evaluate_case(case) for case in dataset.cases)
        counts = Counter(result.evaluation_status for result in case_results)
        capability_results = tuple(
            self._capability_result(capability, case_results)
            for capability in StatisticalCapability
            if any(result.capability is capability for result in case_results)
        )
        overall_status = "fail" if counts[CheckStatus.FAIL] else "pass"
        return StatisticalBaselineReport(
            baseline_id=dataset.baseline_id,
            baseline_version=dataset.version,
            fixture_provenance=dataset.fixture_provenance,
            policy_version=STATISTICAL_POLICY_VERSION,
            offline_provider_statement=(
                "Offline deterministic providers only; no network, live LLM, database, external "
                "judge, or hosted telemetry is required."
            ),
            dataset_size=len(case_results),
            cases_passed=counts[CheckStatus.PASS],
            cases_failed=counts[CheckStatus.FAIL],
            cases_advisory=counts[CheckStatus.ADVISORY],
            cases_invalid=sum(
                result.category is StatisticalCaseCategory.INVALID_INPUT for result in case_results
            ),
            cases_abstained=sum(result.actual_status == "abstained" for result in case_results),
            cases_skipped=counts[CheckStatus.SKIPPED],
            overall_status=overall_status,
            capability_results=capability_results,
            case_results=case_results,
            limitations=LIMITATIONS,
        )

    def _evaluate_case(self, case: StatisticalReferenceCase) -> StatisticalCaseResult:
        first = _cached_fixture(case, reverse_rows=False, execution_slot="first")
        repeated = _cached_fixture(case, reverse_rows=False, execution_slot="repeat")
        reordered = _cached_fixture(case, reverse_rows=True, execution_slot="reordered")
        actual = first.model_dump(mode="json")
        repeated_payload = repeated.model_dump(mode="json")
        reordered_payload = reordered.model_dump(mode="json")
        actual_status = _actual_status(case, actual)
        diagnostics = _actual_diagnostics(case, actual)
        warnings = _actual_warnings(case, actual)
        repeated_diagnostics = tuple(
            _mapping(item) for item in _actual_diagnostics(case, repeated_payload)
        )
        checks = [
            _exact_check(
                check_id="status",
                rule_id="statistics.status.expected",
                dimension="status",
                expected=case.expected_status,
                actual=actual_status,
            )
        ]
        if case.expected_method is not None:
            checks.append(
                _exact_check(
                    check_id="method",
                    rule_id="statistics.method.expected",
                    dimension="reference_accuracy",
                    expected=case.expected_method,
                    actual=_actual_method(case, actual),
                )
            )
        checks.extend(check_expected_value(actual, item) for item in case.expected_values)
        checks.extend(
            check_diagnostics(
                expected_codes=case.expected_diagnostic_codes,
                expected_advisory_codes=case.expected_advisory_codes,
                actual_diagnostics=diagnostics,
                actual_warnings=warnings,
                repeated_diagnostics=repeated_diagnostics,
                allow_additional_codes=case.capability
                in {
                    StatisticalCapability.CUPED,
                    StatisticalCapability.SEQUENTIAL,
                    StatisticalCapability.BAYESIAN_BINARY,
                    StatisticalCapability.BAYESIAN_CONTINUOUS,
                },
            )
        )
        checks.extend(
            check_abstention(
                expected=case.expected_abstention,
                expected_reason=case.expected_abstention_reason,
                actual=actual,
                capability=case.capability,
            )
        )
        if case.capability in {
            StatisticalCapability.RANDOMIZED_BINARY,
            StatisticalCapability.RANDOMIZED_CONTINUOUS,
        }:
            checks.extend(check_uncertainty(actual))
        elif case.capability in {
            StatisticalCapability.CUPED,
            StatisticalCapability.SEQUENTIAL,
            StatisticalCapability.BAYESIAN_BINARY,
            StatisticalCapability.BAYESIAN_CONTINUOUS,
        }:
            is_successful = actual_status in {
                "completed",
                "no_improvement",
                "degraded_precision",
                "continue",
                "efficacy",
                "no_rejection",
            }
            checks.extend(
                check_assumptions(
                    required_codes=(
                        tuple(
                            sorted(
                                set(case.expected_assumption_codes)
                                | set(_required_assumption_codes(case.capability))
                            )
                        )
                        if is_successful
                        else ()
                    ),
                    actual_assumptions=_actual_assumptions(case, actual),
                )
            )
            checks.extend(check_method_uncertainty(case.capability, actual))
            if case.capability is StatisticalCapability.SEQUENTIAL:
                checks.extend(check_sequential_plan_integrity(actual))
            if case.capability in {
                StatisticalCapability.BAYESIAN_BINARY,
                StatisticalCapability.BAYESIAN_CONTINUOUS,
            }:
                checks.extend(check_bayesian_semantics(actual))
            if case.category is not StatisticalCaseCategory.SKIPPED:
                privacy_passed, privacy_violations = _cached_telemetry_privacy(case)
                checks.append(
                    _exact_check(
                        check_id="telemetry_privacy",
                        rule_id="statistics.telemetry.privacy",
                        dimension="telemetry_privacy",
                        expected=True,
                        actual=privacy_passed,
                    ).model_copy(
                        update={
                            "message": (
                                "Telemetry contains only approved aggregate metadata."
                                if privacy_passed
                                else f"Forbidden telemetry keys: {', '.join(privacy_violations)}"
                            )
                        }
                    )
                )
            checks.extend(_method_advisories(case, actual, warnings))
        canonical = _canonical_json(actual)
        determinism_checks = (
            _exact_check(
                check_id="repeatability",
                rule_id="statistics.determinism.repeated_result",
                dimension="determinism",
                expected=canonical,
                actual=_canonical_json(repeated_payload),
            ),
            _exact_check(
                check_id="row_order_invariance",
                rule_id="statistics.determinism.row_order",
                dimension="determinism",
                expected=canonical,
                actual=_canonical_json(reordered_payload),
            ),
        )
        checks.extend(determinism_checks)
        check_tuple = tuple(checks)
        blocking = tuple(check.rule_id for check in check_tuple if check.status is CheckStatus.FAIL)
        advisories = tuple(
            check.rule_id for check in check_tuple if check.status is CheckStatus.ADVISORY
        )
        skipped = tuple(
            check.check_id for check in check_tuple if check.status is CheckStatus.SKIPPED
        )
        evaluation_status = (
            CheckStatus.FAIL
            if blocking
            else CheckStatus.SKIPPED
            if case.category is StatisticalCaseCategory.SKIPPED
            else CheckStatus.ADVISORY
            if advisories
            else CheckStatus.SKIPPED
            if check_tuple and len(skipped) == len(check_tuple)
            else CheckStatus.PASS
        )
        return StatisticalCaseResult(
            case_id=case.case_id,
            capability=case.capability,
            category=case.category,
            expected_status=case.expected_status,
            actual_status=actual_status,
            evaluation_status=evaluation_status,
            passed=evaluation_status in {CheckStatus.PASS, CheckStatus.ADVISORY},
            checks=check_tuple,
            diagnostic_codes=tuple(str(item.get("code")) for item in diagnostics),
            advisory_codes=tuple(str(item.get("code")) for item in warnings),
            blocking_findings=blocking,
            advisory_findings=advisories,
            skipped_checks=skipped,
            skip_reasons=tuple(
                check.message for check in check_tuple if check.status is CheckStatus.SKIPPED
            ),
            duration_ms=0.0,
            determinism_passed=all(
                check.status is CheckStatus.PASS for check in determinism_checks
            ),
        )

    @staticmethod
    def _capability_result(
        capability: StatisticalCapability,
        results: tuple[StatisticalCaseResult, ...],
    ) -> StatisticalCapabilityResult:
        selected = tuple(result for result in results if result.capability is capability)
        return StatisticalCapabilityResult(
            capability=capability,
            cases=len(selected),
            passed=sum(result.evaluation_status is CheckStatus.PASS for result in selected),
            failed=sum(result.evaluation_status is CheckStatus.FAIL for result in selected),
            advisory=sum(result.evaluation_status is CheckStatus.ADVISORY for result in selected),
        )


def check_expected_value(
    actual: Mapping[str, Any],
    expected: StatisticalExpectedValue,
) -> StatisticalCheck:
    observed = _path_value(actual, expected.path)
    if observed is _MISSING:
        return _failed_check(
            expected.path,
            "statistics.reference.missing_field",
            "reference_accuracy",
            expected.value,
            None,
            "Expected result field was not present.",
        )
    if expected.tolerance is None:
        return _exact_check(
            check_id=expected.path,
            rule_id="statistics.reference.exact",
            dimension="reference_accuracy",
            expected=expected.value,
            actual=observed,
        )
    if (
        not isinstance(observed, (int, float))
        or isinstance(observed, bool)
        or not isinstance(expected.value, (int, float))
        or isinstance(expected.value, bool)
    ):
        return _failed_check(
            expected.path,
            "statistics.reference.numeric_type",
            "reference_accuracy",
            expected.value,
            observed,
            "Observed reference value was not numeric.",
        )
    observed_float = float(observed)
    if not math.isfinite(observed_float):
        return _failed_check(
            expected.path,
            "statistics.reference.nonfinite",
            "reference_accuracy",
            expected.value,
            observed,
            "Observed numerical value was not finite.",
        )
    delta = abs(observed_float - float(expected.value))
    passed = delta <= expected.tolerance.absolute
    return StatisticalCheck(
        check_id=expected.path,
        rule_id="statistics.reference.numeric_tolerance",
        dimension="reference_accuracy",
        status=CheckStatus.PASS if passed else CheckStatus.FAIL,
        expected=expected.value,
        actual=observed,
        delta=delta,
        tolerance=expected.tolerance.absolute,
        tolerance_rationale=expected.tolerance.rationale,
        tolerance_provenance=expected.tolerance.provenance,
        message=(
            "Numerical value is within the declared tolerance."
            if passed
            else "Numerical value exceeds the declared tolerance."
        ),
    )


def _cached_fixture(
    case: StatisticalReferenceCase,
    *,
    reverse_rows: bool,
    execution_slot: str,
) -> Any:
    key = (case.fixture_id, reverse_rows, execution_slot)
    if key not in _FIXTURE_CACHE:
        _FIXTURE_CACHE[key] = run_statistical_fixture(case, reverse_rows=reverse_rows)
    return _FIXTURE_CACHE[key]


def _cached_telemetry_privacy(
    case: StatisticalReferenceCase,
) -> tuple[bool, tuple[str, ...]]:
    if case.fixture_id not in _TELEMETRY_PRIVACY_CACHE:
        _TELEMETRY_PRIVACY_CACHE[case.fixture_id] = evaluate_fixture_telemetry_privacy(case)
    return _TELEMETRY_PRIVACY_CACHE[case.fixture_id]


def check_abstention(
    *,
    expected: bool,
    expected_reason: str | None,
    actual: Mapping[str, Any],
    capability: StatisticalCapability | None = None,
) -> tuple[StatisticalCheck, ...]:
    status = _actual_status_for_capability(capability, actual)
    if not expected:
        return (
            _exact_check(
                check_id="abstention_state",
                rule_id="statistics.abstention.expected_state",
                dimension="abstention",
                expected=False,
                actual=status == "abstained",
            ),
        )
    reason, point_effect, test_result, posterior_probability = _abstention_payload(
        capability, actual
    )
    expected_state: object = "abstained" if capability is None else True
    actual_state: object = status if capability is None else status != "completed"
    return (
        _exact_check(
            check_id="abstention_state",
            rule_id="statistics.abstention.expected_state",
            dimension="abstention",
            expected=expected_state,
            actual=actual_state,
        ),
        _exact_check(
            check_id="abstention_reason",
            rule_id="statistics.abstention.reason",
            dimension="abstention",
            expected=expected_reason,
            actual=reason,
        ),
        _exact_check(
            check_id="abstention_point_estimate",
            rule_id="statistics.abstention.no_point_estimate",
            dimension="abstention",
            expected=None,
            actual=point_effect,
        ),
        _exact_check(
            check_id="abstention_p_value",
            rule_id="statistics.abstention.no_p_value",
            dimension="abstention",
            expected=None,
            actual=test_result.get("p_value"),
        ),
        _exact_check(
            check_id="abstention_interval",
            rule_id="statistics.abstention.no_interval",
            dimension="abstention",
            expected=None,
            actual=test_result.get("confidence_interval"),
        ),
        _exact_check(
            check_id="abstention_posterior_probability",
            rule_id="statistics.abstention.no_posterior_probability",
            dimension="abstention",
            expected=None,
            actual=posterior_probability,
        ),
    )


def check_diagnostics(
    *,
    expected_codes: tuple[str, ...],
    expected_advisory_codes: tuple[str, ...],
    actual_diagnostics: Sequence[Mapping[str, Any]],
    actual_warnings: Sequence[Mapping[str, Any]],
    repeated_diagnostics: Sequence[Mapping[str, Any]] | None = None,
    allow_additional_codes: bool = False,
) -> tuple[StatisticalCheck, ...]:
    actual_codes = tuple(str(item.get("code")) for item in actual_diagnostics)
    warning_codes = tuple(str(item.get("code")) for item in actual_warnings)
    repeated_codes = tuple(
        str(item.get("code")) for item in (repeated_diagnostics or actual_diagnostics)
    )
    contradictory = any(
        first.get("code") == second.get("code") and first.get("status") != second.get("status")
        for index, first in enumerate(actual_diagnostics)
        for second in actual_diagnostics[index + 1 :]
    )
    return (
        _exact_check(
            check_id="diagnostic_codes",
            rule_id="statistics.diagnostics.required_codes",
            dimension="diagnostics",
            expected=tuple(sorted(expected_codes)),
            actual=(
                tuple(sorted(expected_codes))
                if allow_additional_codes and set(expected_codes) <= set(actual_codes)
                else tuple(sorted(actual_codes))
            ),
        ),
        _exact_check(
            check_id="advisory_codes",
            rule_id="statistics.diagnostics.advisory_codes",
            dimension="diagnostics",
            expected=tuple(sorted(expected_advisory_codes)),
            actual=(
                tuple(sorted(expected_advisory_codes))
                if allow_additional_codes and set(expected_advisory_codes) <= set(warning_codes)
                else tuple(sorted(warning_codes))
            ),
        ),
        _exact_check(
            check_id="diagnostic_ordering",
            rule_id="statistics.diagnostics.ordering",
            dimension="diagnostics",
            expected=actual_codes,
            actual=repeated_codes,
        ),
        _exact_check(
            check_id="diagnostic_contradiction",
            rule_id="statistics.diagnostics.no_contradiction",
            dimension="diagnostics",
            expected=False,
            actual=contradictory,
        ),
    )


def check_uncertainty(actual: Mapping[str, Any]) -> tuple[StatisticalCheck, ...]:
    if actual.get("status") != "completed":
        return ()
    test_result = _mapping(actual.get("test_result"))
    interval = _mapping(test_result.get("confidence_interval"))
    configuration = _mapping(actual.get("configuration"))
    lower = interval.get("lower")
    upper = interval.get("upper")
    finite_ordered = (
        isinstance(lower, (int, float))
        and isinstance(upper, (int, float))
        and math.isfinite(float(lower))
        and math.isfinite(float(upper))
        and float(lower) <= float(upper)
    )
    required = {
        "point_estimate_present": actual.get("point_effect") is not None,
        "standard_error_present": test_result.get("standard_error") is not None,
        "interval_present": bool(interval),
        "interval_bounds_finite_ordered": finite_ordered,
        "confidence_level_valid": (
            interval.get("confidence_level") == configuration.get("confidence_level")
            and isinstance(interval.get("confidence_level"), (int, float))
            and 0 < float(interval["confidence_level"]) < 1
        ),
        "p_value_present": test_result.get("p_value") is not None,
        "method_present": bool(test_result.get("test_type")),
        "estimand_present": bool(_mapping(actual.get("estimand")).get("kind")),
        "treatment_count_present": bool(_mapping(actual.get("treatment_summary")).get("n")),
        "control_count_present": bool(_mapping(actual.get("control_summary")).get("n")),
    }
    return tuple(
        _exact_check(
            check_id=name,
            rule_id=f"statistics.uncertainty.{name}",
            dimension="uncertainty",
            expected=True,
            actual=value,
        )
        for name, value in required.items()
    )


def check_assumptions(
    *,
    required_codes: tuple[str, ...],
    actual_assumptions: Sequence[Mapping[str, Any]],
) -> tuple[StatisticalCheck, ...]:
    """Block successful inference when method-relevant assumptions are absent."""
    actual_codes = tuple(str(item.get("code")) for item in actual_assumptions)
    present = set(required_codes) <= set(actual_codes)
    return (
        (
            _exact_check(
                check_id="required_assumption_codes",
                rule_id="statistics.assumptions.required_codes",
                dimension="assumptions",
                expected=True,
                actual=present,
            ),
        )
        if required_codes
        else ()
    )


def check_method_uncertainty(
    capability: StatisticalCapability,
    actual: Mapping[str, Any],
) -> tuple[StatisticalCheck, ...]:
    """Apply only the uncertainty semantics belonging to the selected method."""
    status = _actual_status_for_capability(capability, actual)
    successful = {
        StatisticalCapability.CUPED: {"completed", "no_improvement", "degraded_precision"},
        StatisticalCapability.SEQUENTIAL: {"continue", "efficacy", "no_rejection"},
        StatisticalCapability.BAYESIAN_BINARY: {"completed"},
        StatisticalCapability.BAYESIAN_CONTINUOUS: {"completed"},
    }.get(capability, set())
    if status not in successful:
        return ()
    if capability is StatisticalCapability.CUPED:
        adjusted = _mapping(actual.get("adjusted_result"))
        test_result = _mapping(adjusted.get("test_result"))
        interval = _mapping(test_result.get("confidence_interval"))
        required = {
            "adjusted_point_estimate": adjusted.get("point_effect") is not None,
            "adjusted_standard_error": test_result.get("standard_error") is not None,
            "adjusted_interval": _finite_interval(interval),
            "confidence_level": interval.get("confidence_level") is not None,
            "comparable_unadjusted": actual.get("comparable_unadjusted_result") is not None,
            "variance_reduction": bool(_mapping(actual.get("variance_reduction"))),
        }
    elif capability is StatisticalCapability.SEQUENTIAL:
        look = _mapping(actual.get("current_look"))
        analysis = _mapping(look.get("look_level_analysis"))
        test_result = _mapping(analysis.get("test_result"))
        required = {
            "effect_estimate": analysis.get("point_effect") is not None,
            "look_uncertainty": _finite_interval(_mapping(test_result.get("confidence_interval"))),
            "sequential_boundary": look.get("sequential_boundary") is not None,
            "cumulative_alpha": look.get("cumulative_alpha_spent") is not None,
            "look_metadata": look.get("look_index") is not None,
        }
    else:
        effect = _mapping(actual.get("effect"))
        interval = _mapping(effect.get("credible_interval"))
        required = {
            "posterior_effect_summary": effect.get("posterior_mean") is not None,
            "posterior_standard_deviation": effect.get("posterior_standard_deviation") is not None,
            "credible_interval": _finite_interval(interval),
            "credible_level": interval.get("credible_level") is not None,
            "treatment_prior": bool(_mapping(actual.get("treatment_prior"))),
            "control_prior": bool(_mapping(actual.get("control_prior"))),
            "treatment_posterior": bool(_mapping(actual.get("treatment_posterior"))),
            "control_posterior": bool(_mapping(actual.get("control_posterior"))),
            "posterior_method": bool(effect.get("computation_method")),
        }
    return tuple(
        _exact_check(
            check_id=name,
            rule_id=f"statistics.uncertainty.{name}",
            dimension="uncertainty",
            expected=True,
            actual=value,
        )
        for name, value in required.items()
    )


def check_sequential_plan_integrity(actual: Mapping[str, Any]) -> tuple[StatisticalCheck, ...]:
    status = str(actual.get("current_status", "invalid"))
    expected = "invalid" if status == "invalid" else "valid"
    return (
        _exact_check(
            check_id="sequential_plan_integrity",
            rule_id="statistics.sequential.plan_integrity",
            dimension="plan_integrity",
            expected=expected,
            actual=actual.get("plan_integrity"),
        ),
    )


def check_bayesian_semantics(actual: Mapping[str, Any]) -> tuple[StatisticalCheck, ...]:
    if actual.get("status") != "completed":
        return ()
    effect = _mapping(actual.get("effect"))
    rope_probability = effect.get("rope_probability")
    rope_consistent = rope_probability is None or bool(_mapping(rope_probability).get("rope"))
    required = {
        "likelihood_recorded": bool(_mapping(actual.get("likelihood"))),
        "prior_provenance_recorded": all(
            bool(_sequence(_mapping(actual.get(name)).get("provenance")))
            for name in ("treatment_prior", "control_prior")
        ),
        "no_p_value": "p_value" not in effect,
        "no_confidence_interval": "confidence_interval" not in effect,
        "rope_declaration_consistent": rope_consistent,
    }
    return tuple(
        _exact_check(
            check_id=name,
            rule_id=f"statistics.bayesian.{name}",
            dimension="bayesian_semantics",
            expected=True,
            actual=value,
        )
        for name, value in required.items()
    )


def _actual_status(case: StatisticalReferenceCase, actual: Mapping[str, Any]) -> str:
    if case.capability is StatisticalCapability.DESCRIPTIVE_STATISTICS:
        return "completed"
    return _actual_status_for_capability(case.capability, actual)


def _actual_status_for_capability(
    capability: StatisticalCapability | None,
    actual: Mapping[str, Any],
) -> str:
    if capability is StatisticalCapability.SEQUENTIAL:
        status = str(actual.get("current_status", "invalid"))
        return "abstained" if status == "abstain" else status
    return str(actual.get("status", "invalid"))


def _actual_method(case: StatisticalReferenceCase, actual: Mapping[str, Any]) -> str | None:
    if case.capability is StatisticalCapability.ELIGIBILITY_VALIDATION:
        method = actual.get("requested_method")
        return str(method) if method is not None else None
    if case.capability is StatisticalCapability.CUPED:
        return str(actual.get("adjustment_method"))
    if case.capability is StatisticalCapability.SEQUENTIAL:
        method = _mapping(actual.get("plan")).get("boundary_method")
        return str(method) if method is not None else None
    if case.capability in {
        StatisticalCapability.BAYESIAN_BINARY,
        StatisticalCapability.BAYESIAN_CONTINUOUS,
    }:
        method = _mapping(actual.get("configuration")).get("effect_method")
        return str(method) if method is not None else None
    return _mapping(actual.get("test_result")).get("test_type")


def _actual_diagnostics(
    case: StatisticalReferenceCase,
    actual: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    key = "deviations" if case.capability is StatisticalCapability.SEQUENTIAL else "diagnostics"
    diagnostics = tuple(_mapping(item) for item in _sequence(actual.get(key)))
    reason = _mapping(actual.get("abstention_reason")).get("code")
    aliases = {
        "continuous_arm_inadequate": "inadequate_continuous_evidence",
        "covariate.missingness_exceeds_threshold": "excessive_covariate_missingness",
        "covariate.post_treatment_leakage": "post_treatment_covariate",
    }
    alias = aliases.get(str(reason))
    return diagnostics + (({"code": alias},) if alias is not None else ())


def _actual_warnings(
    case: StatisticalReferenceCase,
    actual: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    if case.capability is StatisticalCapability.SEQUENTIAL:
        look = _mapping(actual.get("current_look"))
        analysis = _mapping(look.get("look_level_analysis"))
        return tuple(_mapping(item) for item in _sequence(analysis.get("warnings")))
    warnings = tuple(_mapping(item) for item in _sequence(actual.get("warnings")))
    if case.capability is not StatisticalCapability.CUPED:
        return warnings
    codes = {str(item.get("code")) for item in warnings}
    aliases: list[Mapping[str, Any]] = []
    status = str(actual.get("status"))
    if status == "degraded_precision":
        aliases.append({"code": "cuped.negative_variance_reduction"})
    if status == "no_improvement":
        aliases.append({"code": "cuped.weak_outcome_covariate_correlation"})
    retention = _mapping(actual.get("retention"))
    if isinstance(retention.get("removed_total"), int) and retention["removed_total"] > 0:
        aliases.append({"code": "cuped.sample_rows_removed"})
    if "eligibility.allocation.deviation_warning" in codes:
        aliases.append({"code": "eligibility.sample.arm_imbalance"})
    return warnings + tuple(aliases)


def _actual_assumptions(
    case: StatisticalReferenceCase,
    actual: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    if case.capability is StatisticalCapability.SEQUENTIAL:
        return tuple(
            _mapping(item)
            for item in _sequence(_mapping(actual.get("current_look")).get("assumptions"))
        )
    return tuple(_mapping(item) for item in _sequence(actual.get("assumptions")))


def _required_assumption_codes(capability: StatisticalCapability) -> tuple[str, ...]:
    if capability is StatisticalCapability.CUPED:
        return (
            "compatible_analysis_randomization_units",
            "covariate_pre_treatment",
            "covariate_unaffected_by_treatment",
            "estimand_preserved",
            "random_assignment",
        )
    if capability is StatisticalCapability.SEQUENTIAL:
        return (
            "sequential.alpha_spending_controlled",
            "sequential.cumulative_eligible_data",
            "sequential.fixed_primary_outcome",
            "sequential.fixed_treatment_control",
            "sequential.information_time_prespecified",
            "sequential.plan_immutable",
            "sequential.plan_preregistered",
            "sequential.valid_look_schedule",
        )
    if capability in {
        StatisticalCapability.BAYESIAN_BINARY,
        StatisticalCapability.BAYESIAN_CONTINUOUS,
    }:
        return (
            "bayesian.computation_method",
            "bayesian.credible_interval_method",
            "bayesian.likelihood_family",
            "bayesian.outcome_model",
            "bayesian.prior_family",
            "bayesian.prior_parameters",
        )
    return ()


def _abstention_payload(
    capability: StatisticalCapability | None,
    actual: Mapping[str, Any],
) -> tuple[object, object, Mapping[str, Any], object]:
    aliases = {
        "continuous_arm_inadequate": "inadequate_continuous_evidence",
        "covariate.missingness_exceeds_threshold": "excessive_covariate_missingness",
        "covariate.post_treatment_leakage": "post_treatment_covariate",
        "eligibility.sample.total_insufficient": "insufficient_estimator_support",
    }
    if capability is StatisticalCapability.CUPED:
        reason = _mapping(actual.get("abstention_reason")).get("code")
        adjusted = _mapping(actual.get("adjusted_result"))
        return (
            aliases.get(str(reason), reason),
            adjusted.get("point_effect"),
            _mapping(adjusted.get("test_result")),
            None,
        )
    if capability is StatisticalCapability.SEQUENTIAL:
        analysis = _mapping(_mapping(actual.get("current_look")).get("look_level_analysis"))
        reason = _mapping(analysis.get("abstention_reason")).get("code")
        return (
            aliases.get(str(reason), reason),
            analysis.get("point_effect"),
            _mapping(analysis.get("test_result")),
            None,
        )
    if capability in {
        StatisticalCapability.BAYESIAN_BINARY,
        StatisticalCapability.BAYESIAN_CONTINUOUS,
    }:
        reason = _mapping(actual.get("abstention_reason")).get("code")
        effect = _mapping(actual.get("effect"))
        return (
            aliases.get(str(reason), reason),
            effect.get("posterior_mean"),
            {},
            effect.get("probability_of_superiority"),
        )
    return (
        _mapping(actual.get("abstention_reason")).get("code"),
        actual.get("point_effect"),
        _mapping(actual.get("test_result")),
        None,
    )


def _finite_interval(interval: Mapping[str, Any]) -> bool:
    lower = interval.get("lower")
    upper = interval.get("upper")
    return (
        isinstance(lower, (int, float))
        and not isinstance(lower, bool)
        and isinstance(upper, (int, float))
        and not isinstance(upper, bool)
        and math.isfinite(float(lower))
        and math.isfinite(float(upper))
        and float(lower) <= float(upper)
    )


def _method_advisories(
    case: StatisticalReferenceCase,
    actual: Mapping[str, Any],
    warnings: Sequence[Mapping[str, Any]],
) -> tuple[StatisticalCheck, ...]:
    if case.category in {StatisticalCaseCategory.INVALID_INPUT, StatisticalCaseCategory.ABSTENTION}:
        return ()
    advisory_codes = tuple(dict.fromkeys(str(item.get("code")) for item in warnings))
    return tuple(
        StatisticalCheck(
            check_id=f"advisory.{code}",
            rule_id=f"statistics.performance.{code}",
            dimension="statistical_performance",
            status=CheckStatus.ADVISORY,
            expected="review",
            actual="observed",
            message="Statistical performance finding is advisory and does not invalidate output.",
        )
        for code in advisory_codes
    )


def _path_value(payload: Any, path: str) -> Any:
    current = payload
    for part in path.split("."):
        if isinstance(current, Mapping):
            if part not in current:
                return _MISSING
            current = current[part]
        elif isinstance(current, Sequence) and not isinstance(current, (str, bytes)):
            try:
                current = current[int(part)]
            except (IndexError, ValueError):
                return _MISSING
        else:
            return _MISSING
    return current


def _exact_check(
    *,
    check_id: str,
    rule_id: str,
    dimension: str,
    expected: Any,
    actual: Any,
) -> StatisticalCheck:
    passed = actual == expected and type(actual) is type(expected)
    return StatisticalCheck(
        check_id=check_id,
        rule_id=rule_id,
        dimension=dimension,
        status=CheckStatus.PASS if passed else CheckStatus.FAIL,
        expected=expected,
        actual=actual,
        message="Exact value matched." if passed else "Exact value did not match.",
    )


def _failed_check(
    check_id: str,
    rule_id: str,
    dimension: str,
    expected: Any,
    actual: Any,
    message: str,
) -> StatisticalCheck:
    return StatisticalCheck(
        check_id=check_id,
        rule_id=rule_id,
        dimension=dimension,
        status=CheckStatus.FAIL,
        expected=expected,
        actual=actual,
        message=message,
    )


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[object]:
    return value if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else ()


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


__all__ = [
    "StatisticalBaselineEvaluator",
    "check_abstention",
    "check_assumptions",
    "check_diagnostics",
    "check_expected_value",
    "check_method_uncertainty",
    "check_uncertainty",
]
