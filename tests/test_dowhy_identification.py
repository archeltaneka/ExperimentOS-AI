from __future__ import annotations

from types import SimpleNamespace

from packages.experiments.analysis.causal.dowhy.adapter import DoWhyAdapter
from packages.experiments.analysis.causal.dowhy.dependency import DoWhyBackend
from tests.causal_identification_fixtures import provenance
from tests.dowhy_fixtures import execution


class _Identified:
    estimands = {"backdoor": {"estimand": object()}}
    default_backdoor_id = "backdoor"

    def get_adjustment_set(self, identifier: str):
        assert identifier == "backdoor"
        return ["prior_orders"]


class _Model:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def identify_effect(self, **kwargs):
        return _Identified()


def test_valid_backdoor_normalizes_owned_identification(monkeypatch) -> None:
    from packages.experiments.analysis.causal.dowhy import adapter

    monkeypatch.setattr(
        adapter.dependency,
        "load_dowhy",
        lambda: DoWhyBackend(CausalModel=_Model, version="0.14"),
    )
    result = DoWhyAdapter().analyze(execution(), provenance=provenance())
    assert result.status.value == "completed"
    assert result.identification.adjustment_set == ("prior_orders",)
    assert result.identification.method == "default_backdoor"
    assert len(result.identification.graph_fingerprint) == 64
    assert "conditional" in result.identification.interpretation.lower()


def test_no_identification_abstains_without_adjustment(monkeypatch) -> None:
    from packages.experiments.analysis.causal.dowhy import adapter

    unidentified = SimpleNamespace(
        estimands={"backdoor": None, "frontdoor": None, "iv": None},
        default_backdoor_id=None,
        backdoor_variables={},
    )

    class Model(_Model):
        def identify_effect(self, **kwargs):
            return unidentified

    monkeypatch.setattr(
        adapter.dependency,
        "load_dowhy",
        lambda: DoWhyBackend(CausalModel=Model, version="0.14"),
    )
    result = DoWhyAdapter().analyze(execution(latent=True), provenance=provenance())
    assert result.status.value == "abstained"
    assert result.identification.adjustment_set == ()
    assert result.estimate is None
    assert result.abstention_reason.code == "IDENTIFICATION_UNAVAILABLE"


def test_model_construction_failure_is_normalized(monkeypatch) -> None:
    from packages.experiments.analysis.causal.dowhy import adapter

    class BrokenModel:
        def __init__(self, **kwargs):
            raise RuntimeError("sensitive backend detail")

    monkeypatch.setattr(
        adapter.dependency,
        "load_dowhy",
        lambda: DoWhyBackend(CausalModel=BrokenModel, version="0.14"),
    )
    result = DoWhyAdapter().analyze(execution(), provenance=provenance())
    assert result.status.value == "error"
    assert result.abstention_reason.code == "MODEL_CONSTRUCTION_FAILURE"
    assert "sensitive" not in result.abstention_reason.message


def test_malformed_identification_result_is_normalized(monkeypatch) -> None:
    from packages.experiments.analysis.causal.dowhy import adapter

    class Model(_Model):
        def identify_effect(self, **kwargs):
            return SimpleNamespace()

    monkeypatch.setattr(
        adapter.dependency,
        "load_dowhy",
        lambda: DoWhyBackend(CausalModel=Model, version="0.14"),
    )
    result = DoWhyAdapter().analyze(execution(), provenance=provenance())
    assert result.status.value == "error"
    assert result.abstention_reason.code == "MALFORMED_DOWHY_RESULT"
