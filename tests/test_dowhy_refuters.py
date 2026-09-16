from __future__ import annotations

from types import SimpleNamespace

from packages.experiments.analysis.causal.dowhy.adapter import DoWhyAdapter
from packages.experiments.analysis.causal.dowhy.dependency import DoWhyBackend
from packages.experiments.analysis.causal.dowhy.models import DoWhyRefuterMethod
from tests.causal_identification_fixtures import provenance
from tests.dowhy_fixtures import execution
from tests.test_dowhy_estimation import _Model, _table


class _RefutingModel(_Model):
    def refute_estimate(self, identified, estimate, *, method_name, **kwargs):
        values = {
            "placebo_treatment_refuter": 0.01,
            "random_common_cause": 2.04,
            "data_subset_refuter": 2.03,
        }
        assert kwargs["random_seed"] == 105
        assert kwargs["n_jobs"] == 1
        return SimpleNamespace(
            estimated_effect=2.05,
            new_effect=values[method_name],
            refutation_result={"p_value": 0.5, "is_statistically_significant": False},
        )


def test_all_supported_refuters_record_seed_configuration_and_limits(monkeypatch) -> None:
    from packages.experiments.analysis.causal.dowhy import adapter

    monkeypatch.setattr(
        adapter.dependency,
        "load_dowhy",
        lambda: DoWhyBackend(CausalModel=_RefutingModel, version="0.14"),
    )
    configured = execution(run_estimation=True)
    configured = configured.model_copy(
        update={
            "configuration": configured.configuration.model_copy(
                update={"refuters": tuple(DoWhyRefuterMethod)}
            )
        }
    )
    result = DoWhyAdapter().analyze(configured, _table(), provenance=provenance())
    assert [item.method for item in result.refutations] == list(DoWhyRefuterMethod)
    assert all(item.seed == 105 and item.num_simulations == 20 for item in result.refutations)
    assert all("proof" not in item.interpretation.lower() for item in result.refutations)
    assert result.refutations[0].original_estimate == 2.05
