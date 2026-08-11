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

STATISTICAL_POLICY_VERSION = "2026-08-11"
LIMITATIONS = (
    "CUPED, sequential testing, Bayesian analysis, and Difference-in-Differences are not covered.",
    "Propensity scores, observational treatment effects, DML, and HTE are not covered.",
    "EconML, DoWhy, business-impact estimation, and product workflows are not covered.",
)
_MISSING = object()


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
        overall_status = (
            "fail"
            if counts[CheckStatus.FAIL]
            else ("advisory" if counts[CheckStatus.ADVISORY] else "pass")
        )
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
        first = run_statistical_fixture(case)
        repeated = run_statistical_fixture(case)
        reordered = run_statistical_fixture(case, reverse_rows=True)
        actual = first.model_dump(mode="json")
        repeated_payload = repeated.model_dump(mode="json")
        reordered_payload = reordered.model_dump(mode="json")
        actual_status = _actual_status(case, actual)
        diagnostics = tuple(_mapping(item) for item in _sequence(actual.get("diagnostics")))
        warnings = tuple(_mapping(item) for item in _sequence(actual.get("warnings")))
        repeated_diagnostics = tuple(
            _mapping(item) for item in _sequence(repeated_payload.get("diagnostics"))
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
            )
        )
        checks.extend(
            check_abstention(
                expected=case.expected_abstention,
                expected_reason=case.expected_abstention_reason,
                actual=actual,
            )
        )
        if case.capability in {
            StatisticalCapability.RANDOMIZED_BINARY,
            StatisticalCapability.RANDOMIZED_CONTINUOUS,
        }:
            checks.extend(check_uncertainty(actual))
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


def check_abstention(
    *,
    expected: bool,
    expected_reason: str | None,
    actual: Mapping[str, Any],
) -> tuple[StatisticalCheck, ...]:
    status = actual.get("status")
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
    reason = _mapping(actual.get("abstention_reason")).get("code")
    test_result = _mapping(actual.get("test_result"))
    return (
        _exact_check(
            check_id="abstention_state",
            rule_id="statistics.abstention.expected_state",
            dimension="abstention",
            expected="abstained",
            actual=status,
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
            actual=actual.get("point_effect"),
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
    )


def check_diagnostics(
    *,
    expected_codes: tuple[str, ...],
    expected_advisory_codes: tuple[str, ...],
    actual_diagnostics: Sequence[Mapping[str, Any]],
    actual_warnings: Sequence[Mapping[str, Any]],
    repeated_diagnostics: Sequence[Mapping[str, Any]] | None = None,
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
            actual=tuple(sorted(actual_codes)),
        ),
        _exact_check(
            check_id="advisory_codes",
            rule_id="statistics.diagnostics.advisory_codes",
            dimension="diagnostics",
            expected=tuple(sorted(expected_advisory_codes)),
            actual=tuple(sorted(warning_codes)),
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


def _actual_status(case: StatisticalReferenceCase, actual: Mapping[str, Any]) -> str:
    if case.capability is StatisticalCapability.DESCRIPTIVE_STATISTICS:
        return "completed"
    return str(actual.get("status", "invalid"))


def _actual_method(case: StatisticalReferenceCase, actual: Mapping[str, Any]) -> str | None:
    if case.capability is StatisticalCapability.ELIGIBILITY_VALIDATION:
        method = actual.get("requested_method")
        return str(method) if method is not None else None
    return _mapping(actual.get("test_result")).get("test_type")


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
    "check_diagnostics",
    "check_expected_value",
    "check_uncertainty",
]
