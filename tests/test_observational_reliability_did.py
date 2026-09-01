"""Issue #101 DiD reliability references through the production service."""

from __future__ import annotations

import pytest

from packages.evals.statistical.did_fixtures import run_did_fixture
from packages.experiments.analysis.causal.did import DidStatus


def _codes(result: object) -> set[str]:
    return {item.code for item in result.diagnostics}  # type: ignore[attr-defined]


def test_known_effect_did_reference_has_independent_accuracy_and_uncertainty() -> None:
    result = run_did_fixture("did_known_positive_effect")

    assert result.status is DidStatus.COMPLETED
    assert result.estimand is not None
    assert result.estimand.estimand_type.value == "did_att"
    assert result.estimand.target_population.kind.value == "treated"
    assert result.cell_means is not None
    assert result.cell_means.treated_pre_mean == pytest.approx(10.0, abs=1e-12)
    assert result.cell_means.treated_post_mean == pytest.approx(15.0, abs=1e-12)
    assert result.cell_means.control_pre_mean == pytest.approx(8.0, abs=1e-12)
    assert result.cell_means.control_post_mean == pytest.approx(10.0, abs=1e-12)
    assert result.cell_means.treated_change == pytest.approx(5.0, abs=1e-12)
    assert result.cell_means.control_change == pytest.approx(2.0, abs=1e-12)
    assert result.cell_means.did_estimate == pytest.approx(3.0, abs=1e-12)
    assert result.test_result is not None
    assert result.test_result.standard_error == pytest.approx(2.103464143623269, abs=1e-12)
    assert result.test_result.confidence_interval.confidence_level == 0.95
    assert result.test_result.variance_estimator.value == "cluster_robust_cr1"
    assert result.test_result.cluster_count == 20


def test_null_effect_did_reference_is_completed_without_estimand_substitution() -> None:
    result = run_did_fixture("did_null_effect")

    assert result.status is DidStatus.COMPLETED
    assert result.cell_means is not None
    assert result.cell_means.did_estimate == pytest.approx(0.0, abs=1e-12)
    assert result.estimand is not None
    assert result.estimand.estimand_type.value == "did_att"


@pytest.mark.parametrize(
    ("fixture_id", "status", "code"),
    [
        ("did_staggered_adoption", DidStatus.INVALID, "did.staggered_adoption"),
        ("did_reversed_timing", DidStatus.INVALID, "did.reversed_timing"),
        ("did_missing_treated_group", DidStatus.ABSTAINED, "did.missing_treated_group"),
        ("did_missing_control_group", DidStatus.ABSTAINED, "did.missing_control_group"),
        ("did_incomplete_periods", DidStatus.ABSTAINED, "did.incomplete_unit_coverage"),
    ],
)
def test_invalid_or_incomplete_did_design_never_fabricates_inference(
    fixture_id: str,
    status: DidStatus,
    code: str,
) -> None:
    result = run_did_fixture(fixture_id)

    assert result.status is status
    assert code in _codes(result)
    assert result.cell_means is None
    assert result.test_result is None
    assert result.abstention_reason is not None


def test_divergent_pretrend_is_advisory_and_never_called_verified() -> None:
    result = run_did_fixture("did_divergent_pretrend")

    assert result.status is DidStatus.COMPLETED
    assert result.pretrend.evidence_concern is True
    assert "did.parallel_trends_evidence_concern" in _codes(result)
    parallel = next(item for item in result.assumptions if item.code.value == "parallel_trends")
    assert parallel.status.value != "verified"


def test_few_cluster_case_remains_available_with_advisory() -> None:
    result = run_did_fixture("did_few_clusters")

    assert result.status is DidStatus.COMPLETED
    assert "did.few_clusters" in _codes(result)
    assert result.test_result is not None
    assert result.test_result.cluster_count == 20
