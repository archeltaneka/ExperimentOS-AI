"""Stable statistical identity for a pre-registered sequential plan."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import SequentialAnalysisPlan


def sequential_plan_fingerprint(plan: SequentialAnalysisPlan) -> str:
    """Hash only fields that define the plan's statistical behavior."""
    payload = {
        "analysis_request": plan.analysis_request.model_dump(mode="json"),
        "boundary_method": plan.boundary_method.value,
        "method_version": plan.method_version,
        "plan_version": plan.plan_version,
        "planned_looks": [
            {
                "expected_cumulative_sample_counts": (
                    look.expected_cumulative_sample_counts.model_dump(mode="json")
                    if look.expected_cumulative_sample_counts is not None
                    else None
                ),
                "information_time": look.information_time,
                "look_index": look.look_index,
            }
            for look in plan.planned_looks
        ],
        "sidedness": plan.sidedness.value,
        "total_alpha": plan.total_alpha,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = ["sequential_plan_fingerprint"]
