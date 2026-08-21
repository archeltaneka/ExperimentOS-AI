"""Small repository-owned directed causal graph representation."""

from __future__ import annotations

from pydantic import field_validator

from ..base import ContractModel, NonEmptyStr
from ..provenance import ProvenanceRecords


class CausalGraphNode(ContractModel):
    """Owned graph-node identity mapped to one declared request variable."""

    node_id: NonEmptyStr
    variable_id: NonEmptyStr


class CausalGraphEdge(ContractModel):
    """A directed cause-to-effect edge between owned graph nodes."""

    cause: NonEmptyStr
    effect: NonEmptyStr


class CausalGraph(ContractModel):
    """Versioned directed graph without third-party graph objects."""

    graph_version: NonEmptyStr
    is_dag: bool
    nodes: tuple[CausalGraphNode, ...]
    edges: tuple[CausalGraphEdge, ...]
    source: NonEmptyStr
    provenance: ProvenanceRecords

    @field_validator("nodes")
    @classmethod
    def canonicalize_nodes(
        cls,
        value: tuple[CausalGraphNode, ...],
    ) -> tuple[CausalGraphNode, ...]:
        return tuple(sorted(value, key=lambda node: (node.node_id, node.variable_id)))

    @field_validator("edges")
    @classmethod
    def canonicalize_edges(
        cls,
        value: tuple[CausalGraphEdge, ...],
    ) -> tuple[CausalGraphEdge, ...]:
        return tuple(sorted(value, key=lambda edge: (edge.cause, edge.effect)))


__all__ = ["CausalGraph", "CausalGraphEdge", "CausalGraphNode"]
