"""DR subgroup effects preserve timing, support and direct heterogeneity evidence."""

from __future__ import annotations

import pytest

from packages.experiments.analysis.causal.hte import evaluate_hte_quality
from packages.experiments.analysis.causal.variables import MeasurementTiming
from tests.causal_identification_fixtures import provenance
from tests.econml_fixtures import assert_owned_graph, dr_execution, requires_econml
from tests.hte_fixtures import effect_rows, hte_execution, hte_modifier, hte_table


@requires_econml
@pytest.mark.parametrize(
    ("effects", "heterogeneous"),
    [
        ((("ID", 1.0), ("SG", 3.0)), True),
        ((("ID", 2.0), ("SG", 2.0)), False),
        ((("ID", 0.0), ("SG", 0.0)), False),
    ],
)
def test_subgroup_effects_and_direct_evidence_match_known_semantics(effects, heterogeneous) -> None:
    from packages.experiments.analysis.causal.econml import EconMLHTEAdapter

    result = EconMLHTEAdapter().analyze(
        dr_execution(fold_count=4), hte_table(effect_rows(effects)), provenance=provenance()
    )
    assert result.status.value == "completed", result.model_dump_json()
    assert [item.estimate for item in result.subgroup_results] == pytest.approx(
        [effect for _, effect in effects], abs=0.25
    )
    assert all(item.standard_error > 0 for item in result.subgroup_results)
    assert all(
        item.uncertainty_method == "doubly_robust_statsmodels_hc1"
        for item in result.subgroup_results
    )
    assert result.interactions[0].estimate == pytest.approx(effects[1][1] - effects[0][1], abs=0.25)
    assert result.global_heterogeneity.detected is heterogeneous
    assert result.global_heterogeneity.degrees_of_freedom == 1
    assert result.global_heterogeneity.method == "doubly_robust_interaction_wald_chi_square"
    assert result.adapter_provenance.estimator_class == "econml.dr.LinearDRLearner"
    assert result.adapter_provenance.estimand == "cate"
    assert result.assignment_fingerprint_sha256 is not None
    assert len(result.fold_fits) == 4
    assert evaluate_hte_quality(result).blocking_findings == ()
    assert_owned_graph(result)


@requires_econml
def test_repeatability_and_row_order_invariance_for_hte() -> None:
    from packages.experiments.analysis.causal.econml import EconMLHTEAdapter

    adapter = EconMLHTEAdapter()
    execution = dr_execution(fold_count=4)
    rows = effect_rows()
    first = adapter.analyze(execution, hte_table(rows), provenance=provenance())
    assert first.status.value == "completed"
    for selected in (rows, tuple(reversed(rows))):
        assert (
            adapter.analyze(execution, hte_table(selected), provenance=provenance()).model_dump()
            == first.model_dump()
        )


@pytest.mark.parametrize("timing", [MeasurementTiming.POST_TREATMENT, MeasurementTiming.UNKNOWN])
def test_invalid_modifier_abstains_before_fitting(monkeypatch, timing) -> None:
    from packages.experiments.analysis.causal.econml import EconMLHTEAdapter, dependency

    monkeypatch.setattr(dependency, "load_econml", lambda: pytest.fail("modifier gate bypassed"))
    result = EconMLHTEAdapter().analyze(
        dr_execution(modifier=hte_modifier(timing=timing)),
        hte_table(effect_rows()),
        provenance=provenance(),
    )
    assert result.status.value == "invalid"
    assert all(item.estimate is None for item in result.subgroup_results)


def test_baseline_method_is_not_silently_reinterpreted() -> None:
    from packages.experiments.analysis.causal.econml import EconMLHTEAdapter

    result = EconMLHTEAdapter().analyze(
        hte_execution(), hte_table(effect_rows()), provenance=provenance()
    )
    assert result.status.value == "unsupported"


@requires_econml
def test_sparse_groups_suppress_effects_and_conclusive_global_evidence() -> None:
    from packages.experiments.analysis.causal.econml import EconMLHTEAdapter

    rows = effect_rows((("ID", 1.0),), rows_per_group=80) + effect_rows(
        (("SG", 3.0),), rows_per_group=8
    )
    result = EconMLHTEAdapter().analyze(dr_execution(), hte_table(rows), provenance=provenance())
    assert result.status.value == "abstained"
    assert result.subgroup_results[1].estimate is None
    assert result.global_heterogeneity.status.value == "unavailable"


@requires_econml
@pytest.mark.parametrize("operation", ["fit", "effect_inference", "coef__inference"])
def test_hte_fit_and_inference_failures_do_not_escape(monkeypatch, operation: str) -> None:
    from econml.dr import LinearDRLearner

    from packages.experiments.analysis.causal.econml import EconMLHTEAdapter

    def fail(*args, **kwargs):
        raise RuntimeError("row-secret")

    monkeypatch.setattr(LinearDRLearner, operation, fail)
    result = EconMLHTEAdapter().analyze(
        dr_execution(fold_count=4), hte_table(effect_rows()), provenance=provenance()
    )
    assert result.status.value == "abstained"
    assert result.abstention_reason == (
        "ESTIMATOR_FIT_FAILURE" if operation == "fit" else "INFERENCE_FAILURE"
    )
    assert "row-secret" not in result.model_dump_json()
    assert_owned_graph(result)
