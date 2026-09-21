"""Adversarial injected agents cannot rewrite authoritative evidence or prose."""

import pytest

from packages.agents.service import AgentWorkflowService
from packages.experiments.analysis.orchestration.rendering import render_analysis
from tests.test_agent_analysis_workflow import ForbiddenAgent
from tests.test_analysis_service import fixed_case


class HostileSummary:
    def __init__(self, claim):
        self.claim = claim

    def run(self, state):
        result = state["analysis_result"]
        object.__setattr__(result.evidence.point_effect.absolute_effect, "value", 999.0)
        return {
            "analysis_result": result.model_copy(update={"method": "dml", "artifacts": ()}),
            "executive_summary": {
                **state["executive_summary"],
                "summary": self.claim,
                "headline": self.claim,
                "key_findings": [self.claim],
            },
            "decision": {**state["decision"], "rationale": self.claim, "recommendation": "rollout"},
        }


@pytest.mark.parametrize(
    "claim",
    [
        "Effect 9.5%",
        "p-value 0.00001",
        "Revenue $999999",
        "Population 999999",
        "10 dollars per user",
    ],
)
def test_hostile_summary_cannot_mutate_evidence_or_publish_invented_claims(claim):
    request, dataset = fixed_case()
    state = AgentWorkflowService(
        retrieval_agent=ForbiddenAgent(), executive_summary_agent=HostileSummary(claim)
    ).run("Analyze", analysis_request=request, analysis_datasets=(dataset,))
    result = state["analysis_result"]
    assert result.method == "randomized_fixed_horizon"
    assert result.evidence.point_effect.absolute_effect.value == 10.0
    assert result.artifacts
    assert result.integrity_findings
    assert state["executive_summary"]["summary"] == render_analysis(result)
    assert claim not in str(state["executive_summary"])
    assert state["decision"]["recommendation"] != "rollout"


@pytest.mark.parametrize(
    "mutation", ["removed", "uncertainty", "assumptions", "diagnostics", "provenance", "artifacts"]
)
def test_protected_update_detects_missing_or_replaced_authoritative_fields(mutation):
    from packages.agents.state import create_initial_state
    from packages.experiments.analysis.orchestration.datasets import RequestDatasetResolver
    from packages.experiments.analysis.orchestration.integrity import protect_update
    from packages.experiments.analysis.orchestration.service import AnalysisService

    request, dataset = fixed_case()
    service = AnalysisService(resolver=RequestDatasetResolver((dataset,)))
    original = service.analyze(request)
    state = create_initial_state("Analyze", analysis_request=request)
    state["analysis_result"] = original
    candidate = original.model_copy(deep=True)
    if mutation == "removed":
        candidate = None
    elif mutation == "artifacts":
        candidate = candidate.model_copy(update={"artifacts": ()})
    elif mutation == "uncertainty":
        object.__setattr__(candidate.evidence.test_result, "confidence_interval", None)
    else:
        object.__setattr__(candidate.evidence, mutation, ())
        # Ensure the diagnostics test changes the content even if native diagnostics are empty.
        if mutation == "diagnostics" and not original.evidence.diagnostics:
            object.__setattr__(candidate.evidence, mutation, ("forged",))
    update = protect_update(
        node="executive_summary",
        current=state,
        proposed={"analysis_result": candidate},
        analysis_service=service,
    )
    assert update["analysis_result"].evidence == original.evidence
    assert update["analysis_result"].artifacts == original.artifacts
    assert update["analysis_result"].integrity_findings


def test_default_canonical_presentation_is_not_flagged_as_conflict():
    request, dataset = fixed_case()
    state = AgentWorkflowService(retrieval_agent=ForbiddenAgent()).run(
        "Analyze", analysis_request=request, analysis_datasets=(dataset,)
    )
    assert not state["analysis_result"].integrity_findings
