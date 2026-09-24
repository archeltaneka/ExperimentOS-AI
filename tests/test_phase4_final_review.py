"""Reject unsupported closeout claims and changed evidence, not estimator re-tests."""

import hashlib
import json
from copy import deepcopy

import pytest


def fixture_review(tmp_path):
    result = {"id": "gate", "status": "pass", "exit_code": 0, "argv": ["test"]}
    payload = {"failed": 0, "cases": 7, "command": result}
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(payload))
    return {
        "schema_version": "phase4-final-review-v1",
        "metadata": {"git_commit": "a" * 40, "review_date": "2026-09-24"},
        "evidence": {
            "gate": {
                "path": "evidence.json",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "pointer": "/failed",
                "value": 0,
            },
            "command-result": {
                "path": "evidence.json",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "pointer": "/command",
                "value": result,
            },
        },
        "commands": [
            {
                "id": "gate",
                "status": "pass",
                "exit_code": 0,
                "required": True,
                "command": "test",
                "evidence": ["command-result"],
            }
        ],
        "capabilities": [
            {
                "id": "test",
                "classification": "ADVISORY",
                "scope": "bounded fixture",
                "limitations": ["fixture only"],
                "evidence": ["gate"],
            }
        ],
        "principles": [
            {"id": "test", "status": "PASS", "claim": "fixture reviewed", "evidence": ["gate"]}
        ],
        "findings": [],
        "sections": [
            {
                "title": "Evaluation evidence",
                "claims": [{"text": "No failed cases in fixture.", "evidence": ["gate"]}],
            }
        ],
        "milestone_readiness": "READY_WITH_ADVISORIES",
    }


def api():
    from packages.evals import phase4_review

    return phase4_review


def test_changed_artifact_cannot_support_a_review(tmp_path):
    review = fixture_review(tmp_path)
    (tmp_path / "evidence.json").write_text('{"failed": 1}')
    with pytest.raises(ValueError, match="digest"):
        api().validate_review(review, tmp_path)


def test_wrong_json_claim_rejected_even_when_file_hash_matches(tmp_path):
    review = fixture_review(tmp_path)
    review["evidence"]["gate"]["value"] = 1
    with pytest.raises(ValueError, match="value"):
        api().validate_review(review, tmp_path)


@pytest.mark.parametrize(
    "mutation", ["blocker", "required_failure", "required_skip", "blocked_capability"]
)
def test_readiness_cannot_override_blocking_evidence(tmp_path, mutation):
    review = fixture_review(tmp_path)
    if mutation == "blocker":
        review["findings"] = [
            {
                "id": "B1",
                "kind": "BLOCKING",
                "severity": "critical",
                "capability": "test",
                "description": "Broken guarantee",
                "impact": "Cannot close",
                "follow_up": "Repair guarantee",
                "required_before_close": True,
                "evidence": ["gate"],
            }
        ]
    elif mutation == "required_failure":
        review["commands"][0].update(status="fail", exit_code=1)
    elif mutation == "required_skip":
        review["commands"][0].update(status="skipped", exit_code=None)
    else:
        review["capabilities"][0]["classification"] = "BLOCKED"
    if mutation in {"required_failure", "required_skip"}:
        path = tmp_path / "evidence.json"
        payload = json.loads(path.read_text())
        payload["command"].update({k: review["commands"][0][k] for k in ("status", "exit_code")})
        path.write_text(json.dumps(payload))
        for item in review["evidence"].values():
            item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        review["evidence"]["command-result"]["value"] = payload["command"]
    with pytest.raises(ValueError, match="readiness"):
        api().validate_review(review, tmp_path)
    review["milestone_readiness"] = "NOT_READY_BLOCKING_FINDINGS"
    api().validate_review(review, tmp_path)


def test_missing_reference_and_path_escape_rejected(tmp_path):
    review = fixture_review(tmp_path)
    review["capabilities"][0]["evidence"] = ["absent"]
    with pytest.raises(ValueError, match="reference"):
        api().validate_review(review, tmp_path)
    review = fixture_review(tmp_path)
    review["evidence"]["gate"]["path"] = "../outside.json"
    with pytest.raises(ValueError, match="path"):
        api().validate_review(review, tmp_path)


def test_rendering_is_derived_and_stale_markdown_is_detected(tmp_path):
    review = fixture_review(tmp_path)
    api().validate_review(review, tmp_path)
    rendered = api().render_review(review)
    assert "READY_WITH_ADVISORIES" in rendered
    assert "ADVISORY" in rendered
    assert "No failed cases in fixture." in rendered
    assert "gate" in rendered
    changed = deepcopy(review)
    changed["sections"][0]["claims"][0]["text"] = "A corrected claim."
    assert api().render_review(changed) != rendered


def test_production_classification_requires_all_readiness_dimensions(tmp_path):
    review = fixture_review(tmp_path)
    review["capabilities"][0]["classification"] = "PRODUCTION_READY_WITHIN_SCOPE"
    with pytest.raises(ValueError, match="dimensions"):
        api().validate_review(review, tmp_path)


def test_render_does_not_depend_on_json_object_key_order(tmp_path):
    review = fixture_review(tmp_path)
    review["metadata"]["branch"] = "audit"
    sorted_roundtrip = json.loads(json.dumps(review, sort_keys=True))
    assert api().render_review(review) == api().render_review(sorted_roundtrip)


def test_cli_check_rejects_stale_markdown(tmp_path, monkeypatch):
    review = fixture_review(tmp_path)
    path = tmp_path / "review.json"
    path.write_text(json.dumps(review))
    markdown = tmp_path / "review.md"
    markdown.write_text("stale success report")
    monkeypatch.chdir(tmp_path)
    args = ["--review", str(path), "--output", str(markdown)]
    assert api().main([*args, "--check"]) == 1
    assert markdown.read_text() == "stale success report"
    assert api().main(args) == 0
    assert api().main([*args, "--check"]) == 0


@pytest.mark.parametrize(
    "field,value", [("status", "skipped"), ("command", "invented --success"), ("id", "unexecuted")]
)
def test_command_claim_must_match_executed_evidence(tmp_path, field, value):
    review = fixture_review(tmp_path)
    review["commands"][0][field] = value
    with pytest.raises(ValueError, match="^command evidence"):
        api().validate_review(review, tmp_path)
