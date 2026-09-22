"""Optional requests preserve adapter identity even when runtime is unavailable."""

from importlib.metadata import PackageNotFoundError

import pytest

from packages.experiments.analysis.orchestration.datasets import RequestDatasetResolver
from packages.experiments.analysis.orchestration.requests import normalize_analysis_input
from packages.experiments.analysis.orchestration.service import AnalysisService
from tests.orchestration_fixtures import method_payload
from tests.test_analysis_dispatch_causal import causal_case


@pytest.mark.parametrize("method", ["econml_dml", "econml_hte", "dowhy"])
def test_optional_missing_preserves_identity_without_substitution(monkeypatch, method):
    from packages.experiments.analysis.causal.dml.service import DoubleMachineLearningEstimator
    from packages.experiments.analysis.causal.econml import dependency
    from packages.experiments.analysis.causal.hte.service import HeterogeneousEffectEstimator

    def unavailable(name):
        raise PackageNotFoundError(name)

    def forbidden(*args, **kwargs):
        pytest.fail("optional method must never fall back to repository estimator")

    monkeypatch.setattr(dependency.metadata, "version", unavailable)
    monkeypatch.setattr(DoubleMachineLearningEstimator, "analyze", forbidden)
    monkeypatch.setattr(HeterogeneousEffectEstimator, "analyze", forbidden)
    base, dataset = causal_case("hte" if method == "econml_hte" else "dml")
    payload = method_payload(method)
    if method != "dowhy":
        payload["parameters"]["configuration"] = base.configuration.model_dump(mode="json")
    if method == "econml_hte":
        payload["parameters"]["configuration"]["analysis_version"] = "hte-dr-v1"
        payload["parameters"]["analysis_request"]["identification"]["design"]["method"] = (
            "doubly_robust_subgroup_effects"
        )
    request = normalize_analysis_input(payload, experiment_id="experiment-a")
    result = AnalysisService(resolver=RequestDatasetResolver((dataset,))).analyze(request)
    assert result.method == method
    assert result.status == "unavailable", result
    assert result.evidence is not None
    assert result.abstention.code == "OPTIONAL_DEPENDENCY_UNAVAILABLE"
