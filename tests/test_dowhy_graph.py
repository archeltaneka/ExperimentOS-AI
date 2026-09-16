from __future__ import annotations

from packages.experiments.analysis.causal import (
    CausalDiagnosticCode,
    CausalGraph,
    CausalGraphEdge,
    CausalGraphNode,
    CausalIdentificationService,
    IdentificationStatus,
)
from tests.causal_identification_fixtures import provenance, request


def _graph(*, is_dag: bool = True, downstream_adjustment: bool = False) -> CausalGraph:
    edges = (
        CausalGraphEdge(cause="adjustment", effect="treatment"),
        CausalGraphEdge(cause="adjustment", effect="outcome"),
        CausalGraphEdge(cause="treatment", effect="outcome"),
    )
    if downstream_adjustment:
        edges = (
            CausalGraphEdge(cause="treatment", effect="adjustment"),
            CausalGraphEdge(cause="adjustment", effect="outcome"),
        )
    return CausalGraph(
        graph_version="1",
        is_dag=is_dag,
        nodes=(
            CausalGraphNode(node_id="outcome", variable_id="conversion"),
            CausalGraphNode(node_id="treatment", variable_id="treated"),
            CausalGraphNode(node_id="adjustment", variable_id="prior_orders"),
        ),
        edges=edges,
        source="user_supplied",
        provenance=provenance("graph"),
    )


def _identify(graph: CausalGraph):
    candidate = request()
    identification = candidate.identification.model_copy(update={"causal_graph": graph})
    return CausalIdentificationService().identify(
        candidate.model_copy(update={"identification": identification})
    )


def test_graph_node_observed_defaults_true() -> None:
    node = CausalGraphNode(node_id="x", variable_id="x")
    assert node.observed is True


def test_graph_declared_non_dag_is_invalid() -> None:
    result = _identify(_graph(is_dag=False))
    assert result.status is IdentificationStatus.INVALID
    assert CausalDiagnosticCode.GRAPH_NOT_DAG in {item.code for item in result.diagnostics}


def test_graph_rejects_adjustment_descendant_of_treatment() -> None:
    result = _identify(_graph(downstream_adjustment=True))
    assert result.status is IdentificationStatus.INVALID
    assert CausalDiagnosticCode.GRAPH_ADJUSTMENT_DESCENDANT in {
        item.code for item in result.diagnostics
    }


def test_graph_fingerprint_is_order_and_provenance_independent() -> None:
    from packages.experiments.analysis.causal.dowhy.graph import (
        canonical_graph_payload,
        graph_fingerprint,
    )

    left = _graph()
    right = left.model_copy(
        update={
            "nodes": tuple(reversed(left.nodes)),
            "edges": tuple(reversed(left.edges)),
            "provenance": provenance("other-source"),
        }
    )
    assert canonical_graph_payload(left) == canonical_graph_payload(right)
    assert graph_fingerprint(left) == graph_fingerprint(right)
    assert len(graph_fingerprint(left)) == 64
