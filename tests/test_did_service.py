"""End-to-end bounded DiD service behavior."""

from __future__ import annotations

import pytest

from packages.experiments.analysis.causal.did import (
    DidStatus,
    DifferenceInDifferencesService,
)
from tests.causal_identification_fixtures import provenance
from tests.did_fixtures import (
    add_extra_pre_rows,
    did_execution,
    did_table,
    extra_pre_periods,
    no_effect_rows,
    positive_effect_rows,
)


def _codes(result: object) -> set[str]:
    return {item.code for item in result.diagnostics}  # type: ignore[attr-defined]


def test_positive_effect_returns_did_att_and_clustered_inference() -> None:
    execution = did_execution()

    result = DifferenceInDifferencesService().analyze(
        execution,
        did_table(positive_effect_rows()),
        provenance=provenance("did-input"),
    )

    assert result.status is DidStatus.COMPLETED
    assert result.cell_means is not None
    assert result.test_result is not None
    assert result.cell_means.did_estimate == pytest.approx(3.0, abs=1e-12)
    assert result.test_result.standard_error == pytest.approx(2.103464143623269, abs=1e-12)
    assert result.test_result.cluster_count == 20
    assert result.test_result.degrees_of_freedom == 19
    assert result.estimand is not None
    assert result.estimand.estimand_type.value == "did_att"
    assert result.estimand.target_population.kind.value == "treated"
    assert result.sample_counts.retained_units == 20
    assert "did.few_clusters" in _codes(result)
    assert {item.source_type.value for item in result.provenance} >= {
        "user_supplied",
        "analysis_request",
        "derived",
    }


def test_no_effect_fixture_returns_finite_null_inference() -> None:
    result = DifferenceInDifferencesService().analyze(
        did_execution(),
        did_table(no_effect_rows()),
        provenance=provenance("did-input"),
    )

    assert result.status is DidStatus.COMPLETED
    assert result.cell_means is not None
    assert result.test_result is not None
    assert result.cell_means.did_estimate == pytest.approx(0.0, abs=1e-12)
    assert result.test_result.statistic == pytest.approx(0.0, abs=1e-12)
    assert result.test_result.p_value == pytest.approx(1.0, abs=1e-12)


def test_unbalanced_panel_abstains_without_returning_filtered_estimate() -> None:
    rows = list(positive_effect_rows())
    rows.pop(1)

    result = DifferenceInDifferencesService().analyze(
        did_execution(),
        did_table(tuple(rows)),
        provenance=provenance("did-input"),
    )

    assert result.status is DidStatus.ABSTAINED
    assert result.cell_means is None
    assert result.test_result is None
    assert result.abstention_reason is not None
    assert result.sample_counts.retained_units == 19
    assert "did.incomplete_unit_coverage" in _codes(result)


def test_minimum_cluster_policy_abstains_before_estimation() -> None:
    keep = {f"t-{index:02d}" for index in range(1, 4)} | {f"c-{index:02d}" for index in range(1, 4)}
    rows = tuple(row for row in positive_effect_rows() if row["unit_id"] in keep)

    result = DifferenceInDifferencesService().analyze(
        did_execution(),
        did_table(rows),
        provenance=provenance("did-input"),
    )

    assert result.status is DidStatus.ABSTAINED
    assert result.cell_means is None
    assert result.test_result is None
    assert {"did.insufficient_clusters", "did.insufficient_group_clusters"} <= _codes(result)


def test_divergent_pretrend_warns_without_changing_canonical_att() -> None:
    execution = did_execution(extra_pre_periods=extra_pre_periods())
    rows = add_extra_pre_rows(
        positive_effect_rows(),
        treated_means=(-6.0, 2.0),
        control_means=(6.0, 7.0),
    )

    result = DifferenceInDifferencesService().analyze(
        execution,
        did_table(rows),
        provenance=provenance("did-input"),
    )

    assert result.status is DidStatus.COMPLETED
    assert result.cell_means is not None
    assert result.cell_means.did_estimate == pytest.approx(3.0, abs=1e-12)
    assert result.pretrend.evidence_concern is True
    assert "did.parallel_trends_evidence_concern" in _codes(result)
    parallel = next(item for item in result.assumptions if item.code.value == "parallel_trends")
    assert parallel.status.value == "asserted"


def test_result_is_invariant_to_source_row_order() -> None:
    rows = positive_effect_rows()
    service = DifferenceInDifferencesService()

    forward = service.analyze(
        did_execution(),
        did_table(rows),
        provenance=provenance("did-input"),
    )
    reverse = service.analyze(
        did_execution(),
        did_table(tuple(reversed(rows))),
        provenance=provenance("did-input"),
    )

    assert forward.model_dump_json() == reverse.model_dump_json()
