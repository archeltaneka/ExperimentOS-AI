import json
from pathlib import Path

from packages.evals.policy.adapters import load_source
from packages.evals.policy.models import PolicySource


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
