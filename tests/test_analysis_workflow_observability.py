"""Safe analysis telemetry and strict-provider isolation without hosted services."""

import json

import pytest

from packages.agents.service import AgentWorkflowService
from packages.experiments.analysis.orchestration.datasets import RequestDatasetResolver
from packages.experiments.analysis.orchestration.service import AnalysisService
from packages.observability.base import BaseObservabilityProvider
from packages.observability.models import ObservabilitySettings
from tests.test_agent_analysis_workflow import ForbiddenAgent
from tests.test_analysis_service import fixed_case


class Recorder(BaseObservabilityProvider):
    def __init__(self):
        super().__init__(
            ObservabilitySettings(
                enabled=True, strict=True, trace_inputs=True, trace_outputs=True, sampling_rate=1.0
            )
        )
        self.records = []

    def _emit_root(self, record):
        self.records.append(record)


def flatten(record):
    return [
        {
            "name": record.name,
            "inputs": record.inputs,
            "outputs": record.outputs,
            "metadata": record.metadata,
            "error": record.error,
        },
        *(item for child in record.children for item in flatten(child)),
    ]


def test_analysis_spans_allowlist_metadata_even_with_content_tracing():
    request, dataset = fixed_case()
    provider = Recorder()
    result = AnalysisService(
        resolver=RequestDatasetResolver((dataset,)), observability_provider=provider
    ).analyze(request)
    captured = [item for root in provider.records for item in flatten(root)]
    assert any(item["name"] == "analysis" for item in captured)
    assert any(item["name"] == "estimator" for item in captured)
    assert any(item["metadata"].get("method") == result.method for item in captured)
    text = json.dumps(captured)
    for forbidden in (
        "treatment-0",
        "control-0",
        '"rows"',
        '"outcomes"',
        '"scores"',
        '"causal_graph"',
    ):
        assert forbidden not in text


@pytest.mark.parametrize(
    "operation",
    ["start_root_span", "start_span", "current_span", "build_langgraph_config", "_emit_root"],
)
def test_provider_failures_never_break_real_analysis_workflow(monkeypatch, operation):
    request, dataset = fixed_case()
    provider = Recorder()

    def explode(*args, **kwargs):
        raise RuntimeError("PRIVATE_PROVIDER_ERROR")

    monkeypatch.setattr(provider, operation, explode)
    state = AgentWorkflowService(
        retrieval_agent=ForbiddenAgent(), observability_provider=provider
    ).run("Analyze", analysis_request=request, analysis_datasets=(dataset,))
    assert state["analysis_result"].status == "completed"
    assert not state["errors"]
