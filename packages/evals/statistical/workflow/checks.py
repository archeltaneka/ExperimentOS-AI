"""Method-aware invariants supplement exact native-to-workflow comparisons."""

import math

from .models import AnalysisCheck

UNCERTAINTY_PATHS = {
    "randomized_fixed_horizon": ("test_result.confidence_interval",),
    "cuped": ("adjusted_result.test_result.confidence_interval",),
    "bayesian_ab": ("effect.credible_interval",),
    "sequential": ("looks.0.look_level_analysis.test_result.confidence_interval",),
    "did": ("test_result.confidence_interval",),
    "ipw_ate": ("test_result.confidence_interval",),
    "ipw_att": ("test_result.confidence_interval",),
    "dml": ("test_result.confidence_interval",),
    "hte": ("subgroup_results.0.confidence_interval",),
    "econml_dml": ("test_result.confidence_interval",),
    "econml_hte": ("subgroup_results.0.confidence_interval",),
}


def path_value(payload, path):
    current = payload
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, (list, tuple)) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def check(case, code, passed, *, applicable=True, evidence=()):
    return AnalysisCheck(
        code=code,
        status="skipped" if not applicable else "pass" if passed else "fail",
        method=case.expected_method,
        execution_status=case.expected_status,
        applicable=applicable,
        rule_id="analysis.failures." + code,
        case_id=case.case_id,
        diagnostic_evidence=tuple(evidence),
    )


def finite_payload(value):
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(finite_payload(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return all(finite_payload(v) for v in value)
    return True


def valid_interval(value, *, credible=False):
    if not isinstance(value, dict):
        return False
    lower, upper = value.get("lower"), value.get("upper")
    level = value.get("credible_level" if credible else "confidence_level")
    return (
        all(type(v) in (float, int) and math.isfinite(v) for v in (lower, upper, level))
        and lower <= upper
        and 0 < level < 1
        and value.get("kind") == ("credible_interval" if credible else "confidence_interval")
    )


def evidence_checks(case, payload):
    from ..evaluator import check_expected_value

    successful = case.expected_status in {"completed", "inconclusive"}
    paths = UNCERTAINTY_PATHS.get(case.expected_method, ())
    required = successful and bool(paths)
    uncertainty = all(
        valid_interval(path_value(payload, p), credible=case.expected_method == "bayesian_ab")
        for p in paths
    )
    assumption_path = (
        "looks.0.assumptions" if case.expected_method == "sequential" else "assumptions"
    )
    numeric = [check_expected_value(payload or {}, v) for v in case.expectations.numerical]
    codes = {
        "uncertainty_preserved": check(
            case, "uncertainty_preserved", uncertainty, applicable=required
        ),
        "assumptions_preserved": check(
            case,
            "assumptions_preserved",
            bool(path_value(payload, assumption_path)),
            applicable=successful,
        ),
        "provenance_preserved": check(
            case,
            "provenance_preserved",
            bool(path_value(payload, "provenance")),
            applicable=successful,
        ),
        "reference_accuracy": check(
            case,
            "reference_accuracy",
            all(c.status == "pass" for c in numeric),
            applicable=bool(numeric),
            evidence=tuple(c.check_id for c in numeric if c.status != "pass"),
        ),
        "finite_outputs": check(case, "finite_outputs", finite_payload(payload)),
        "required_fields": check(
            case,
            "required_fields",
            all(path_value(payload, p) is not None for p in case.expectations.required_paths)
            and all(path_value(payload, p) is None for p in case.expectations.forbidden_paths),
        ),
    }
    return codes


def merge_checks(existing, additional):
    """A supplemental applicability skip cannot erase a failed preservation check."""
    merged = dict(existing)
    for code, value in additional.items():
        previous = merged.get(code)
        if previous is not None and (previous.status == "fail" or value.status == "skipped"):
            continue
        merged[code] = value
    return merged
