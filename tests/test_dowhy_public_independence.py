from __future__ import annotations

from packages.experiments.analysis.causal.dowhy.models import DoWhyAnalysisResult


def test_public_result_schema_contains_only_experimentos_owned_types() -> None:
    schema = DoWhyAnalysisResult.model_json_schema()
    rendered = str(schema)
    for third_party_name in (
        "CausalModel",
        "IdentifiedEstimand",
        "CausalEstimate",
        "CausalRefutation",
        "networkx",
        "dowhy.",
    ):
        assert third_party_name not in rendered
