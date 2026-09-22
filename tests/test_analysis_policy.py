import json
from pathlib import Path

from packages.evals.policy.adapters import load_source
from packages.evals.policy.models import PolicySource


def test_required_case_inventory_and_applicable_skips_fail_closed(tmp_path):
    from packages.evals.agent_analysis_cases import (
        ANALYSIS_CHECK_CODES,
        load_analysis_workflow_cases,
    )

    samples = [
        {
            "case": {"analysis_case_id": c.case_id},
            "analysis_checks": {
                code: {"status": "pass", "applicable": True} for code in ANALYSIS_CHECK_CODES
            },
        }
        for c in load_analysis_workflow_cases()
    ]
    samples[0]["analysis_checks"] = {}
    samples[1]["analysis_checks"]["uncertainty_preserved"] = {
        "status": "skipped",
        "applicable": True,
    }
    samples[2]["analysis_checks"]["result_integrity"] = {"status": "skipped", "applicable": False}
    samples[-1] = samples[-2]
    (tmp_path / "agent.json").write_text(json.dumps({"summary": {}, "samples": samples}))
    source = load_source(PolicySource("agent", Path("agent.json"), "agent_json"), tmp_path)
    assert source.metrics["analysis.failures.uncertainty_preserved"].value >= 2
    assert source.metrics["analysis.failures.case_inventory"].value > 0
    assert source.metrics["analysis.failures.result_integrity"].value >= 2


def test_agent_json_policy_consumes_structured_failures(tmp_path):
    payload = {
        "summary": {"sample_count": 1, "fail_count": 1},
        "samples": [
            {
                "analysis_checks": {
                    "uncertainty_preserved": {"status": "fail"},
                    "adapter_identity": {"status": "pass"},
                }
            }
        ],
    }
    (tmp_path / "agent.json").write_text(json.dumps(payload))
    source = load_source(PolicySource("agent", Path("agent.json"), "agent_json"), tmp_path)
    assert source.metrics["analysis.failures.uncertainty_preserved"].value == 1
    assert source.metrics["analysis.failures.adapter_identity"].value == 0


def test_missing_required_json_never_uses_stale_markdown(tmp_path):
    (tmp_path / "agent_evaluation.md").write_text("Everything passed")
    assert (
        load_source(PolicySource("agent", Path("agent_evaluation.json"), "agent_json"), tmp_path)
        is None
    )


def test_missing_check_is_not_counted_as_pass(tmp_path):
    payload = {"summary": {}, "samples": [{"analysis_checks": {"routing": {"status": "pass"}}}]}
    (tmp_path / "agent.json").write_text(json.dumps(payload))
    source = load_source(PolicySource("agent", Path("agent.json"), "agent_json"), tmp_path)
    assert source.metrics["analysis.failures.uncertainty_preserved"].value == 1
