"""Reproducibility-critical HTE provenance checks."""

from __future__ import annotations

from packages.experiments.analysis.causal.hte import HTEStatus
from packages.experiments.analysis.causal.hte.service import HeterogeneousEffectEstimator
from tests.causal_identification_fixtures import provenance
from tests.hte_fixtures import effect_rows, hte_execution, hte_table


def test_completed_result_carries_modifier_fold_nuisance_and_policy_provenance() -> None:
    result = HeterogeneousEffectEstimator().analyze(
        hte_execution(fold_count=4, seed=812),
        hte_table(effect_rows()),
        provenance=provenance("hte-provenance"),
    )

    assert result.status is HTEStatus.COMPLETED
    source_ids = {item.source_id for item in result.provenance}
    assert "hte-config:hte-dml-v1" in source_ids
    assert "hte-modifier-registration:hte-registry-103" in source_ids
    assert "hte-orthogonal-subgroup-interactions" in source_ids
    assert result.assignment_fingerprint_sha256 is not None
    assert result.fold_plan is not None and result.fold_plan.random_seed == 812
    assert all(item.outcome_adapter.model_family for item in result.fold_fits)
    assert all(item.treatment_adapter.model_family for item in result.fold_fits)
    assert result.estimand is not None and result.estimand.estimand_type.value == "cate"
    assert result.modifier.registration_status.value == "registered"
