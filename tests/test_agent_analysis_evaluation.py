import json

import pytest

from packages.evals.agent_dataset import load_agent_evaluation_dataset
from packages.evals.agent_e2e import AgentE2EEvaluator, build_default_agent_e2e_cases
from packages.evals.agent_e2e_report import agent_e2e_report_to_json
from packages.evals.agent_evaluator import (
    AgentWorkflowEvaluator,
    build_default_agent_workflow_service,
)
from packages.evals.agent_report import agent_evaluation_report_to_json


def test_default_dataset_path_and_full_payload_version_are_stable(monkeypatch):
    from packages.evals.agent_dataset import (
        DEFAULT_AGENT_DATASET_PATH,
        build_agent_dataset_manifest,
    )

    relative = load_agent_evaluation_dataset()
    absolute = load_agent_evaluation_dataset(DEFAULT_AGENT_DATASET_PATH.resolve())
    assert relative == absolute
    first = build_agent_dataset_manifest(DEFAULT_AGENT_DATASET_PATH, relative)
    from dataclasses import replace

    altered = list(relative)
    original = altered[-1]
    altered[-1] = replace(
        original,
        analysis_case=original.analysis_case.model_copy(
            update={"presenter_candidate": "different fixture"}
        ),
    )
    second = build_agent_dataset_manifest(DEFAULT_AGENT_DATASET_PATH, altered)
    assert first.version != second.version


@pytest.mark.parametrize(
    "case_id,mutation",
    [
        ("business", "business"),
        ("optional_unavailable", "evidence"),
        ("randomized", "summary"),
        ("randomized", "decision"),
        ("unsupported", "diagnostics"),
    ],
)
def test_required_analysis_outputs_and_all_prose_are_checked(case_id, mutation):
    import asyncio

    from apps.api.ask_service import AgentWorkflowAskService, AskRequest
    from packages.evals.agent_analysis_cases import (
        build_analysis_case_service,
        check_analysis_response,
        load_analysis_workflow_cases,
    )
    from packages.experiments.analysis.orchestration.rendering import render_analysis
    from packages.experiments.analysis.orchestration.results import AnalysisResultEnvelope

    case = next(c for c in load_analysis_workflow_cases() if c.case_id == case_id)
    response = asyncio.run(
        AgentWorkflowAskService(build_analysis_case_service(case)).answer(
            AskRequest.model_validate(case.ask_payload)
        )
    )
    payload = response.model_dump(mode="json")
    if mutation in {"business", "evidence"}:
        payload["analysis"]["business_impact" if mutation == "business" else "evidence"] = None
        payload["analysis"]["evidence_fingerprint"] = ""
        result = AnalysisResultEnvelope.model_validate(payload["analysis"])
        payload["analysis"] = result.model_dump(mode="json")
        payload["answer"] = render_analysis(result)
        payload["executive_summary"]["summary"] = payload["answer"]
    elif mutation == "diagnostics":
        payload["analysis"]["diagnostics"] = []
    elif mutation == "summary":
        payload["executive_summary"]["business_impact_summary"] = "$99999 invented revenue"
    else:
        payload["decision"]["rationale"] = "p-value = 0.000001"
    checks = check_analysis_response(case, payload)
    assert any(c.status == "fail" for c in checks.values())


def test_evaluation_covers_refused_and_negative_requests():
    from packages.evals.agent_analysis_cases import load_analysis_workflow_cases

    ids = {case.case_id for case in load_analysis_workflow_cases()}
    assert {"unsupported", "ambiguous", "missing-business-provenance", "negative"} <= ids


@pytest.mark.parametrize("field", ["test_result", "provenance", "assumptions"])
def test_corrupted_public_evidence_is_blocking(field):
    import asyncio

    from apps.api.ask_service import AgentWorkflowAskService, AskRequest
    from packages.evals.agent_analysis_cases import (
        build_analysis_case_service,
        check_analysis_response,
        load_analysis_workflow_cases,
    )

    case = next(c for c in load_analysis_workflow_cases() if c.case_id == "did")
    response = asyncio.run(
        AgentWorkflowAskService(build_analysis_case_service(case)).answer(
            AskRequest.model_validate(case.ask_payload)
        )
    )
    payload = response.model_dump(mode="json")
    payload["analysis"]["evidence"][field] = None if field == "test_result" else []
    payload["analysis"]["evidence_fingerprint"] = ""
    checks = check_analysis_response(case, payload)
    assert checks["result_integrity"].status == "fail"


def test_existing_agent_evaluator_includes_real_analysis_and_safe_reports():
    run = AgentWorkflowEvaluator(
        workflow_service=build_default_agent_workflow_service(),
        cases=load_agent_evaluation_dataset(),
    ).evaluate()
    samples = [sample for sample in run.samples if sample.analysis_checks]
    assert len(samples) >= 6
    assert all(
        all(c.status in {"pass", "skipped"} for c in s.analysis_checks.values()) for s in samples
    )
    report = agent_evaluation_report_to_json(run)
    assert '"analysis_request":' not in report
    assert '"analysis_datasets"' not in report
    assert '"analysis_checks"' in report


def test_existing_e2e_evaluator_includes_real_analysis_and_safe_reports():
    run = AgentE2EEvaluator(cases=build_default_agent_e2e_cases()).evaluate()
    samples = [sample for sample in run.samples if sample.analysis_checks]
    assert len(samples) >= 6
    assert all(s.passed for s in samples)
    payload = json.loads(agent_e2e_report_to_json(run))
    assert all("ask_payload" not in sample["case"] for sample in payload["samples"])


def test_factuality_uses_structured_analysis_artifacts():
    from packages.evals.factuality.deterministic import evaluate_case
    from packages.evals.factuality.runner import build_agent_workflow_cases

    run = AgentWorkflowEvaluator(
        workflow_service=build_default_agent_workflow_service(),
        cases=load_agent_evaluation_dataset(),
    ).evaluate()
    cases = [
        case
        for case in build_agent_workflow_cases(run, dataset_identifier="offline")
        if case.case_id.startswith("analysis-")
    ]
    assert cases
    assert all(case.analysis is not None for case in cases)
    assert all(not evaluate_case(case).failed_findings for case in cases)
