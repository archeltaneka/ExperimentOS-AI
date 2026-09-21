from packages.agents.service import AgentWorkflowService
from tests.test_agent_analysis_workflow import ForbiddenAgent
from tests.test_analysis_service import fixed_case


def test_graph_cites_returned_analysis_artifact_without_fake_quote():
    request, dataset = fixed_case()
    state = AgentWorkflowService(retrieval_agent=ForbiddenAgent()).run(
        "Analyze", analysis_request=request, analysis_datasets=(dataset,)
    )
    result = state["analysis_result"]
    citation = next(c for c in state["citations"] if c.get("document_id") == result.analysis_id)
    assert citation["metadata"]["source_type"] == "analysis_artifact"
    assert not citation.get("quote")
    assert citation["metadata"]["evidence_fingerprint"] == result.evidence_fingerprint
