"""Shared estimands and independently known effects, not forced implementation equality."""

from __future__ import annotations

import pytest

from packages.experiments.analysis.causal.dml import DoubleMachineLearningEstimator
from packages.experiments.analysis.causal.hte import HeterogeneousEffectEstimator
from tests.causal_identification_fixtures import provenance
from tests.dml_fixtures import dml_execution, dml_table
from tests.econml_fixtures import dr_execution, linear_rows, requires_econml
from tests.hte_fixtures import effect_rows, hte_execution, hte_table


@requires_econml
@pytest.mark.parametrize("effect", [2.0, 0.0])
def test_repository_and_econml_dml_recover_the_same_known_estimand(effect):
    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter

    execution = dml_execution(fold_count=4, seed=812)
    table = dml_table(linear_rows(effect))
    baseline = DoubleMachineLearningEstimator().analyze(execution, table, provenance=provenance())
    adapted = EconMLDMLAdapter(
        constant_effect_assumption=True,
    ).analyze(execution, table, provenance=provenance())
    assert baseline.status.value == adapted.status.value == "completed"
    assert baseline.estimand == adapted.execution_request.identification_result.estimand
    for estimate in (baseline.point_estimate, adapted.point_estimate):
        assert estimate == pytest.approx(effect, abs=0.25)
        if effect:
            assert estimate > 0
    assert baseline.test_result.standard_error > 0
    assert adapted.inference.standard_error > 0


@requires_econml
@pytest.mark.parametrize("effects", [(("ID", 1.0), ("SG", 3.0)), (("ID", 2.0), ("SG", 2.0))])
def test_repository_and_econml_hte_recover_declared_subgroup_effects(effects):
    from packages.experiments.analysis.causal.econml import EconMLHTEAdapter

    table = hte_table(effect_rows(effects))
    baseline = HeterogeneousEffectEstimator().analyze(
        hte_execution(fold_count=4), table, provenance=provenance()
    )
    adapted = EconMLHTEAdapter().analyze(dr_execution(fold_count=4), table, provenance=provenance())
    assert baseline.status.value == adapted.status.value == "completed"
    assert baseline.estimand == adapted.estimand
    for result in (baseline, adapted):
        assert [g.estimate for g in result.subgroup_results] == pytest.approx(
            [e for _, e in effects], abs=0.25
        )
        assert result.interactions[0].estimate == pytest.approx(
            effects[1][1] - effects[0][1], abs=0.25
        )
        assert all(g.standard_error > 0 for g in result.subgroup_results)
        assert result.global_heterogeneity.detected is (effects[0][1] != effects[1][1])
