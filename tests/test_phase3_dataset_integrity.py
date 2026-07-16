from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.evals.agent_dataset import load_agent_evaluation_dataset
from packages.evals.dataset import load_evaluation_dataset
from packages.evals.dataset_manifest import build_dataset_manifest


def test_dataset_manifest_is_content_addressed_and_repository_relative(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    dataset.write_text('[{"id":"case-1"}]\n', encoding="utf-8")

    manifest = build_dataset_manifest(dataset, dataset_id="qa.golden", case_count=1)

    assert manifest.dataset_id == "qa.golden"
    assert manifest.version.startswith("sha256:")
    assert len(manifest.version) == len("sha256:") + 64
    assert not Path(manifest.relative_path).is_absolute()
    assert manifest.case_count == 1


@pytest.mark.parametrize("field,value", [("category", "invented"), ("difficulty", "impossible")])
def test_qa_dataset_rejects_unknown_enums(tmp_path: Path, field: str, value: str) -> None:
    source = json.loads(Path("data/eval/qa_dataset.json").read_text(encoding="utf-8"))
    source[0][field] = value
    dataset = tmp_path / "qa.json"
    dataset.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(ValueError, match=field):
        load_evaluation_dataset(dataset)


def test_qa_dataset_rejects_unknown_failure_mode(tmp_path: Path) -> None:
    source = json.loads(Path("data/eval/qa_dataset.json").read_text(encoding="utf-8"))
    source[0]["expected_failure_mode"] = "silent_fallback"
    dataset = tmp_path / "qa.json"
    dataset.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(ValueError, match="expected_failure_mode"):
        load_evaluation_dataset(dataset)


def test_agent_dataset_rejects_unknown_required_agent(tmp_path: Path) -> None:
    source = json.loads(Path("data/eval/agent_dataset.json").read_text(encoding="utf-8"))
    source[0]["expected_required_agents"] = ["vendor_agent"]
    dataset = tmp_path / "agent.json"
    dataset.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(ValueError, match="expected_required_agents"):
        load_agent_evaluation_dataset(dataset)


@pytest.mark.parametrize(
    "field,value",
    [
        ("category", "invented"),
        ("expected_intent", "vendor_intent"),
        ("expected_decision_status", "unknown"),
        ("expected_summary_status", "unknown"),
        ("expected_approval_status", "unknown"),
        ("expected_failure_mode", "unknown"),
    ],
)
def test_agent_dataset_rejects_unknown_enums(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    source = json.loads(Path("data/eval/agent_dataset.json").read_text(encoding="utf-8"))
    source[0][field] = value
    dataset = tmp_path / "agent.json"
    dataset.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(ValueError, match=field):
        load_agent_evaluation_dataset(dataset)


def test_committed_datasets_preserve_declared_order_and_unique_ids() -> None:
    qa_raw = json.loads(Path("data/eval/qa_dataset.json").read_text(encoding="utf-8"))
    agent_raw = json.loads(Path("data/eval/agent_dataset.json").read_text(encoding="utf-8"))
    qa_ids = [case.id for case in load_evaluation_dataset()]
    agent_ids = [case.id for case in load_agent_evaluation_dataset()]

    assert qa_ids == [row["id"] for row in qa_raw]
    assert agent_ids == [row["id"] for row in agent_raw]
    assert len(qa_ids) == len(set(qa_ids))
    assert len(agent_ids) == len(set(agent_ids))
