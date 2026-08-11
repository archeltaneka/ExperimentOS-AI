"""Public package exports for CUPED contracts and service."""

from packages.experiments.analysis import (
    CupedAnalysisExecutionRequest,
    CupedAnalysisResult,
    CupedAnalysisService,
    CupedStatus,
)
from packages.experiments.analysis.randomized import VarianceReductionStatus


def test_cuped_public_exports_resolve_to_experimentos_types() -> None:
    assert CupedAnalysisExecutionRequest.__module__.startswith("packages.experiments.analysis")
    assert CupedAnalysisResult.__module__.startswith("packages.experiments.analysis")
    assert CupedAnalysisService.__module__.startswith("packages.experiments.analysis")
    assert CupedStatus.COMPLETED.value == "completed"
    assert VarianceReductionStatus.NEGATIVE_REDUCTION.value == "negative_reduction"
