"""Sparse and subgroup-specific overlap safety tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from packages.experiments.analysis.causal.dml import (
    NuisanceAdapterMetadata,
    NuisanceFeatureBatch,
    NuisanceFitReport,
    NuisanceFitStatus,
    NuisanceRole,
)
from packages.experiments.analysis.causal.hte import HTEStatus, HTESubgroupStatus
from packages.experiments.analysis.causal.hte.service import HeterogeneousEffectEstimator
from tests.causal_identification_fixtures import provenance
from tests.hte_fixtures import effect_rows, hte_execution, hte_table


@dataclass
class SubgroupOverlapTreatmentAdapter:
    feature_order: tuple[str, ...] = ("prior_orders", "country::sg")
    seed: int = 103
    metadata: NuisanceAdapterMetadata = field(init=False)

    def __post_init__(self) -> None:
        self.metadata = NuisanceAdapterMetadata.create(
            role=NuisanceRole.TREATMENT,
            adapter_name="subgroup_overlap_fixture",
            adapter_version="1",
            model_family="test_probability",
            hyperparameters={},
            preprocessing="identity",
            feature_order=self.feature_order,
            seed=self.seed,
            minimum_training_rows=4,
            dependency_name="none",
            dependency_version="owned-test-double",
        )

    def for_fold(self, seed: int):
        return SubgroupOverlapTreatmentAdapter(feature_order=self.feature_order, seed=seed)

    def fit(self, batch: NuisanceFeatureBatch, target: tuple[float, ...]) -> NuisanceFitReport:
        return NuisanceFitReport(
            role=NuisanceRole.TREATMENT,
            status=NuisanceFitStatus.CONVERGED,
            converged=True,
            training_count=len(target),
            classes=(0, 1),
        )

    def predict_probability(self, batch: NuisanceFeatureBatch) -> tuple[float, ...]:
        return tuple(
            (0.99 if row[0] >= 0.0 else 0.01)
            if row[1] == 1.0
            else (0.60 if row[0] >= 0.0 else 0.40)
            for row in batch.rows
        )


def test_sparse_subgroup_abstains_without_estimate_or_interval() -> None:
    rows = effect_rows(rows_per_group=12)
    result = HeterogeneousEffectEstimator().analyze(
        hte_execution(fold_count=2), hte_table(rows), provenance=provenance("sparse")
    )

    assert result.status is HTEStatus.ABSTAINED
    assert all(item.status is HTESubgroupStatus.ABSTAINED for item in result.subgroup_results)
    assert all(
        item.estimate is None and item.confidence_interval is None
        for item in result.subgroup_results
    )
    assert {item.abstention_reason for item in result.subgroup_results} == {
        "hte.subgroup.sparse_total"
    }


def test_low_treated_and_low_control_subgroups_have_distinct_abstentions() -> None:
    base = effect_rows()
    low_treated = tuple(
        {
            **row,
            "treated": int(row["country"] == "ID" and int(str(row["account_id"])[-3:]) % 2 == 1)
            if row["country"] == "ID"
            else int(int(str(row["account_id"])[-3:]) < 4),
        }
        for row in base
    )
    low_control = tuple(
        {
            **row,
            "treated": int(str(row["account_id"])[-3:]) % 2
            if row["country"] == "ID"
            else int(int(str(row["account_id"])[-3:]) >= 4),
        }
        for row in base
    )

    treated_result = HeterogeneousEffectEstimator().analyze(
        hte_execution(fold_count=2), hte_table(low_treated), provenance=provenance("low-treated")
    )
    control_result = HeterogeneousEffectEstimator().analyze(
        hte_execution(fold_count=2), hte_table(low_control), provenance=provenance("low-control")
    )

    treated_sg = next(item for item in treated_result.subgroup_results if item.subgroup_id == "sg")
    control_sg = next(item for item in control_result.subgroup_results if item.subgroup_id == "sg")
    assert treated_sg.abstention_reason == "hte.subgroup.sparse_treated"
    assert control_sg.abstention_reason == "hte.subgroup.sparse_control"


def test_healthy_global_overlap_does_not_override_failed_subgroup_overlap() -> None:
    rows = (
        *effect_rows((("ID", 1.0),), rows_per_group=180),
        *effect_rows((("SG", 3.0),), rows_per_group=20),
    )
    result = HeterogeneousEffectEstimator(
        treatment_adapter=SubgroupOverlapTreatmentAdapter()
    ).analyze(
        hte_execution(fold_count=2), hte_table(rows), provenance=provenance("subgroup-overlap")
    )

    assert result.global_overlap is not None
    assert result.global_overlap.status.value in {"acceptable", "weak"}
    by_id = {item.subgroup_id: item for item in result.subgroup_results}
    assert by_id["id"].status is HTESubgroupStatus.COMPLETED
    assert by_id["sg"].status is HTESubgroupStatus.ABSTAINED
    assert by_id["sg"].abstention_reason == "hte.subgroup.overlap_severe"
    assert result.status is HTEStatus.ABSTAINED
    assert result.global_heterogeneity.status.value == "unavailable"
