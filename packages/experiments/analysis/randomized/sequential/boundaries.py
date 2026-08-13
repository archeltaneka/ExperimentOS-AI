"""Finite-safe O'Brien-Fleming-shaped weighted Bonferroni boundaries."""

from __future__ import annotations

import math

import scipy.stats as _stats  # type: ignore[import-untyped]

from ..numerics import normal_critical_value
from .models import SequentialAnalysisPlan, SequentialBoundary


def generate_sequential_boundaries(
    plan: SequentialAnalysisPlan,
) -> tuple[SequentialBoundary, ...]:
    """Generate the complete deterministic boundary schedule from a registered plan."""
    fixed_horizon_boundary = normal_critical_value(plan.total_alpha)
    previous_cumulative = 0.0
    generated: list[SequentialBoundary] = []
    last_index = len(plan.planned_looks)

    for look in plan.planned_looks:
        if look.look_index == last_index:
            cumulative = plan.total_alpha
        else:
            shaped_boundary = fixed_horizon_boundary / math.sqrt(look.information_time)
            cumulative = float(2.0 * _stats.norm.sf(shaped_boundary))
            if not math.isfinite(cumulative) or cumulative < 0.0:
                raise ValueError("cumulative alpha spending must be finite and non-negative")
            cumulative = min(cumulative, plan.total_alpha)

        nominal = max(0.0, cumulative - previous_cumulative)
        if nominal == 0.0:
            critical = fixed_horizon_boundary / math.sqrt(look.information_time)
        else:
            critical = float(_stats.norm.isf(nominal / 2.0))
        if not math.isfinite(critical) or critical <= 0.0:
            raise ValueError("sequential critical boundary must be positive and finite")

        remaining = max(0.0, plan.total_alpha - cumulative)
        generated.append(
            SequentialBoundary(
                look_index=look.look_index,
                information_time=look.information_time,
                critical_boundary=critical,
                nominal_alpha=nominal,
                cumulative_alpha_spent=cumulative,
                remaining_alpha=remaining,
                method=plan.boundary_method,
                method_version=plan.method_version,
                total_alpha=plan.total_alpha,
            )
        )
        previous_cumulative = cumulative
    return tuple(generated)


__all__ = ["generate_sequential_boundaries"]
