"""Public advanced executions feeding the existing Phase 4 case-result contract."""

from __future__ import annotations

from importlib import metadata
from time import perf_counter

from packages.experiments.analysis.causal.advanced.conformance import configuration_fingerprint

from ..models import CheckStatus, StatisticalCaseResult, StatisticalReferenceCase
from ..telemetry import _RecordingProvider
from .audit import audit_execution
from .checks import boundary_violations, check, equivalent
from .fixtures import prepare_case, run_case
from .models import AdvancedResultDetails
from .privacy import DIAGNOSTIC_CODES, privacy_violations
from .registry import REGISTRY
from .result_checks import result_checks


def dependency_state(package):
    if package is None:
        return "not_required", None
    try:
        return "installed", metadata.version(package)
    except metadata.PackageNotFoundError:
        return "unavailable", None
    except Exception:
        return "broken", None


def evaluate_advanced_case(
    case: StatisticalReferenceCase, required_dependencies: tuple[str, ...] = ()
) -> StatisticalCaseResult:
    started = perf_counter()
    details = case.advanced
    assert details is not None
    cap = REGISTRY[details.capability_id]
    state, version = dependency_state(cap.dependency)
    controlled = details.dependency_expectation == "controlled"
    checks = []
    actual_status = "error"
    semantic = "failed"
    codes = ()
    fingerprint = None
    try:
        request, table, config = prepare_case(case)
        fingerprint = configuration_fingerprint(request, cap.adapter_id, config)
        changed, _, changed_config = prepare_case(case, seed=details.seed + 1)
        checks.append(
            check(
                "configuration",
                "provenance",
                fingerprint != configuration_fingerprint(changed, cap.adapter_id, changed_config),
            )
        )
        first = run_case(case, _RecordingProvider())
        second = run_case(case, _RecordingProvider())
        safe = not boundary_violations(first.result) and not boundary_violations(second.result)
        if not safe:
            checks.append(check("interface", "interface_leakage", False))
        else:
            actual_status = first.result.status.value
            raw_codes = tuple(d.code for d in first.result.diagnostics)
            codes = tuple(sorted(code for code in raw_codes if code in DIAGNOSTIC_CODES))
            checks.append(
                check("diagnostic_projection", "telemetry_privacy", len(codes) == len(raw_codes))
            )
            semantic = {
                "completed": "successful",
                "invalid": "invalid",
                "unsupported": "invalid",
                "abstained": "abstained",
                "error": "failed",
            }[actual_status]
            unavailable = (
                state == "unavailable"
                and "OPTIONAL_DEPENDENCY_UNAVAILABLE" in codes
                and not controlled
            )
            # Only real dependency-requiring cases can become advisory absence.
            if unavailable and details.scenario in {
                "success",
                "homogeneous",
                "null",
                "inference_failure",
                "malformed",
                "nonfinite",
            }:
                semantic = "unavailable" if actual_status == "abstained" else "failed"
                absent_case = case.model_copy(
                    update={
                        "expected_status": "abstained",
                        "expected_abstention": True,
                        "expected_abstention_reason": "OPTIONAL_DEPENDENCY_UNAVAILABLE",
                        "expected_diagnostic_codes": ("OPTIONAL_DEPENDENCY_UNAVAILABLE",),
                    }
                )
                checks.extend(result_checks(absent_case, first.result))
                checks.append(
                    check(
                        "optional_dependency",
                        "dependency",
                        cap.dependency not in required_dependencies,
                        status=CheckStatus.FAIL
                        if cap.dependency in required_dependencies
                        else CheckStatus.ADVISORY,
                        message="Required optional dependency is absent."
                        if cap.dependency in required_dependencies
                        else "Optional package absent; repository capabilities still execute.",
                    )
                )
                checks.append(
                    check(
                        "absent_estimate",
                        "abstention",
                        first.result.abstention_reason is not None
                        and getattr(first.result, "point_estimate", None) is None
                        and getattr(first.result, "estimate", None) is None,
                    )
                )
            else:
                checks.extend(result_checks(case, first.result))
                checks.extend(audit_execution(first, request, table, cap))
                checks.extend(
                    item.model_copy(update={"check_id": item.check_id + "_replay"})
                    for item in audit_execution(second, request, table, cap)
                )
            checks.append(
                check(
                    "repeatability",
                    "determinism",
                    equivalent(
                        first.result.model_dump(mode="json"), second.result.model_dump(mode="json")
                    ),
                )
            )
            checks.append(
                check(
                    "configuration_recorded",
                    "provenance",
                    first.result.configuration_fingerprint_sha256 == fingerprint,
                )
            )
            private = privacy_violations((*first.records, *second.records))
            checks.append(
                check(
                    "privacy",
                    "telemetry_privacy",
                    not private and bool(first.records) and bool(second.records),
                )
            )
            if "INCOMPATIBLE_DEPENDENCY_RUNTIME" in codes and not controlled:
                state = "broken"
                checks.append(check("installed_runtime", "dependency", False))
        checks.append(check("failure_normalization", "exception_normalization", True))
    except Exception:
        checks.append(
            check(
                "failure_normalization",
                "exception_normalization",
                False,
                message="An exception crossed the public execution boundary; details suppressed.",
            )
        )
    blocking = tuple(c.rule_id for c in checks if c.status is CheckStatus.FAIL)
    advisory = tuple(c.rule_id for c in checks if c.status is CheckStatus.ADVISORY)
    verdict = (
        CheckStatus.FAIL if blocking else CheckStatus.ADVISORY if advisory else CheckStatus.PASS
    )
    return StatisticalCaseResult(
        case_id=case.case_id,
        capability=case.capability,
        category=case.category,
        design=case.analysis_design,
        estimand=case.estimand,
        method=case.method,
        target_population=case.target_population,
        reference_result={e.path: e.value for e in case.expected_values},
        tolerances={e.path: e.tolerance.absolute for e in case.expected_values if e.tolerance},
        expected_status=case.expected_status,
        actual_status=actual_status,
        evaluation_status=verdict,
        passed=not blocking,
        checks=tuple(checks),
        diagnostic_codes=codes,
        advisory_codes=(),
        blocking_findings=blocking,
        advisory_findings=advisory,
        skipped_checks=tuple(c.check_id for c in checks if c.status is CheckStatus.SKIPPED),
        skip_reasons=tuple(c.message for c in checks if c.status is CheckStatus.SKIPPED),
        duration_ms=(perf_counter() - started) * 1000,
        determinism_passed=any(
            c.check_id == "repeatability" and c.status is CheckStatus.PASS for c in checks
        ),
        advanced=AdvancedResultDetails(
            capability_id=cap.capability_id,
            adapter_id=cap.adapter_id,
            adapter_version=cap.adapter_version,
            implementation_version=cap.implementation_version,
            dependency_package=cap.dependency,
            dependency_version=version,
            dependency_state="controlled" if controlled else state,
            configuration_fingerprint=fingerprint,
            seed=details.seed,
            native_status=actual_status,
            semantic_status=semantic,
            uncertainty=cap.uncertainty,
            uncertainty_support=cap.uncertainty_support,
            execution_kind="controlled"
            if controlled or details.scenario in {"inference_failure", "malformed", "nonfinite"}
            else "real",
        ),
    )
