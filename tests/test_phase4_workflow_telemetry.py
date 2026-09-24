"""Linked real-request traces and recursively safe evidence."""

from dataclasses import replace

import pytest

from packages.evals.agent_analysis_cases import load_analysis_workflow_cases
from packages.evals.statistical.telemetry import _RecordingProvider


def test_real_request_trace_linkage_and_broken_parent_detection():
    from packages.evals.statistical.workflow.harness import evaluate_workflow_case
    from packages.evals.statistical.workflow.telemetry import check_trace_linkage

    provider = _RecordingProvider()
    case = next(c for c in load_analysis_workflow_cases() if c.case_id == "business")
    result = evaluate_workflow_case(case, observability_provider=provider)
    assert result.checks["trace_linkage"].status == "pass"
    assert result.trace_summary
    assert not check_trace_linkage(
        tuple(provider.records), method=case.expected_method, business_requested=True
    )
    root = provider.records[0]
    corrupt = replace(root, children=[replace(root.children[0], parent=None)])
    assert check_trace_linkage((corrupt,), method=case.expected_method, business_requested=True)


@pytest.mark.parametrize(
    "payload",
    [
        {"events": [{"attributes": {"method": "PRIVATE_ROW_SENTINEL"}}]},
        {"metrics": [{"labels": {"safe": "prefix PRIVATE_ROW_SENTINEL suffix"}}]},
        {"error": {"message": "PRIVATE_ROW_SENTINEL"}},
        {"nested": {"rows": [[1, 2, 3]]}},
        {"safe": "Bearer secret-token"},
    ],
)
def test_recursive_privacy_returns_only_safe_codes(payload):
    from packages.evals.statistical.workflow.telemetry import privacy_violations

    violations = privacy_violations(payload, sentinels=("PRIVATE_ROW_SENTINEL",))
    assert violations
    assert "PRIVATE_ROW_SENTINEL" not in repr(violations)


@pytest.mark.parametrize(
    "operation",
    ["start_root_span", "start_span", "current_span", "build_langgraph_config", "_emit_root"],
)
def test_provider_failure_cannot_change_api_evidence(monkeypatch, operation):
    from packages.evals.statistical.workflow.harness import evaluate_workflow_case

    case = next(c for c in load_analysis_workflow_cases() if c.case_id == "dml-success")
    provider = _RecordingProvider()

    def fail(*args, **kwargs):
        raise RuntimeError("PRIVATE_PROVIDER_SENTINEL")

    monkeypatch.setattr(provider, operation, fail)
    result = evaluate_workflow_case(case, observability_provider=provider)
    assert result.execution_status == "completed"
    assert result.call_counts["dml"] == 1
    assert result.checks["result_integrity"].status == "pass"
    assert "PRIVATE_PROVIDER_SENTINEL" not in result.model_dump_json()
    if operation == "_emit_root":
        assert result.provider_failure_count > 0


def test_allowed_telemetry_key_does_not_allow_arbitrary_method_value():
    from packages.experiments.analysis.orchestration.observability import safe_fields

    assert "method" not in safe_fields({"method": "PRIVATE_ROW_SENTINEL"})


def test_real_api_exports_linked_otel_spans_in_memory():
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from packages.evals.statistical.workflow.harness import evaluate_workflow_case
    from packages.observability.models import OpenTelemetrySettings
    from packages.observability.opentelemetry import OpenTelemetryObservabilityProvider

    exporter = InMemorySpanExporter()
    provider = OpenTelemetryObservabilityProvider(
        settings=OpenTelemetrySettings(
            enabled=True,
            exporter_type="in_memory",
            trace_enabled=True,
            metrics_enabled=False,
            instrument_fastapi=False,
        ),
        span_exporter=exporter,
    )
    try:
        case = next(c for c in load_analysis_workflow_cases() if c.case_id == "dml-success")
        result = evaluate_workflow_case(case, observability_provider=provider)
        provider.force_flush()
        assert result.execution_status == "completed"
        spans = exporter.get_finished_spans()
        by_name = {span.name: span for span in spans}
        for child, parent in (
            ("workflow", "ask_request"),
            ("analysis", "workflow"),
            ("estimator", "analysis"),
            ("response_serialization", "ask_request"),
        ):
            assert by_name[child].parent.span_id == by_name[parent].context.span_id
            assert by_name[child].context.trace_id == by_name[parent].context.trace_id
    finally:
        provider.shutdown()
