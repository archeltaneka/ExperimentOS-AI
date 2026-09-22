"""Owned safe spans: providers receive allowlisted records only, never graph callbacks."""

from typing import TYPE_CHECKING

from packages.observability.base import BaseObservabilityProvider, BufferedSpan, BufferedSpanRecord

if TYPE_CHECKING:
    from .results import AnalysisResultEnvelope

SAFE_FIELDS = frozenset(
    {
        "method",
        "capability",
        "status",
        "analysis_id",
        "estimand",
        "diagnostic_codes",
        "assumption_codes",
        "duration_ms",
        "latency_ms",
        "row_count",
        "look_count",
        "fold_count",
        "estimator_version",
        "surface",
        "workflow",
        "workflow_mode",
        "execution_mode",
        "environment",
        "top_k",
        "experiment_id",
        "experimentos_trace_id",
        "workflow_execution_id",
        "request_id",
        "endpoint",
        "ask_mode",
        "timestamp",
        "citation_count",
        "required_agent_count",
        "intent",
        "required_agents",
        "approval_status",
        "decision_status",
        "summary_status",
        "trace_completeness",
        "workflow_success",
        "execution_status",
        "result_status",
        "error_count",
        "tool_call_count",
        "tool_failure_count",
        "required",
        "status_code",
        "success",
        "error_type",
        "native_status",
    }
)


def safe_fields(values: dict[str, object] | None) -> dict[str, object]:
    return {
        key: value
        for key, value in (values or {}).items()
        if key in SAFE_FIELDS
        and (
            value is None
            or isinstance(value, str | int | float | bool)
            or isinstance(value, list | tuple)
            and all(isinstance(v, str) for v in value)
        )
    }


class _SafeSpan(BufferedSpan):
    def add_metadata(self, metadata: dict[str, object]) -> None:
        super().add_metadata(safe_fields(metadata))

    def record_output(self, output: dict[str, object] | None) -> None:
        super().record_output(safe_fields(output))

    def record_error(
        self, error: BaseException | str, *, details: dict[str, object] | None = None
    ) -> None:
        super().record_error(
            "Analysis operation failed",
            details={
                **safe_fields(details),
                "error_type": type(error).__name__,
            },
        )

    def finish(self, *, outputs: dict[str, object] | None = None) -> None:
        super().finish(outputs=safe_fields(outputs))


class _SafeAnalysisProvider(BaseObservabilityProvider):
    def __init__(self, target: BaseObservabilityProvider) -> None:
        super().__init__(target.settings)
        self.target = target

    def start_root_span(
        self,
        name: str,
        *,
        trace_id: str | None = None,
        run_type: str = "chain",
        inputs: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
        tags: tuple[str, ...] | list[str] = (),
    ) -> BufferedSpan:
        span = super().start_root_span(
            name,
            trace_id=trace_id,
            run_type=run_type,
            inputs=safe_fields(inputs),
            metadata=safe_fields(metadata),
            tags=tags,
        )
        return _SafeSpan(self, span.record)

    def start_span(
        self,
        name: str,
        *,
        run_type: str = "chain",
        inputs: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
        tags: tuple[str, ...] | list[str] = (),
        parent: BufferedSpan | None = None,
    ) -> BufferedSpan:
        span = super().start_span(
            name,
            run_type=run_type,
            inputs=safe_fields(inputs),
            metadata=safe_fields(metadata),
            tags=tags,
            parent=parent,
        )
        return _SafeSpan(self, span.record)

    def build_langgraph_config(
        self, *, metadata: dict[str, object] | None = None, tags: tuple[str, ...] | list[str] = ()
    ) -> dict[str, object] | None:
        # Provider callbacks can serialize the entire graph input, including a
        # causal graph or sourced business declarations. Owned spans suffice.
        return None

    def _emit_root(self, record: BufferedSpanRecord) -> None:
        # Base _finish_root catches strict target transport/export exceptions.
        self.target._finish_root(record)

    def _finish_root(self, record: BufferedSpanRecord) -> None:
        try:
            super()._finish_root(record)
        except Exception:
            # Strict mode belongs to diagnostics, never to this analysis boundary.
            pass


def safe_analysis_provider(provider: BaseObservabilityProvider) -> BaseObservabilityProvider:
    return (
        provider if isinstance(provider, _SafeAnalysisProvider) else _SafeAnalysisProvider(provider)
    )


def analysis_metadata(envelope: "AnalysisResultEnvelope") -> dict[str, object]:
    from .requests import SUPPORTED_METHODS

    diagnostics = list(envelope.diagnostics)
    if envelope.evidence:
        diagnostics.extend(getattr(envelope.evidence, "diagnostics", ()))
    return {
        "method": envelope.method if envelope.method in SUPPORTED_METHODS else "unsupported",
        "capability": envelope.capability,
        "status": envelope.status,
        "analysis_id": envelope.analysis_id,
        "diagnostic_codes": [d.code for d in diagnostics],
    }
