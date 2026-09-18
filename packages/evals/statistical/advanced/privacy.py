"""Allowlisted advanced telemetry shapes with safe categorical violation evidence."""

from __future__ import annotations

import math
import re

from ..telemetry import telemetry_privacy_violations
from .registry import CAPABILITIES

# Closed inventory for this versioned conformance suite. New diagnostics require
# an explicit review; unfamiliar strings must never be echoed into artifacts.
DIAGNOSTIC_CODES = frozenset(
    {
        "ESTIMATION_FAILURE",
        "ESTIMATOR_FIT_FAILURE",
        "IDENTIFICATION_UNAVAILABLE",
        "INFERENCE_FAILURE",
        "INVALID_GRAPH",
        "MALFORMED_DOWHY_RESULT",
        "MODEL_CONSTRUCTION_FAILURE",
        "NONFINITE_ESTIMATE",
        "OPTIONAL_DEPENDENCY_UNAVAILABLE",
        "REFUTER_FAILURE",
        "UNSUPPORTED_INFERENCE",
        "INCOMPATIBLE_DEPENDENCY_RUNTIME",
        "assumption.unverified",
        "dml.crossfit.complete",
        "dml.degenerate_treatment_residual",
        "dml.identification.invalid",
        "dml.nuisance.fit_failure",
        "dml.overlap.severe",
        "hte.modifier.post_treatment",
        "hte.overlap.global_severe",
        "hte.subgroup.sparse_total",
    }
)

CATEGORIES = {
    "method": {c.method for c in CAPABILITIES},
    "adapter": {"econml", "dowhy"},
    "adapter_id": {c.adapter_id for c in CAPABILITIES},
    "adapter_version": {c.adapter_version for c in CAPABILITIES},
    "implementation_version": {c.implementation_version for c in CAPABILITIES},
    "status": {"completed", "invalid", "unsupported", "abstained", "error"},
    "dependency_state": {"not_required", "installed", "unavailable", "broken"},
    "estimand": {"ate", "cate", "unavailable", "missing"},
    "cross_fitting_status": {"complete", "not_complete"},
    "overlap_status": {"acceptable", "weak", "severe", "unavailable"},
    "outcome_nuisance_family": {"ridge_regression", "unavailable"},
    "treatment_nuisance_family": {"regularized_logistic_regression", "unavailable"},
    "modifier_type": {"binary_categorical", "finite_categorical", "continuous_binned"},
    "global_heterogeneity_status": {"available", "unavailable"},
    "multiplicity_method": {"holm"},
    "pre_specification_status": {"confirmatory_pre_specified", "exploratory", "data_mined"},
    "estimator": {"LinearDML", "LinearDRLearner"},
    "estimator_category": {"dml", "hte"},
    "inference_mode": {"statsmodels_hc1", "unsupported"},
    "operation": {"identification", "estimation", "refutation"},
    "identification_status": {
        "completed",
        "invalid",
        "unsupported",
        "unidentified",
        "error",
        "abstained",
    },
    "refuter": {c.method for c in CAPABILITIES if c.capability_id.startswith("dowhy")},
}


def approved_value(key, value):
    if key in CATEGORIES:
        return type(value) is str and value in CATEGORIES[key]
    if key.endswith("_count"):
        return type(value) is int and value >= 0
    if key in {"dml_completed", "hte_completed", "dependency_available"}:
        return type(value) is bool or (key == "dependency_available" and value is None)
    if key in {"configuration_fingerprint", "graph_fingerprint"}:
        return value is None or (type(value) is str and bool(re.fullmatch(r"[0-9a-f]{64}", value)))
    if key == "dependency_version":
        return value is None or (
            type(value) is str
            and bool(re.fullmatch(r"\d+(?:\.\d+)*(?:(?:a|b|rc|\.post|\.dev)\d+)?", value))
        )
    if key == "duration_ms":
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    if key == "diagnostic_codes":
        return type(value) in (tuple, list) and all(
            type(c) is str and c in DIAGNOSTIC_CODES for c in value
        )
    return False


ALLOWED = frozenset(
    {
        "row_count",
        "method",
        "fold_count",
        "adapter",
        "adapter_id",
        "adapter_version",
        "configuration_fingerprint",
        "dependency_state",
        "dependency_version",
        "status",
        "estimand",
        "cross_fitting_status",
        "overlap_status",
        "outcome_nuisance_family",
        "treatment_nuisance_family",
        "diagnostic_codes",
        "retained_count",
        "duration_ms",
        "dml_completed",
        "hte_completed",
        "modifier_type",
        "subgroup_count",
        "global_heterogeneity_status",
        "multiplicity_method",
        "pre_specification_status",
        "abstained_group_count",
        "overlap_failure_count",
        "estimator",
        "estimator_category",
        "inference_mode",
        "dependency_available",
        "operation",
        "identification_status",
        "graph_node_count",
        "graph_edge_count",
        "graph_fingerprint",
        "refuter",
        "implementation_version",
    }
)
SENSITIVE = (
    "private-graph-canary",
    "private-array-canary",
    "unit-secret",
    "prior_orders",
    "account_id",
    "unit-000",
    "ID-000",
    "SG-000",
)


def privacy_violations(records: tuple) -> tuple[str, ...]:
    violations = set()
    if telemetry_privacy_violations(records):
        violations.add("forbidden_payload")

    def visit(value):
        if type(value) is dict:
            for key, child in value.items():
                if key not in ALLOWED:
                    violations.add("unapproved_key")
                elif not approved_value(key, child):
                    violations.add("unapproved_value")
                visit(child)
        elif type(value) in (tuple, list):
            for child in value:
                visit(child)
        elif isinstance(value, str):
            if (
                any(secret in value for secret in SENSITIVE)
                or len(value) > 160
                or re.search(r"\[[\d., ]+\]", value)
            ):
                violations.add("sensitive_value")
        elif value is not None and type(value) not in (int, float, bool):
            violations.add("unowned_value")
        elif type(value) is float and not math.isfinite(value):
            violations.add("nonfinite_value")

    for record in records:
        for payload in (record.inputs, record.metadata, record.outputs):
            visit(payload)
        if record.error:
            violations.add("unexpected_error_payload")
        violations.update(privacy_violations(tuple(record.children)))
    return tuple(sorted(violations))
