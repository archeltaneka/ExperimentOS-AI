"""Repository-local real workflow cases shared by agent and end-to-end evaluation."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict, JsonValue

from packages.agents.service import AgentWorkflowService
from packages.experiments.analysis.causal.did.service import DifferenceInDifferencesService
from packages.experiments.analysis.orchestration.datasets import AnalysisDatasetInput
from packages.experiments.analysis.orchestration.requests import (
    AnalysisRoutingRefusal,
    DidWorkflowRequest,
    FixedHorizonWorkflowRequest,
    normalize_analysis_input,
)
from packages.experiments.analysis.orchestration.results import AnalysisEvidence, project_evidence
from packages.experiments.analysis.randomized.service import RandomizedAnalysisService
from packages.experiments.analysis.validation import AnalysisTable

FIXTURE_DIRECTORY = Path(__file__).resolve().parents[2] / "data/eval/workflow_analysis"


class AnalysisWorkflowCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    case_id: str
    ask_payload: dict[str, JsonValue]
    expected_method: str | None
    expected_status: str
    presenter_candidate: str | None = None
    optional_unavailable: bool = False


def load_analysis_workflow_cases() -> tuple[AnalysisWorkflowCase, ...]:
    cases = tuple(
        AnalysisWorkflowCase.model_validate_json(path.read_text())
        for path in sorted(FIXTURE_DIRECTORY.glob("*.json"))
    )
    for case in cases:
        request = normalize_analysis_input(
            case.ask_payload.get("analysis"), experiment_id=str(case.ask_payload["experiment_id"])
        )
        if isinstance(request, AnalysisRoutingRefusal):
            raise ValueError(f"Fixture {case.case_id} contains an invalid declaration")
    return cases


class _NoRetrieval:
    def run(self, state):
        raise AssertionError("Analysis fixtures must not call retrieval or an external provider")


class _CandidatePresenter:
    def __init__(self, text: str) -> None:
        self.text = text

    def run(self, state):
        return {"executive_summary": {**state["executive_summary"], "summary": self.text}}


class _UnavailableWorkflow(AgentWorkflowService):
    def run(self, *args, **kwargs):
        from packages.experiments.analysis.causal.econml.dependency import AdapterError

        with patch(
            "packages.experiments.analysis.causal.econml.dependency.load_econml",
            side_effect=AdapterError(
                "OPTIONAL_DEPENDENCY_UNAVAILABLE", "Offline unavailable-runtime case"
            ),
        ):
            return super().run(*args, **kwargs)


def build_analysis_case_service(case: AnalysisWorkflowCase) -> AgentWorkflowService:
    factory = _UnavailableWorkflow if case.optional_unavailable else AgentWorkflowService
    return factory(
        retrieval_agent=_NoRetrieval(),
        executive_summary_agent=_CandidatePresenter(case.presenter_candidate)
        if case.presenter_candidate is not None
        else None,
    )


def run_direct_reference(case: AnalysisWorkflowCase) -> AnalysisEvidence | None:
    """Call native analyzers directly, without orchestration registry or dispatch."""
    request = normalize_analysis_input(
        case.ask_payload["analysis"], experiment_id=str(case.ask_payload["experiment_id"])
    )
    datasets = case.ask_payload.get("analysis_datasets")
    if not isinstance(datasets, list) or not datasets:
        return None
    dataset = AnalysisDatasetInput.model_validate(datasets[0])
    table = AnalysisTable(columns=dataset.columns, rows=dataset.rows)
    if isinstance(request, FixedHorizonWorkflowRequest):
        return project_evidence(
            RandomizedAnalysisService().analyze(
                request.execution, table, request.binding, provenance=dataset.provenance
            )
        )
    if isinstance(request, DidWorkflowRequest):
        columns = {
            request.execution.binding.time_column,
            request.execution.binding.treatment_start_column,
        }
        rows = tuple(
            tuple(
                datetime.fromisoformat(value)
                if column in columns and isinstance(value, str)
                else value
                for column, value in zip(table.columns, row, strict=True)
            )
            for row in table.rows
        )
        return project_evidence(
            DifferenceInDifferencesService().analyze(
                request.execution,
                AnalysisTable(columns=table.columns, rows=rows),
                provenance=dataset.provenance,
            )
        )
    return None
