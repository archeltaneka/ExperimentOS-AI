"""A malformed or incomplete inventory cannot masquerade as complete coverage."""

import json

import pytest

from packages.evals.agent_analysis_cases import load_analysis_workflow_cases


def test_duplicate_case_ids_are_rejected(tmp_path):
    case = load_analysis_workflow_cases()[0]
    for name in ("one.json", "two.json"):
        (tmp_path / name).write_text(case.model_dump_json())
    with pytest.raises(ValueError, match="duplicate"):
        load_analysis_workflow_cases(tmp_path)


def test_empty_inventory_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="empty"):
        load_analysis_workflow_cases(tmp_path)


def test_malformed_case_never_echoes_private_input(tmp_path):
    (tmp_path / "case.json").write_text(json.dumps({"private": "PRIVATE_ROW_SENTINEL"}))
    with pytest.raises(ValueError) as error:
        load_analysis_workflow_cases(tmp_path)
    assert "PRIVATE_ROW_SENTINEL" not in str(error.value)


def test_required_inventory_is_independent_of_supplied_cases():
    from packages.evals.statistical.workflow.cases import validate_case_inventory

    with pytest.raises(ValueError, match="missing required"):
        validate_case_inventory((), required_ids=frozenset({"randomized"}))


def test_inventory_is_sorted_and_versioned():
    cases = load_analysis_workflow_cases()
    assert [c.case_id for c in cases] == sorted(c.case_id for c in cases)
    assert all(c.case_version == "1" for c in cases)


@pytest.mark.parametrize("content", ["{not-json", '{"case_id": ""}'])
def test_invalid_metadata_is_rejected(tmp_path, content):
    (tmp_path / "case.json").write_text(content)
    with pytest.raises(ValueError, match="invalid workflow case metadata"):
        load_analysis_workflow_cases(tmp_path)


def test_numeric_reference_requires_justified_float_tolerance():
    from packages.evals.statistical.workflow.models import WorkflowExpectations

    with pytest.raises(ValueError, match="tolerance"):
        WorkflowExpectations(numerical=[{"path": "effect", "value": 1.5}])
    assert WorkflowExpectations(numerical=[{"path": "count", "value": 2}]).numerical[0].value == 2
