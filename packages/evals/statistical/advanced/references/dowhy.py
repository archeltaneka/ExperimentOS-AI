from __future__ import annotations

import numpy as np

from packages.experiments.analysis import AnalysisTable
from packages.experiments.analysis.causal import (
    CausalGraph,
    CausalGraphEdge,
    CausalGraphNode,
    CausalIdentificationService,
)
from packages.experiments.analysis.causal.dowhy.models import (
    DoWhyConfig,
    DoWhyCovariateBinding,
    DoWhyDataBinding,
    DoWhyExecutionRequest,
)

from .causal import provenance
from .dml import dml_request


def graph(*, latent: bool = False) -> CausalGraph:
    nodes = [
        CausalGraphNode(node_id="T", variable_id="treated"),
        CausalGraphNode(node_id="Y", variable_id="outcome"),
    ]
    edges = [CausalGraphEdge(cause="T", effect="Y")]
    if latent:
        nodes.append(CausalGraphNode(node_id="U", variable_id="latent_u", observed=False))
        edges.extend(
            (
                CausalGraphEdge(cause="U", effect="T"),
                CausalGraphEdge(cause="U", effect="Y"),
            )
        )
    else:
        nodes.append(CausalGraphNode(node_id="X", variable_id="prior_orders"))
        edges.extend(
            (
                CausalGraphEdge(cause="X", effect="T"),
                CausalGraphEdge(cause="X", effect="Y"),
            )
        )
    return CausalGraph(
        graph_version="1",
        is_dag=True,
        nodes=tuple(nodes),
        edges=tuple(edges),
        source="user_supplied",
        provenance=provenance("dowhy-graph"),
    )


def execution(*, latent: bool = False, run_estimation: bool = False) -> DoWhyExecutionRequest:
    request = dml_request()
    source = request.identification
    if latent:
        from packages.experiments.analysis.causal import MeasurementTiming, VariableRole

        from .causal import variable

        variables = (
            *source.variables,
            variable("latent_u", VariableRole.UNKNOWN, timing=MeasurementTiming.TIME_INVARIANT),
        )
        source = source.model_copy(update={"variables": variables, "adjustment_set": None})
    source = source.model_copy(update={"causal_graph": graph(latent=latent)})
    identified = CausalIdentificationService().identify(
        request.model_copy(update={"identification": source})
    )
    return DoWhyExecutionRequest(
        identification_result=identified,
        binding=DoWhyDataBinding(
            treatment_column="treated",
            outcome_column="outcome",
            covariates=(DoWhyCovariateBinding(variable_id="prior_orders", column="prior_orders"),)
            if not latent
            else (),
        ),
        configuration=DoWhyConfig(run_estimation=run_estimation),
    )


def known_effect_table() -> AnalysisTable:
    rng = np.random.default_rng(105)
    x = rng.normal(size=600)
    probability = 1.0 / (1.0 + np.exp(-0.8 * x))
    treated = rng.binomial(1, probability)
    outcome = 2.0 * treated + 1.5 * x + rng.normal(scale=0.5, size=600)
    return AnalysisTable.from_records(
        tuple(
            {"treated": int(t), "outcome": float(y), "prior_orders": float(c)}
            for t, y, c in zip(treated, outcome, x, strict=True)
        )
    )
