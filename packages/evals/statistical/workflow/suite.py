"""Collect independent real workflow and controlled-defence results offline."""

from unittest.mock import patch

from ..telemetry import _RecordingProvider
from .checks import check
from .harness import evaluate_workflow_case
from .injections import INJECTION_SPECS, evaluate_injection
from .optional import PACKAGES


def evaluate_provider_isolation(case):
    provider = _RecordingProvider()
    with patch.object(provider, "_emit_root", side_effect=RuntimeError("PRIVATE_EXPORT_SENTINEL")):
        result = evaluate_workflow_case(case, observability_provider=provider)
    valid = result.execution_status == case.expected_status and result.provider_failure_count > 0
    valid = valid and result.checks["result_integrity"].status == "pass"
    return result.model_copy(
        update={
            "case_id": "provider-export-failure",
            "family": "provider",
            "execution_kind": "controlled",
            "checks": {"provider_isolation": check(case, "provider_isolation", valid)},
        }
    )


def evaluate_workflow_suite(cases, *, scope="complete", required_dependencies=()):
    by_id = {c.case_id: c for c in cases}
    results, errors = [], []
    executions = [(c.case_id, lambda c=c: evaluate_workflow_case(c)) for c in cases]
    if scope == "complete":
        executions.extend(
            ("injection-" + s.injection_id, lambda s=s: evaluate_injection(s, by_id[s.case_id]))
            for s in INJECTION_SPECS
        )
        executions.append(
            ("provider-export-failure", lambda: evaluate_provider_isolation(by_id["randomized"]))
        )
    for identity, execute in executions:
        try:
            result = execute()
            if (
                result.dependency_state == "unavailable"
                and PACKAGES.get(result.method) in required_dependencies
            ):
                result = result.model_copy(
                    update={
                        "checks": {
                            **result.checks,
                            "dependency": result.checks["dependency"].model_copy(
                                update={"status": "fail"}
                            ),
                        }
                    }
                )
            results.append(result)
        except Exception:
            # Independent cases still run; errors are infrastructure, never successful skips.
            errors.append(identity)
    return tuple(results), tuple(errors)
