from __future__ import annotations

from packages.evals.statistical.did_fixtures import run_did_fixture


def test_known_effect_evaluation_fixture_is_hand_calculable() -> None:
    result = run_did_fixture("did_known_positive_effect")

    assert result.status == "completed"
    assert result.cell_means.treated_pre_mean == 10.0
    assert result.cell_means.treated_post_mean == 15.0
    assert result.cell_means.control_pre_mean == 8.0
    assert result.cell_means.control_post_mean == 10.0
    assert result.cell_means.did_estimate == 3.0


def test_invalid_composition_evaluation_fixture_abstains() -> None:
    result = run_did_fixture("did_post_only_treated_unit")

    assert result.status == "abstained"
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "did.composition_change"


def test_did_evaluation_fixture_is_row_order_deterministic() -> None:
    forward = run_did_fixture("did_known_positive_effect")
    reverse = run_did_fixture("did_known_positive_effect", reverse_rows=True)

    assert forward.model_dump(mode="json") == reverse.model_dump(mode="json")
