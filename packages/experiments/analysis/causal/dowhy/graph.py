"""Deterministic private conversion of owned causal graphs."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..graph import CausalGraph


def canonical_graph_payload(graph: CausalGraph) -> bytes:
    """Return provenance-independent canonical graph semantics."""
    payload = {
        "fingerprint_schema": "experimentos-causal-graph-v1",
        "graph_version": graph.graph_version,
        "nodes": [
            {
                "node_id": node.node_id,
                "variable_id": node.variable_id,
                "observed": node.observed,
            }
            for node in sorted(graph.nodes, key=lambda item: (item.node_id, item.variable_id))
        ],
        "edges": [
            {"cause": edge.cause, "effect": edge.effect}
            for edge in sorted(graph.edges, key=lambda item: (item.cause, item.effect))
        ],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def graph_fingerprint(graph: CausalGraph) -> str:
    """Return the stable SHA-256 graph-semantics fingerprint."""
    return hashlib.sha256(canonical_graph_payload(graph)).hexdigest()


def to_networkx(graph: CausalGraph) -> Any:
    """Build a private NetworkX graph lazily so core imports remain independent."""
    import networkx as nx  # type: ignore[import-untyped]

    converted = nx.DiGraph()
    by_id = {node.node_id: node.variable_id for node in graph.nodes}
    converted.add_nodes_from(node.variable_id for node in graph.nodes)
    converted.add_edges_from((by_id[edge.cause], by_id[edge.effect]) for edge in graph.edges)
    return converted


__all__ = ["canonical_graph_payload", "graph_fingerprint"]
