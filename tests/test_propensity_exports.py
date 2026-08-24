"""Stable causal package exports for propensity diagnostics."""

from __future__ import annotations

from packages.experiments.analysis.causal import (
    CappedWeightDiagnostics,
    DeterministicLogisticPropensityEstimator,
    PropensityConfig,
    PropensityExecutionRequest,
    PropensityResult,
    RetainedPopulationDiagnostics,
)


def test_propensity_entry_points_are_exported_from_causal_boundary() -> None:
    assert DeterministicLogisticPropensityEstimator.__name__
    assert PropensityConfig.__name__
    assert PropensityExecutionRequest.__name__
    assert PropensityResult.__name__
    assert RetainedPopulationDiagnostics.__name__
    assert CappedWeightDiagnostics.__name__
