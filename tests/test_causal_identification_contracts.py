from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from packages.experiments.analysis.causal import (
    AdjustmentPurpose,
    AdjustmentSet,
    AdjustmentValidationStatus,
    CausalEstimand,
    CausalEstimandKind,
    CausalGraph,
    CausalGraphEdge,
    CausalGraphNode,
    EffectScale,
    MeasurementTiming,
    TargetPopulation,
    TargetPopulationKind,
    TreatmentContrast,
    VariableRole,
)
from tests.causal_identification_fixtures import (
    adjustment_set,
    contrast,
    estimand,
    population,
    provenance,
    variable,
)


def test_observational_estimand_vocabulary_is_stable_and_distinct() -> None:
    assert [item.value for item in CausalEstimandKind] == ["ate", "att", "did_att", "cate"]
    assert estimand(CausalEstimandKind.ATE).target_population.kind is TargetPopulationKind.FULL
    assert estimand(CausalEstimandKind.ATT).target_population.kind is TargetPopulationKind.TREATED
    assert (
        estimand(CausalEstimandKind.DID_ATT).target_population.kind
        is TargetPopulationKind.TREATED
    )
    assert estimand(CausalEstimandKind.CATE).effect_modifiers == ("country",)


def test_estimand_rejects_vague_or_contradictory_shapes() -> None:
    common = {
        "treatment_contrast": contrast(),
        "target_population": TargetPopulation(
            kind=TargetPopulationKind.FULL,
            population=population(),
        ),
        "outcome_variable": "conversion",
        "effect_scale": EffectScale.RISK_DIFFERENCE,
        "provenance": provenance("estimand"),
    }
    with pytest.raises(ValidationError, match="treated target population"):
        CausalEstimand(estimand_type=CausalEstimandKind.ATT, **common)
    with pytest.raises(ValidationError, match="effect modifier"):
        CausalEstimand(
            estimand_type=CausalEstimandKind.CATE,
            target_population=TargetPopulation(
                kind=TargetPopulationKind.CONDITIONED,
                population=population(),
            ),
            conditioning_definition="Country-specific effect.",
            **{key: value for key, value in common.items() if key != "target_population"},
        )
    with pytest.raises(ValidationError, match="conditioning"):
        CausalEstimand(
            estimand_type=CausalEstimandKind.ATE,
            conditioning_definition="Not valid for an ATE.",
            **common,
        )


def test_treatment_contrast_rejects_equal_values() -> None:
    with pytest.raises(ValidationError, match="must differ"):
        TreatmentContrast(
            treatment_variable="treated",
            treated_value=1,
            control_value=1,
            exposure_definition="Exposure.",
            provenance=provenance("contrast"),
        )


def test_variable_roles_and_adjustment_set_serialize_in_canonical_order() -> None:
    item = variable(
        "country",
        VariableRole.EFFECT_MODIFIER,
        timing=MeasurementTiming.PRE_TREATMENT,
        additional_roles=(VariableRole.ADJUSTMENT,),
    )
    adjustment = AdjustmentSet(
        variable_ids=("z_score", "age"),
        purpose=AdjustmentPurpose.CONFOUNDING_CONTROL,
        estimand_type=CausalEstimandKind.ATE,
        source="user_supplied",
        validation_status=AdjustmentValidationStatus.UNVALIDATED,
        diagnostics=(),
        provenance=provenance("adjustment"),
    )

    assert item.roles == (VariableRole.ADJUSTMENT, VariableRole.EFFECT_MODIFIER)
    assert adjustment.variable_ids == ("age", "z_score")


def test_adjustment_set_preserves_duplicates_for_blocking_validation() -> None:
    duplicate = adjustment_set().model_copy(
        update={"variable_ids": ("prior_orders", "prior_orders")}
    )
    assert duplicate.variable_ids == ("prior_orders", "prior_orders")


def test_causal_graph_canonicalizes_nodes_and_edges() -> None:
    graph = CausalGraph(
        graph_version="1",
        is_dag=True,
        nodes=(
            CausalGraphNode(node_id="outcome", variable_id="conversion"),
            CausalGraphNode(node_id="treatment", variable_id="treated"),
            CausalGraphNode(node_id="covariate", variable_id="prior_orders"),
        ),
        edges=(
            CausalGraphEdge(cause="treatment", effect="outcome"),
            CausalGraphEdge(cause="covariate", effect="treatment"),
            CausalGraphEdge(cause="covariate", effect="outcome"),
        ),
        source="user_supplied",
        provenance=provenance("graph"),
    )

    assert tuple(node.node_id for node in graph.nodes) == ("covariate", "outcome", "treatment")
    assert tuple((edge.cause, edge.effect) for edge in graph.edges) == (
        ("covariate", "outcome"),
        ("covariate", "treatment"),
        ("treatment", "outcome"),
    )


def test_variable_timing_requires_timezone_aware_references() -> None:
    payload = variable(
        "prior_orders",
        VariableRole.ADJUSTMENT,
        timing=MeasurementTiming.PRE_TREATMENT,
    ).model_dump(mode="python")
    payload["timing"]["treatment_start"] = datetime(2026, 7, 10)
    with pytest.raises(ValidationError, match="timezone-aware"):
        type(variable(
            "prior_orders",
            VariableRole.ADJUSTMENT,
            timing=MeasurementTiming.PRE_TREATMENT,
        )).model_validate(payload)


def test_fixture_timestamps_are_timezone_aware() -> None:
    assert datetime(2026, 7, 10, tzinfo=UTC).utcoffset() is not None
