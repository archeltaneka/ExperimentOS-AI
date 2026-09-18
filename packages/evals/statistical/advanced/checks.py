"""Owned boundaries, numerical equivalence, and compatibility-gated comparisons."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from ..models import CheckStatus, StatisticalCheck, StatisticalTolerance

REPLAY_TOLERANCE = StatisticalTolerance(
    absolute=1e-10,
    rationale="Same-runtime seeded numerical roundoff, not statistical error.",
    provenance="advanced-conformance-v1:numerical-repeatability",
)
COMPARISON_TOLERANCE = StatisticalTolerance(
    absolute=0.25,
    rationale="Independent small-fixture recovery bound; divergence is advisory.",
    provenance="issue-104:known-effect-reference",
)
COMPATIBILITY_FIELDS = (
    "estimand",
    "contrast",
    "population",
    "outcome",
    "covariates",
    "assumptions",
    "fixture",
    "subgroups",
)


def check(
    name: str,
    dimension: str,
    passed: bool,
    *,
    message: str | None = None,
    status: CheckStatus | None = None,
) -> StatisticalCheck:
    return StatisticalCheck(
        check_id=name,
        rule_id=f"statistics.advanced.{name}",
        dimension=dimension,
        status=status or (CheckStatus.PASS if passed else CheckStatus.FAIL),
        expected=True,
        actual=passed,
        message=message or f"Advanced causal {name.replace('_', ' ')} contract.",
    )


def boundary_violations(value: object) -> tuple[str, ...]:
    """Inspect objects before serialization; never expose object names or values."""
    violations: set[str] = set()
    active: set[int] = set()

    def visit(item: object) -> None:
        if item is None or type(item) in (str, int, bool, datetime):
            return
        if type(item) is float:
            if not math.isfinite(item):
                violations.add("nonfinite_scalar")
            return
        if isinstance(item, Enum) and type(item).__module__.startswith(
            "packages.experiments.analysis"
        ):
            visit(item.value)
            return
        if id(item) in active:
            violations.add("cyclic_object")
            return
        active.add(id(item))
        if isinstance(item, BaseModel) and type(item).__module__.startswith(
            "packages.experiments.analysis"
        ):
            # Include extra attributes: model_copy can bypass Pydantic validation.
            for child in vars(item).values():
                visit(child)
            for child in (item.model_extra or {}).values():
                visit(child)
            for child in (item.__pydantic_private__ or {}).values():
                visit(child)
        elif type(item) is dict:
            for key, child in item.items():
                if type(key) is not str:
                    violations.add("non_string_key")
                visit(child)
        elif type(item) in (tuple, list):
            for child in item:
                visit(child)
        else:
            violations.add("unowned_object")
        active.remove(id(item))

    visit(value)
    return tuple(sorted(violations))


def equivalent(left: object, right: object) -> bool:
    """Exact structural/categorical agreement and explicitly bounded float roundoff."""
    if type(left) is not type(right):
        return False
    if isinstance(left, float):
        return (
            math.isfinite(left) and math.isfinite(right) and REPLAY_TOLERANCE.accepts(left, right)
        )
    if isinstance(left, Mapping):
        return left.keys() == right.keys() and all(equivalent(v, right[k]) for k, v in left.items())
    if isinstance(left, (tuple, list)):
        return len(left) == len(right) and all(
            equivalent(a, b) for a, b in zip(left, right, strict=True)
        )
    return bool(left == right)


def compare_effects(
    left: Mapping[str, object],
    right: Mapping[str, object],
    left_estimate: float,
    right_estimate: float,
) -> StatisticalCheck:
    mismatches = tuple(
        k
        for k in COMPATIBILITY_FIELDS
        if k not in left or k not in right or left[k] is None or left[k] != right[k]
    )
    if mismatches:
        return check(
            "comparison",
            "comparison",
            True,
            status=CheckStatus.SKIPPED,
            message="NOT_APPLICABLE: incompatible " + ", ".join(mismatches),
        )
    finite = math.isfinite(left_estimate) and math.isfinite(right_estimate)
    delta = abs(left_estimate - right_estimate) if finite else None
    return StatisticalCheck(
        check_id="comparison",
        rule_id="statistics.advanced.comparison",
        dimension="comparison",
        status=CheckStatus.PASS
        if finite and COMPARISON_TOLERANCE.accepts(right_estimate, left_estimate)
        else CheckStatus.ADVISORY,
        expected=left_estimate if finite else None,
        actual=right_estimate if finite else None,
        delta=delta,
        tolerance=COMPARISON_TOLERANCE.absolute,
        tolerance_rationale=COMPARISON_TOLERANCE.rationale,
        tolerance_provenance=COMPARISON_TOLERANCE.provenance,
        message="Compatible aggregate comparison; agreement does not establish causal validity.",
    )
