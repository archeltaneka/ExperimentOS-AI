from pathlib import Path

from apps.api.ask_service import AskRequest
from packages.evals.agent_analysis_cases import load_analysis_workflow_cases
from packages.experiments.analysis.orchestration.requests import normalize_analysis_input


def test_workflow_documentation_declares_boundaries_and_runnable_examples():
    text = Path("docs/phase4/workflow_analysis.md").read_text()
    for phrase in (
        "AnalysisService",
        "legacy_rag",
        "analysis_request",
        "analysis_result",
        "human approval",
        "does not calculate statistics",
        "provenance",
        "independently callable",
        "never invented",
        "authoritative",
        "unavailable",
    ):
        assert phrase in text
    for name in (
        "randomized",
        "did",
        "business",
        "insufficient",
        "optional_unavailable",
        "prose_conflict",
    ):
        assert f"{name}.json" in text
    for case in load_analysis_workflow_cases():
        request = AskRequest.model_validate(case.ask_payload)
        assert normalize_analysis_input(request.analysis, experiment_id=request.experiment_id)
