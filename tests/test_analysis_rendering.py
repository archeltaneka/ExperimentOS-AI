"""Presentation is a deterministic view, never statistical evidence."""

from packages.experiments.analysis.orchestration.datasets import RequestDatasetResolver
from packages.experiments.analysis.orchestration.rendering import render_analysis
from packages.experiments.analysis.orchestration.service import AnalysisService
from tests.test_analysis_service import fixed_case


def test_rendering_uses_native_estimate_interval_and_assumptions():
    request, dataset = fixed_case()
    result = AnalysisService(resolver=RequestDatasetResolver((dataset,))).analyze(request)
    text = render_analysis(result)
    assert "randomized_fixed_horizon" in text
    assert "10" in text
    assert "confidence" in text.lower()
    assert "assumptions" in text.lower()
    assert "does not authorize rollout" in text.lower()


def test_abstention_renders_reason_without_estimate():
    request, _ = fixed_case()
    result = AnalysisService(resolver=RequestDatasetResolver(())).analyze(request)
    text = render_analysis(result)
    assert "abstained" in text
    assert "analysis.dataset_missing" in text
    assert "Estimate:" not in text
