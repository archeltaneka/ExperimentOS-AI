"""Repository-local real workflow cases shared by agent and end-to-end evaluation."""

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Literal
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict, JsonValue

from packages.agents.service import AgentWorkflowService
from packages.experiments.analysis.causal.did.service import DifferenceInDifferencesService
from packages.experiments.analysis.orchestration.datasets import AnalysisDatasetInput
from packages.experiments.analysis.orchestration.requests import (
    AnalysisRoutingRefusal,
    DidWorkflowRequest,
    EconMLDMLWorkflowRequest,
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


class AnalysisCheck(BaseModel):
    code: str
    status: Literal["pass", "warning", "fail", "skipped"]
    method: str | None
    execution_status: str | None
    applicable: bool = True


ANALYSIS_CHECK_CODES = (
    "routing",
    "execution_status",
    "adapter_identity",
    "result_integrity",
    "uncertainty_preserved",
    "assumptions_preserved",
    "diagnostics_preserved",
    "provenance_preserved",
    "estimand_preserved",
    "limitations_preserved",
    "abstention_preserved",
    "downstream_gating",
    "business_provenance",
    "prose_grounding",
    "object_privacy",
)


def analysis_check_applicability(case: AnalysisWorkflowCase) -> dict[str, bool]:
    evidence_checks = {
        "uncertainty_preserved",
        "assumptions_preserved",
        "provenance_preserved",
        "estimand_preserved",
        "limitations_preserved",
    }
    has_reference = case.expected_method in {"randomized_fixed_horizon", "did", "econml_dml"}
    return {code: has_reference or code not in evidence_checks for code in ANALYSIS_CHECK_CODES}


def check_analysis_response(
    case: AnalysisWorkflowCase, payload: dict[str, object]
) -> dict[str, AnalysisCheck]:
    from pydantic import ValidationError

    from apps.api.ask_service import AskResponse
    from packages.experiments.analysis.orchestration.rendering import render_analysis

    try:
        response = AskResponse.model_validate(payload)
        result = response.analysis
    except ValidationError:
        result = None
    verdicts: dict[str, bool | None] = {code: False for code in ANALYSIS_CHECK_CODES}
    if result is not None:
        expected = run_direct_reference(case)
        evidence = result.evidence
        verdicts.update(
            routing=result.method == case.expected_method,
            adapter_identity=result.method == case.expected_method,
            execution_status=result.status == case.expected_status,
            result_integrity=evidence == expected,
            abstention_preserved=(result.abstention is not None)
            == (case.expected_status in {"abstained", "invalid", "unavailable"}),
        )
        for code, field in (
            ("uncertainty_preserved", "test_result"),
            ("assumptions_preserved", "assumptions"),
            ("diagnostics_preserved", "diagnostics"),
            ("provenance_preserved", "provenance"),
            ("estimand_preserved", "estimand"),
            ("limitations_preserved", "evidence_limitations"),
        ):
            verdicts[code] = (
                getattr(evidence, field, None) == getattr(expected, field, None)
                if expected is not None
                else None
            )
        if expected is None:
            refusal = normalize_analysis_input(
                case.ask_payload["analysis"], experiment_id=str(case.ask_payload["experiment_id"])
            )
            verdicts["diagnostics_preserved"] = (
                isinstance(refusal, AnalysisRoutingRefusal)
                and result.diagnostics == refusal.diagnostics
            )
            verdicts["abstention_preserved"] = (
                isinstance(refusal, AnalysisRoutingRefusal)
                and result.abstention == refusal.abstention
            )
        impact = result.business_impact
        verdicts["downstream_gating"] = (
            impact is None or impact.status in {"abstained", "failed"}
            if result.status not in {"completed", "inconclusive"}
            else True
        )
        declaration = case.ask_payload.get("analysis")
        requested_business = (
            isinstance(declaration, dict) and declaration.get("business") is not None
        )
        verdicts["business_provenance"] = (
            _business_matches(case, impact) if requested_business else impact is None
        )
        verdicts["prose_grounding"] = response.answer == render_analysis(
            result
        ) and _public_narratives_match(case, response)
        # Typed public contracts reject foreign estimator objects and raw rows.
        verdicts["object_privacy"] = not _private_payload(result.model_dump(mode="json"))
    return {
        code: AnalysisCheck(
            code=code,
            status="skipped" if value is None else "pass" if value else "fail",
            method=result.method if result else case.expected_method,
            execution_status=result.status if result else None,
            applicable=value is not None,
        )
        for code, value in verdicts.items()
    }


def _private_payload(value: object) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {
                "rows",
                "scores",
                "assignments",
                "analysis_request",
                "execution_request",
            } and isinstance(child, list | dict):
                return True
            if _private_payload(child):
                return True
    elif isinstance(value, list):
        return any(_private_payload(item) for item in value)
    return False


def _business_matches(case, impact) -> bool:
    from packages.experiments.analysis.impact.service import BusinessImpactService
    from packages.experiments.analysis.orchestration.business import project_business
    from packages.experiments.analysis.orchestration.requests import BusinessInputRefusal

    request = normalize_analysis_input(
        case.ask_payload["analysis"], experiment_id=str(case.ask_payload["experiment_id"])
    )
    if impact is None:
        return False
    if isinstance(request.business, BusinessInputRefusal):
        return (
            impact.status == "abstained"
            and impact.abstention == request.business.abstention
            and impact.diagnostics == request.business.diagnostics
        )
    native = _run_native_reference(case)
    if native is None:
        return False
    expected = project_business(BusinessImpactService().analyze(native, request.business))
    return impact == expected


def _public_narratives_match(case, response) -> bool:
    from packages.agents.decision_agent import DecisionAgent
    from packages.agents.executive_summary_agent import ExecutiveSummaryAgent
    from packages.agents.human_approval_agent import HumanApprovalAgent
    from packages.agents.risk_assessment_agent import RiskAssessmentAgent
    from packages.agents.state import create_initial_state
    from packages.experiments.analysis.orchestration.integrity import artifact_citations

    plan = analysis_case_plan(case)
    state = create_initial_state(
        str(case.ask_payload["question"]), experiment_id=str(case.ask_payload["experiment_id"])
    )
    state.update(
        intent=plan.intent,
        required_agents=plan.required_agents,
        analysis_result=response.analysis,
        citations=artifact_citations(response.analysis, str(case.ask_payload["experiment_id"])),
    )
    for name, agent in (
        ("risk_assessment", RiskAssessmentAgent()),
        ("decision", DecisionAgent()),
        ("human_approval", HumanApprovalAgent()),
        ("executive_summary", ExecutiveSummaryAgent()),
    ):
        if name in plan.required_agents:
            state.update(agent.run(state))
    return (
        response.executive_summary == state["executive_summary"]
        and response.decision == state["decision"]
        and response.citations == state["citations"]
    )


def analysis_case_plan(case: AnalysisWorkflowCase):
    from packages.agents.planner import plan_analysis, plan_question

    request = normalize_analysis_input(
        case.ask_payload["analysis"], experiment_id=str(case.ask_payload["experiment_id"])
    )
    return plan_analysis(request, plan_question(str(case.ask_payload["question"])))


def safe_run_payload(run) -> dict[str, object]:
    """Serialize existing reports without fixture inputs or private workflow requests."""
    from pydantic_core import to_jsonable_python

    payload = asdict(run)
    for sample in payload["samples"]:
        case = sample["case"]
        analysis_case = case.pop("analysis_case", None)
        if analysis_case is not None:
            case["analysis_case_id"] = analysis_case.case_id
        state = sample.get("state")
        if state is not None:
            state.pop("analysis_request", None)
    return to_jsonable_python(payload)


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
    by_id = {case.case_id: case for case in cases}
    variants = []
    for name, method in (("unsupported", "unsupported_method"), ("ambiguous", None)):
        payload = deepcopy(by_id["randomized"].ask_payload)
        payload["analysis"]["method"] = method
        variants.append(
            AnalysisWorkflowCase(
                case_id=name,
                ask_payload=payload,
                expected_method=method,
                expected_status="abstained",
            )
        )
    payload = deepcopy(by_id["business"].ask_payload)
    payload["analysis"]["business"]["population"]["evidence"]["provenance"] = []
    variants.append(
        by_id["business"].model_copy(
            update={
                "case_id": "missing-business-provenance",
                "ask_payload": payload,
            }
        )
    )
    payload = deepcopy(by_id["randomized"].ask_payload)
    for row in payload["analysis_datasets"][0]["rows"]:
        row[2] = -row[2]
    variants.append(
        by_id["randomized"].model_copy(
            update={
                "case_id": "negative",
                "ask_payload": payload,
            }
        )
    )
    return cases + tuple(variants)


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
    native = _run_native_reference(case)
    return project_evidence(native) if native is not None else None


def _run_native_reference(case):
    request = normalize_analysis_input(
        case.ask_payload["analysis"], experiment_id=str(case.ask_payload["experiment_id"])
    )
    datasets = case.ask_payload.get("analysis_datasets")
    if not isinstance(datasets, list) or not datasets:
        return None
    dataset = AnalysisDatasetInput.model_validate(datasets[0])
    table = AnalysisTable(columns=dataset.columns, rows=dataset.rows)
    if isinstance(request, FixedHorizonWorkflowRequest):
        return RandomizedAnalysisService().analyze(
            request.execution, table, request.binding, provenance=dataset.provenance
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
        return DifferenceInDifferencesService().analyze(
            request.execution,
            AnalysisTable(columns=table.columns, rows=rows),
            provenance=dataset.provenance,
        )
    if isinstance(request, EconMLDMLWorkflowRequest) and case.optional_unavailable:
        from packages.experiments.analysis.causal.dml.models import DMLExecutionRequest
        from packages.experiments.analysis.causal.econml import EconMLDMLAdapter
        from packages.experiments.analysis.causal.econml.dependency import AdapterError
        from packages.experiments.analysis.causal.service import CausalIdentificationService

        identified = CausalIdentificationService().identify(request.analysis_request)
        execution = DMLExecutionRequest(
            identification_result=identified,
            binding=request.binding,
            configuration=request.configuration,
        )
        with patch(
            "packages.experiments.analysis.causal.econml.dependency.load_econml",
            side_effect=AdapterError(
                "OPTIONAL_DEPENDENCY_UNAVAILABLE", "Offline unavailable-runtime case"
            ),
        ):
            return EconMLDMLAdapter(configuration=request.adapter_configuration).analyze(
                execution, table, provenance=dataset.provenance
            )
    return None
