"""End-to-end behavior for DML-backed subgroup effects."""

from __future__ import annotations

import pytest

from packages.experiments.analysis.causal.hte import HTEStatus, HTESubgroupStatus
from packages.experiments.analysis.causal.hte.service import HeterogeneousEffectEstimator
from tests.causal_identification_fixtures import provenance
from tests.hte_fixtures import effect_rows, hte_execution, hte_table


@pytest.mark.parametrize(
    ("effects", "heterogeneity"),
    [
        ((("ID", 1.0), ("SG", 3.0)), True),
        ((("ID", 2.0), ("SG", 2.0)), False),
        ((("ID", 0.0), ("SG", 0.0)), False),
    ],
)
def test_service_estimates_known_homogeneous_and_null_subgroup_effects(
    effects: tuple[tuple[str, float], ...], heterogeneity: bool
) -> None:
    result = HeterogeneousEffectEstimator().analyze(
        hte_execution(fold_count=4),
        hte_table(effect_rows(effects)),
        provenance=provenance("hte-service"),
    )

    assert result.status is HTEStatus.COMPLETED
    assert all(item.status is HTESubgroupStatus.COMPLETED for item in result.subgroup_results)
    assert tuple(item.estimate for item in result.subgroup_results) == pytest.approx(
        tuple(effect for _group, effect in effects), abs=0.25
    )
    assert all(
        item.standard_error is not None and item.standard_error > 0
        for item in result.subgroup_results
    )
    assert result.global_heterogeneity.detected is heterogeneity
    assert result.fold_plan is not None
    assert len(result.fold_fits) == 4


def test_service_is_invariant_to_input_row_order() -> None:
    rows = effect_rows()
    estimator = HeterogeneousEffectEstimator()
    first = estimator.analyze(
        hte_execution(fold_count=4), hte_table(rows), provenance=provenance("order")
    )
    second = estimator.analyze(
        hte_execution(fold_count=4),
        hte_table(tuple(reversed(rows))),
        provenance=provenance("order"),
    )

    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_service_records_explicit_holm_multiplicity_without_pairwise_search() -> None:
    result = HeterogeneousEffectEstimator().analyze(
        hte_execution(fold_count=4), hte_table(effect_rows()), provenance=provenance("holm")
    )

    assert result.multiplicity.subgroup_effect_tests == 2
    assert result.multiplicity.interaction_tests == 1
    assert result.multiplicity.pairwise_tests == 0
    assert result.multiplicity.global_tests == 1
    assert result.multiplicity.correction_method.value == "holm"
    assert result.multiplicity.global_p_value_adjusted is False
