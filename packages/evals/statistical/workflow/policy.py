"""Strict structured workflow ingestion; central PolicyEvaluator owns verdicts."""

from .cases import REQUIRED_CASE_IDS
from .checks import evidence_checks
from .injections import INJECTION_SPECS, injection_detected
from .models import WorkflowCaseResult
from .optional import PACKAGES

EXTRA_CHECKS = (
    "reference_accuracy",
    "finite_outputs",
    "required_fields",
    "state_preserved",
    "api_contract",
    "trace_linkage",
    "telemetry_privacy",
    "artifact_privacy",
    "determinism",
)
SPECIAL_CHECKS = ("dependency", "injection_detection", "compatibility", "provider_isolation")


def workflow_quality_status(statuses):
    if "fail" in statuses:
        return "fail"
    if "warning" in statuses:
        return "warning"
    if not statuses or all(status == "skipped" for status in statuses):
        return "skipped"
    return "pass"


def required_ids(scope):
    if scope == "optional-adapters":
        return frozenset(c for c in REQUIRED_CASE_IDS if c.startswith(tuple(PACKAGES))) | {
            "optional_unavailable"
        }
    if scope != "complete":
        raise ValueError("invalid workflow scope")
    return (
        REQUIRED_CASE_IDS
        | {"injection-" + s.injection_id for s in INJECTION_SPECS}
        | {"provider-export-failure"}
    )


def workflow_metrics(payload, *, scope):
    from packages.evals.agent_analysis_cases import (
        ANALYSIS_CHECK_CODES,
        analysis_check_applicability,
        load_analysis_workflow_cases,
    )

    try:
        results = tuple(WorkflowCaseResult.model_validate(r) for r in payload)
    except (ValueError, TypeError):
        raise ValueError("invalid workflow result schema") from None
    inventory = required_ids(scope)
    cases = {c.case_id: c for c in load_analysis_workflow_cases()}
    injections = {"injection-" + s.injection_id: s for s in INJECTION_SPECS}
    failures = dict.fromkeys((*ANALYSIS_CHECK_CODES, *EXTRA_CHECKS, *SPECIAL_CHECKS), 0)
    seen = set()
    inventory_failures = 0
    for result in results:
        identity = result.case_id
        if identity in seen or identity not in inventory:
            inventory_failures += 1
        seen.add(identity)
        if identity == "provider-export-failure":
            expected = {"provider_isolation": True}
            if result.provider_failure_count < 1:
                failures["provider_isolation"] += 1
        elif identity in injections:
            spec = injections[identity]
            expected = {"injection_detection": True}
            if not result.injection_detected or not injection_detected(
                spec.expected_rule_ids, result.detected_rule_ids
            ):
                failures["injection_detection"] += 1
        elif identity in cases:
            case = cases[identity]
            expected = {**analysis_check_applicability(case), **dict.fromkeys(EXTRA_CHECKS, True)}
            expected["reference_accuracy"] = (
                bool(case.expectations.numerical) and result.dependency_state != "unavailable"
            )
            if case.expected_method in PACKAGES:
                expected["dependency"] = True
                if result.dependency_state == "broken":
                    failures["dependency"] += 1
            if result.method != case.expected_method:
                failures["routing"] += 1
            expected_status = (
                "unavailable"
                if result.dependency_state == "unavailable"
                and case.expected_method in PACKAGES
                and not case.optional_scenario
                else case.expected_status
            )
            if result.execution_status != expected_status:
                failures["execution_status"] += 1
            forbidden = {
                "dml-post-treatment": ("dml",),
                "ipw-ate-no-overlap": ("ipw",),
                "missing-business-provenance": ("business",),
                "insufficient": ("business",),
            }.get(identity, ())
            if any(result.call_counts.get(name) != 0 for name in forbidden):
                failures["downstream_gating"] += 1
            if (result.case_version, result.family, result.design, result.estimand) != (
                case.case_version,
                case.family,
                case.design,
                case.estimand,
            ):
                inventory_failures += 1
            # Recompute numeric/shape checks; supplied check totals are not an oracle.
            if result.dependency_state != "unavailable":
                for code, value in evidence_checks(case, result.evidence).items():
                    if value.status == "fail":
                        failures[code] += 1
        else:
            continue
        for code, applicable in expected.items():
            value = result.checks.get(code)
            if (
                value is None
                or value.code != code
                or value.status == "fail"
                or value.applicable != applicable
                or ((value.status == "skipped") == applicable)
                or value.rule_id != "analysis.failures." + code
            ):
                failures[code] += 1
        if result.checks.keys() - failures.keys():
            raise ValueError("unknown workflow check")
    metrics = {"analysis.failures." + code: count for code, count in failures.items()}
    metrics.update(
        {
            "analysis.scope": scope,
            "analysis.case_count": len(results),
            "analysis.failures.case_inventory": inventory_failures + len(inventory - seen),
        }
    )
    return metrics
