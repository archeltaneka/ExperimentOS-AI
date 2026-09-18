"""Privacy-safe best-effort observability for DoWhy adapter operations."""

from __future__ import annotations

from packages.observability.base import BaseObservabilityProvider

from ..advanced.conformance import execution_metadata
from .models import DoWhyAnalysisResult


def observe_dowhy_result(
    provider: BaseObservabilityProvider, result: DoWhyAnalysisResult, duration_ms: float
) -> None:
    graph = result.execution_request.identification_result.causal_graph
    operation = (
        "refutation"
        if result.refutations
        else (
            "estimation"
            if result.execution_request.configuration.run_estimation
            else "identification"
        )
    )
    try:
        span = provider.start_root_span(
            "dowhy_causal_adapter",
            run_type="chain",
            metadata={
                **execution_metadata(result, "experimentos_dowhy"),
                "graph_fingerprint": result.identification.graph_fingerprint,
                "adapter": "dowhy",
                "operation": operation,
                "estimand": "ate",
                "identification_status": result.identification.status.value,
                "status": result.status.value,
                "graph_node_count": len(graph.nodes) if graph is not None else 0,
                "graph_edge_count": len(graph.edges) if graph is not None else 0,
                "diagnostic_codes": tuple(item.code for item in result.diagnostics),
                "duration_ms": duration_ms,
            },
        )
        span.finish(outputs={"status": result.status.value})
    except Exception:
        pass
