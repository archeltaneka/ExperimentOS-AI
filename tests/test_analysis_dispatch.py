"""Dispatch tests catch guessing, duplicate registrations and silent substitution."""

from dataclasses import replace

import pytest

from packages.experiments.analysis.orchestration.datasets import RequestDatasetResolver
from packages.experiments.analysis.orchestration.registry import (
    AnalysisMethodRegistry,
    default_registry,
)
from packages.experiments.analysis.orchestration.requests import normalize_analysis_input
from packages.experiments.analysis.orchestration.service import AnalysisService


def test_unknown_method_does_not_resolve():
    registry = default_registry()
    assert registry.resolve("choose_largest_effect") is None
    assert "randomized_fixed_horizon" in registry.method_ids


def test_duplicate_method_registration_is_rejected():
    registration = default_registry().resolve("randomized_fixed_horizon")
    assert registration is not None
    with pytest.raises(ValueError, match="duplicate"):
        AnalysisMethodRegistry((registration, registration))


@pytest.mark.parametrize("method", ["choose_best", ["dml", "did"], None])
def test_refused_routing_never_calls_registered_handler(method):
    def forbidden(*args):
        pytest.fail("estimator was called for refused routing")

    original = default_registry().resolve("randomized_fixed_horizon")
    assert original is not None
    registry = AnalysisMethodRegistry((replace(original, handler=forbidden),))
    service = AnalysisService(resolver=RequestDatasetResolver(()), registry=registry)
    result = service.analyze(normalize_analysis_input({"method": method}, experiment_id="exp"))
    assert result.status == "abstained"
    assert result.evidence is None
    assert result.abstention is not None
