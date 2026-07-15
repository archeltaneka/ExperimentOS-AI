from __future__ import annotations

import json

from packages.evals.agent_e2e import AgentE2EEvaluator, build_default_agent_e2e_cases
from packages.evals.agent_e2e_report import agent_e2e_report_to_json


def test_agent_e2e_report_identifies_its_code_defined_case_set() -> None:
    result = AgentE2EEvaluator(cases=build_default_agent_e2e_cases()).evaluate()

    payload = json.loads(agent_e2e_report_to_json(result))

    assert payload["dataset_id"] == "agent_e2e.default"
    assert payload["dataset_version"].startswith("sha256:")
    assert len(payload["dataset_version"]) == len("sha256:") + 64
