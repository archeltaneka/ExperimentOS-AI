"""Closed, restoring corruption scenarios at the actual API transport boundary."""

import hashlib
import json
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
from unittest.mock import patch

from .checks import check


@dataclass(frozen=True)
class InjectionSpec:
    injection_id: str
    method: str
    case_id: str
    path: str
    value: object
    stage: str = "response"
    expected_rule_ids: tuple[str, ...] = ("analysis.failures.result_integrity",)
    forbidden_calls: tuple[str, ...] = ()


# Explicit field mutations, not arbitrary import names or executable fixture input.
_MATRIX = (
    (
        "fixed-p-value",
        "randomized_fixed_horizon",
        "randomized",
        "evidence.test_result.p_value",
        0.987,
    ),
    (
        "fixed-ci",
        "randomized_fixed_horizon",
        "randomized",
        "evidence.test_result.confidence_interval",
        None,
    ),
    ("fixed-status", "randomized_fixed_horizon", "randomized", "status", "abstained"),
    ("cuped-timing", "cuped", "cuped-success", "evidence.covariate.timing", "post_treatment"),
    ("cuped-population", "cuped", "cuped-success", "evidence.retention.retained_total", 999),
    ("cuped-variance", "cuped", "cuped-success", "evidence.variance_reduction.fraction", 0.999),
    ("sequential-plan", "sequential", "sequential-success", "evidence.plan_fingerprint", "0" * 64),
    (
        "sequential-spend",
        "sequential",
        "sequential-success",
        "evidence.alpha_summary.cumulative_alpha_spent",
        0.99,
    ),
    ("sequential-boundary", "sequential", "sequential-success", "evidence.boundaries", []),
    ("bayesian-prior", "bayesian_ab", "bayesian-success", "evidence.treatment_prior", None),
    (
        "bayesian-interval",
        "bayesian_ab",
        "bayesian-success",
        "evidence.effect.credible_interval.kind",
        "confidence_interval",
    ),
    ("bayesian-rope", "bayesian_ab", "bayesian-success", "evidence.effect.rope_probability", 0.99),
    ("did-adoption", "did", "did", "evidence.context.time", None),
    ("did-assumptions", "did", "did", "evidence.assumptions", []),
    ("did-ci", "did", "did", "evidence.test_result.confidence_interval", None),
    (
        "propensity-convergence",
        "propensity_diagnostics",
        "propensity-success",
        "evidence.model_fit.converged",
        False,
    ),
    (
        "propensity-overlap",
        "propensity_diagnostics",
        "propensity-success",
        "evidence.overlap.status",
        "severe",
    ),
    (
        "propensity-transforms",
        "propensity_diagnostics",
        "propensity-success",
        "evidence.model_provenance.trimming_enabled",
        True,
    ),
    ("ipw-ate-target", "ipw_ate", "ipw-ate-success", "evidence.weights.estimand", "att"),
    ("ipw-ate-overlap", "ipw_ate", "ipw-ate-success", "evidence.overlap.status", "severe"),
    ("ipw-ate-clipping", "ipw_ate", "ipw-ate-success", "evidence.weights.clipping", None),
    ("ipw-att-target", "ipw_att", "ipw-att-success", "evidence.weights.estimand", "ate"),
    ("ipw-att-ci", "ipw_att", "ipw-att-success", "evidence.test_result.confidence_interval", None),
    ("dml-same-fold", "dml", "dml-success", "evidence.fold_plan.fold_count", 1),
    (
        "dml-degenerate",
        "dml",
        "dml-success",
        "evidence.treatment_residual_diagnostics.squared_norm",
        0,
    ),
    ("dml-fold-seed", "dml", "dml-success", "evidence.fold_plan.random_seed", 999),
    (
        "hte-modifier",
        "hte",
        "hte-success",
        "evidence.modifier.measurement_timing",
        "post_treatment",
    ),
    ("hte-sparse", "hte", "hte-success", "evidence.subgroup_results", []),
    ("hte-direct-evidence", "hte", "hte-success", "evidence.global_heterogeneity", None),
    ("workflow-method", "randomized_fixed_horizon", "randomized", "method", "ipw_att"),
    ("workflow-false-success", "unsupported_method", "unsupported", "status", "completed"),
)

INJECTION_SPECS = tuple(
    InjectionSpec(
        *row,
        expected_rule_ids=(
            "analysis.failures.execution_status"
            if row[3] == "status"
            else "analysis.failures.routing"
            if row[3] == "method"
            else "analysis.failures.result_integrity",
        ),
    )
    for row in _MATRIX
) + tuple(
    InjectionSpec(
        name,
        "randomized_fixed_horizon",
        "business",
        path,
        value,
        expected_rule_ids=("analysis.failures.business_provenance",),
    )
    for name, path, value in (
        ("business-population", "business_impact.inputs.population.value.central", 999999),
        ("business-conversion", "business_impact.net_monetary_impact.central", 999999),
        ("business-units", "business_impact.inputs", None),
        ("business-source", "business_impact.provenance", []),
    )
)

INJECTION_SPECS += (
    InjectionSpec(
        "normalized-estimator-error",
        "randomized_fixed_horizon",
        "randomized",
        "",
        None,
        stage="native",
        expected_rule_ids=("analysis.failures.execution_status",),
    ),
)


def injection_detected(expected, detected):
    return bool(expected) and set(expected) <= set(detected)


def _mutate(payload, spec):
    current = payload["analysis"]
    parts = spec.path.split(".")
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    key = int(parts[-1]) if isinstance(current, list) else parts[-1]
    if current[key] == spec.value:
        raise ValueError("injection must change its target")
    current[key] = spec.value
    # Do not let a stale digest alone detect every semantic mutation.
    evidence = payload["analysis"].get("evidence")
    payload["analysis"]["evidence_fingerprint"] = hashlib.sha256(
        json.dumps(evidence, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@contextmanager
def apply_injection(spec, case):
    from fastapi.testclient import TestClient

    if spec not in INJECTION_SPECS or case.case_id != spec.case_id:
        raise ValueError("unknown injection or incompatible case")
    if spec.stage == "native":
        from packages.experiments.analysis.orchestration import service
        from packages.experiments.analysis.orchestration.registry import AnalysisMethodRegistry

        registry = service.default_registry()

        def fail(*args, **kwargs):
            raise RuntimeError("PRIVATE_ESTIMATOR_ERROR_SENTINEL")

        changed = AnalysisMethodRegistry(
            tuple(
                replace(entry, handler=fail) if entry.method_id == spec.method else entry
                for entry in registry.entries
            )
        )
        with patch.object(service, "default_registry", return_value=changed):
            yield
        return
    original = TestClient.post

    def post(client, *args, **kwargs):
        response = original(client, *args, **kwargs)
        payload = response.json()
        _mutate(payload, spec)
        response._content = json.dumps(payload, allow_nan=False).encode()
        return response

    with patch.object(TestClient, "post", post):
        yield


def evaluate_injection(spec, case):
    from .harness import evaluate_workflow_case

    with apply_injection(spec, case):
        result = evaluate_workflow_case(case)
    detected = tuple(sorted(c.rule_id for c in result.checks.values() if c.status == "fail"))
    success = injection_detected(spec.expected_rule_ids, detected)
    if spec.stage == "native":
        success = (
            success
            and result.execution_status == "failed"
            and (result.checks["api_contract"].status == "pass")
        )
    # Expected corruption findings are evidence; only escaped corruption fails the gate.
    return result.model_copy(
        update={
            "case_id": "injection-" + spec.injection_id,
            "family": "injection",
            "execution_kind": "controlled",
            "detected_rule_ids": detected,
            "injection_detected": success,
            "evidence": None,
            "business_evidence": None,
            "checks": {"injection_detection": check(case, "injection_detection", success)},
        }
    )


@contextmanager
def audit_calls():
    from packages.experiments.analysis.causal.dml.service import DoubleMachineLearningEstimator
    from packages.experiments.analysis.causal.ipw.service import IPWTreatmentEffectEstimator
    from packages.experiments.analysis.impact.service import BusinessImpactService

    with ExitStack() as stack:
        spies = {}
        for name, cls in (
            ("dml", DoubleMachineLearningEstimator),
            ("ipw", IPWTreatmentEffectEstimator),
            ("business", BusinessImpactService),
        ):
            original = cls.analyze
            spies[name] = stack.enter_context(
                patch.object(
                    cls,
                    "analyze",
                    autospec=True,
                    wraps=original,
                    side_effect=original,
                )
            )
        yield spies
