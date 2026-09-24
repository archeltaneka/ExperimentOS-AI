"""Safe recursive privacy findings and actual owned span-tree linkage."""

import math
import re
from collections.abc import Mapping, Sequence

from packages.observability.base import BufferedSpanRecord

from ..telemetry import _normalize_key

PRIVATE_KEYS = frozenset(
    {
        "rows",
        "raw_rows",
        "outcomes",
        "assignments",
        "raw_covariates",
        "raw_outcomes",
        "raw_panel_observations",
        "residuals",
        "nuisance_predictions",
        "posterior_draws",
        "unit_ids",
        "unit_identifiers",
        "unit_level_weights",
        "raw_score_arrays",
        "cate_array",
        "causal_graph",
        "credentials",
        "api_key",
        "authorization",
        "password",
        "ask_payload",
        "analysis_datasets",
        "raw_subgroup_rows",
        "treatment_assignments",
    }
)
PRIVATE_VALUES = re.compile(
    r"(?i)(?:bearer\s+\S+|(?:api[_-]?key|password|secret)\s*[:=]\s*\S+|"
    r"\b(?:unit|account|customer|subject|participant)[-_]\d+\b|"
    r"[\w.+-]+@[\w.-]+\.[a-z]{2,}|PRIVATE_[A-Z_]*SENTINEL)"
)


def privacy_violations(payload, *, sentinels=()):
    violations = set()

    def inspect(value, key=""):
        if isinstance(value, BufferedSpanRecord):
            inspect((value.inputs, value.outputs, value.metadata, value.error, value.tags))
            for child in value.children:
                inspect(child)
        elif isinstance(value, Mapping):
            for key, child in value.items():
                if _normalize_key(str(key)) in PRIVATE_KEYS and not (
                    key == "rows" and type(child) is int and child >= 0
                ):
                    violations.add("private_field")
                inspect(child, key)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            declared_configuration = (
                key in {"score_quantiles", "weight_quantiles"}
                and all(type(v) in (int, float) and 0 <= v <= 1 for v in value)
                and list(value) == sorted(set(value))
            ) or (key == "classes" and list(value) == [0, 1])
            if value and all(type(v) in (int, float) for v in value) and not declared_configuration:
                violations.add("raw_numeric_array")
            for child in value:
                inspect(child)
        elif isinstance(value, str):
            if PRIVATE_VALUES.search(value) or any(s and s in value for s in sentinels):
                violations.add("private_value")
        elif isinstance(value, float) and not math.isfinite(value):
            violations.add("nonfinite_value")
        elif value is not None and not isinstance(value, (int, float, bool)):
            violations.add("foreign_object")

    inspect(payload)
    return tuple(sorted(violations))


def check_trace_linkage(records, *, method, business_requested, estimator_required=True):
    violations = set()
    if len(records) != 1 or records[0].name != "ask_request":
        return ("request_root_missing",)
    root = records[0]
    if not root.trace_id or root.parent is not None:
        violations.add("invalid_request_root")
    seen = set()
    names = {}

    def inspect(record, parent):
        if id(record) in seen:
            violations.add("duplicate_span")
            return
        seen.add(id(record))
        names.setdefault(record.name, []).append(record)
        if record.parent is not parent or record.trace_id != root.trace_id:
            violations.add("broken_span_link")
        if record.ended_at is None:
            violations.add("unfinished_span")
        for child in record.children:
            inspect(child, record)

    inspect(root, None)
    edges = {
        "workflow": "ask_request",
        "analysis": "workflow",
        "validation": "analysis",
        "response_serialization": "ask_request",
    }
    if estimator_required:
        edges["estimator"] = "analysis"
    if business_requested:
        edges["analysis.business_impact"] = "workflow"
    for child, parent in edges.items():
        matching = names.get(child, [])
        if len(matching) != 1 or matching[0].parent is None or matching[0].parent.name != parent:
            violations.add("required_boundary_unlinked")
    if estimator_required and not any(
        r.metadata.get("method") == method for r in names.get("estimator", [])
    ):
        violations.add("method_uncorrelated")
    return tuple(sorted(violations))


def trace_summary(records):
    summary = []

    def walk(record, parent=None):
        span_id = str(len(summary))
        summary.append(
            {
                "span_id": span_id,
                "parent_span_id": parent,
                "name": record.name,
                "trace_id": record.trace_id,
                "status": record.status,
            }
        )
        for child in record.children:
            walk(child, span_id)

    for root in records:
        walk(root)
    return tuple(summary)
