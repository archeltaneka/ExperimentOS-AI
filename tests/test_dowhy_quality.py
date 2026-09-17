from __future__ import annotations

from packages.experiments.analysis.causal.dowhy.adapter import DoWhyAdapter
from packages.experiments.analysis.causal.dowhy.dependency import DoWhyBackend
from packages.experiments.analysis.causal.dowhy.quality import evaluate_dowhy_quality
from tests.causal_identification_fixtures import provenance
from tests.dowhy_fixtures import execution
from tests.test_dowhy_identification import _Model


def test_completed_owned_identification_has_no_blocking_quality_findings(monkeypatch) -> None:
    from packages.experiments.analysis.causal.dowhy import adapter

    monkeypatch.setattr(
        adapter.dependency, "load_dowhy", lambda: DoWhyBackend(CausalModel=_Model, version="0.14")
    )
    result = DoWhyAdapter().analyze(execution(), provenance=provenance())
    assessment = evaluate_dowhy_quality(result)
    assert assessment.blocking_findings == ()
