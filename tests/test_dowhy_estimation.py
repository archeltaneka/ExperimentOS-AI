from __future__ import annotations

import importlib.util
from types import SimpleNamespace

import pytest

from packages.experiments.analysis import AnalysisTable
from packages.experiments.analysis.causal.dowhy.adapter import DoWhyAdapter
from packages.experiments.analysis.causal.dowhy.dependency import DoWhyBackend
from packages.experiments.analysis.causal.dowhy.models import DoWhyRefuterMethod
from tests.causal_identification_fixtures import provenance
from tests.dowhy_fixtures import execution, known_effect_table

requires_dowhy = pytest.mark.skipif(
    importlib.util.find_spec("dowhy") is None, reason="optional DoWhy environment required"
)


class _Identified:
    estimands = {"backdoor": {"estimand": object()}}
    default_backdoor_id = "backdoor"

    def get_adjustment_set(self, identifier: str):
        return ["prior_orders"]


class _Model:
    def __init__(self, **kwargs):
        self.data = kwargs["data"]

    def identify_effect(self, **kwargs):
        return _Identified()

    def estimate_effect(self, identified, **kwargs):
        assert kwargs["method_name"] == "backdoor.linear_regression"
        assert len(self.data) == 4
        return SimpleNamespace(value=2.05)


def _table() -> AnalysisTable:
    return AnalysisTable.from_records(
        (
            {"treated": 0, "outcome": 0.0, "prior_orders": -1.0},
            {"treated": 0, "outcome": 1.0, "prior_orders": 1.0},
            {"treated": 1, "outcome": 2.0, "prior_orders": -1.0},
            {"treated": 1, "outcome": 3.0, "prior_orders": 1.0},
        )
    )


def test_estimation_handoff_normalizes_finite_scalar(monkeypatch) -> None:
    from packages.experiments.analysis.causal.dowhy import adapter

    monkeypatch.setattr(
        adapter.dependency, "load_dowhy", lambda: DoWhyBackend(CausalModel=_Model, version="0.14")
    )
    result = DoWhyAdapter().analyze(
        execution(run_estimation=True), _table(), provenance=provenance()
    )
    assert result.status.value == "completed"
    assert result.estimate.point_estimate == pytest.approx(2.05)
    assert result.estimate.adjustment_set == ("prior_orders",)


def test_estimation_failure_suppresses_estimate(monkeypatch) -> None:
    from packages.experiments.analysis.causal.dowhy import adapter

    class Model(_Model):
        def estimate_effect(self, identified, **kwargs):
            raise RuntimeError("sensitive-row-value")

    monkeypatch.setattr(
        adapter.dependency, "load_dowhy", lambda: DoWhyBackend(CausalModel=Model, version="0.14")
    )
    result = DoWhyAdapter().analyze(
        execution(run_estimation=True), _table(), provenance=provenance()
    )
    assert result.status.value == "abstained"
    assert result.estimate is None
    assert result.abstention_reason.code == "ESTIMATION_FAILURE"
    assert "sensitive-row-value" not in result.model_dump_json()


@requires_dowhy
def test_real_dowhy_known_confounding_path_is_repeatable() -> None:
    configured = execution(run_estimation=True)
    configured = configured.model_copy(
        update={
            "configuration": configured.configuration.model_copy(
                update={"refuters": tuple(DoWhyRefuterMethod), "num_simulations": 8}
            )
        }
    )
    first = DoWhyAdapter().analyze(configured, known_effect_table(), provenance=provenance())
    second = DoWhyAdapter().analyze(configured, known_effect_table(), provenance=provenance())
    assert first.status.value == "completed"
    assert first.estimate.point_estimate == pytest.approx(2.0, abs=0.15)
    assert first.identification.adjustment_set == ("prior_orders",)
    assert first.estimate == second.estimate
    assert first.refutations == second.refutations
