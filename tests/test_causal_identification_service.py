from __future__ import annotations

import pytest

from packages.experiments.analysis.causal import (
    CausalAssumptionCode,
    CausalAssumptionStatus,
    CausalDiagnosticCode,
    CausalEstimandKind,
    CausalGraph,
    CausalGraphEdge,
    CausalGraphNode,
    CausalIdentificationService,
    IdentificationStatus,
    MeasurementTiming,
    ObservationalDesignType,
    VariableRole,
)
from tests.causal_identification_fixtures import (
    adjustment_set,
    assumptions,
    provenance,
    request,
    time_semantics,
    variable,
    variables,
)


def diagnostic_codes(result: object) -> set[CausalDiagnosticCode]:
    return {diagnostic.code for diagnostic in result.diagnostics}  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("design_type", "estimand_kind"),
    (
        (ObservationalDesignType.GENERIC, CausalEstimandKind.ATE),
        (ObservationalDesignType.PROPENSITY_WEIGHTING, CausalEstimandKind.ATT),
        (ObservationalDesignType.DID, CausalEstimandKind.DID_ATT),
        (ObservationalDesignType.HETEROGENEOUS_EFFECTS, CausalEstimandKind.CATE),
    ),
)
def test_valid_observational_shapes_are_identified(
    design_type: ObservationalDesignType,
    estimand_kind: CausalEstimandKind,
) -> None:
    result = CausalIdentificationService().identify(
        request(design_type=design_type, estimand_kind=estimand_kind)
    )
    assert result.status is IdentificationStatus.IDENTIFIED
    assert result.abstention_reason is None
    assert result.estimand is not None
    assert result.estimand.estimand_type is estimand_kind


def test_missing_estimand_is_insufficient_evidence() -> None:
    candidate = request()
    candidate = candidate.model_copy(
        update={"identification": candidate.identification.model_copy(update={"estimand": None})}
    )
    result = CausalIdentificationService().identify(candidate)
    assert result.status is IdentificationStatus.INSUFFICIENT_EVIDENCE
    assert CausalDiagnosticCode.MISSING_ESTIMAND in diagnostic_codes(result)


def test_missing_adjustment_information_is_insufficient_evidence() -> None:
    candidate = request()
    candidate = candidate.model_copy(
        update={
            "identification": candidate.identification.model_copy(
                update={"adjustment_set": None, "causal_graph": None}
            )
        }
    )
    result = CausalIdentificationService().identify(candidate)
    assert result.status is IdentificationStatus.INSUFFICIENT_EVIDENCE
    assert CausalDiagnosticCode.MISSING_ADJUSTMENT_INFORMATION in diagnostic_codes(result)


def test_missing_required_assumptions_is_insufficient_evidence() -> None:
    candidate = request(declared_assumptions=())
    result = CausalIdentificationService().identify(candidate)
    assert result.status is IdentificationStatus.INSUFFICIENT_EVIDENCE
    assert CausalDiagnosticCode.MISSING_REQUIRED_ASSUMPTION in diagnostic_codes(result)


@pytest.mark.parametrize(
    ("timing", "expected_code"),
    (
        (MeasurementTiming.POST_TREATMENT, CausalDiagnosticCode.POST_TREATMENT_ADJUSTMENT),
        (MeasurementTiming.UNKNOWN, CausalDiagnosticCode.UNKNOWN_COVARIATE_TIMING),
    ),
)
def test_invalid_adjustment_timing_blocks_identification(
    timing: MeasurementTiming,
    expected_code: CausalDiagnosticCode,
) -> None:
    declared = variables(adjustment_timing=timing)
    result = CausalIdentificationService().identify(request(declared_variables=declared))
    assert result.status is IdentificationStatus.INVALID
    assert expected_code in diagnostic_codes(result)


@pytest.mark.parametrize(
    ("role", "expected_code"),
    (
        (VariableRole.TREATMENT, CausalDiagnosticCode.TREATMENT_LEAKAGE),
        (VariableRole.OUTCOME, CausalDiagnosticCode.OUTCOME_LEAKAGE),
        (VariableRole.IDENTIFIER, CausalDiagnosticCode.IDENTIFIER_MISUSE),
    ),
)
def test_forbidden_adjustment_roles_are_invalid(
    role: VariableRole,
    expected_code: CausalDiagnosticCode,
) -> None:
    declared = tuple(
        variable(
            item.variable_id,
            role if item.variable_id == "prior_orders" else item.roles[0],
            timing=item.timing.measurement_timing,
        )
        for item in variables()
    )
    result = CausalIdentificationService().identify(request(declared_variables=declared))
    assert result.status is IdentificationStatus.INVALID
    assert expected_code in diagnostic_codes(result)


def test_duplicate_adjustment_and_modifier_variables_are_invalid() -> None:
    candidate = request(estimand_kind=CausalEstimandKind.CATE)
    identification = candidate.identification.model_copy(
        update={
            "adjustment_set": candidate.identification.adjustment_set.model_copy(
                update={"variable_ids": ("prior_orders", "prior_orders")}
            ),
            "effect_modifiers": ("country", "country"),
        }
    )
    result = CausalIdentificationService().identify(
        candidate.model_copy(update={"identification": identification})
    )
    assert result.status is IdentificationStatus.INVALID
    assert CausalDiagnosticCode.DUPLICATE_ADJUSTMENT_VARIABLE in diagnostic_codes(result)
    assert CausalDiagnosticCode.DUPLICATE_EFFECT_MODIFIER in diagnostic_codes(result)


def test_did_requires_ordered_periods_and_design_assumptions() -> None:
    candidate = request(
        design_type=ObservationalDesignType.DID,
        estimand_kind=CausalEstimandKind.DID_ATT,
    )
    missing_period = candidate.identification.time.model_copy(update={"pre_period": None})
    missing_assumptions = tuple(
        item
        for item in assumptions(did=True)
        if item.code
        not in {CausalAssumptionCode.PARALLEL_TRENDS, CausalAssumptionCode.NO_ANTICIPATION}
    )
    identification = candidate.identification.model_copy(
        update={"time": missing_period, "assumptions": missing_assumptions}
    )
    result = CausalIdentificationService().identify(
        candidate.model_copy(update={"identification": identification})
    )
    assert result.status is IdentificationStatus.INVALID
    assert CausalDiagnosticCode.MISSING_PRE_PERIOD in diagnostic_codes(result)
    assert CausalDiagnosticCode.MISSING_REQUIRED_ASSUMPTION in diagnostic_codes(result)


def test_post_treatment_effect_modifier_is_invalid() -> None:
    declared = variables(modifier_timing=MeasurementTiming.POST_TREATMENT)
    result = CausalIdentificationService().identify(
        request(
            design_type=ObservationalDesignType.HETEROGENEOUS_EFFECTS,
            estimand_kind=CausalEstimandKind.CATE,
            declared_variables=declared,
        )
    )
    assert result.status is IdentificationStatus.INVALID
    assert CausalDiagnosticCode.POST_TREATMENT_EFFECT_MODIFIER in diagnostic_codes(result)


@pytest.mark.parametrize(
    ("edges", "code"),
    (
        (
            (CausalGraphEdge(cause="treatment", effect="treatment"),),
            CausalDiagnosticCode.GRAPH_SELF_LOOP,
        ),
        (
            (
                CausalGraphEdge(cause="treatment", effect="outcome"),
                CausalGraphEdge(cause="treatment", effect="outcome"),
            ),
            CausalDiagnosticCode.GRAPH_DUPLICATE_EDGE,
        ),
        (
            (
                CausalGraphEdge(cause="treatment", effect="outcome"),
                CausalGraphEdge(cause="outcome", effect="treatment"),
            ),
            CausalDiagnosticCode.GRAPH_CYCLE,
        ),
        (
            (CausalGraphEdge(cause="unknown", effect="outcome"),),
            CausalDiagnosticCode.GRAPH_UNKNOWN_NODE,
        ),
    ),
)
def test_malformed_graph_is_invalid(
    edges: tuple[CausalGraphEdge, ...],
    code: CausalDiagnosticCode,
) -> None:
    candidate = request()
    graph = CausalGraph(
        graph_version="1",
        is_dag=True,
        nodes=(
            CausalGraphNode(node_id="treatment", variable_id="treated"),
            CausalGraphNode(node_id="outcome", variable_id="conversion"),
            CausalGraphNode(node_id="adjustment", variable_id="prior_orders"),
        ),
        edges=edges,
        source="user_supplied",
        provenance=provenance("graph"),
    )
    identification = candidate.identification.model_copy(update={"causal_graph": graph})
    result = CausalIdentificationService().identify(
        candidate.model_copy(update={"identification": identification})
    )
    assert result.status is IdentificationStatus.INVALID
    assert code in diagnostic_codes(result)


def test_unverified_required_assumption_is_partially_identified() -> None:
    declared = tuple(
        item.model_copy(update={"status": CausalAssumptionStatus.UNVERIFIED})
        if item.code is CausalAssumptionCode.POSITIVITY
        else item
        for item in assumptions()
    )
    result = CausalIdentificationService().identify(request(declared_assumptions=declared))
    assert result.status is IdentificationStatus.PARTIALLY_IDENTIFIED
    assert result.abstention_reason is not None


def test_custom_design_is_unsupported() -> None:
    result = CausalIdentificationService().identify(
        request(design_type=ObservationalDesignType.CUSTOM)
    )
    assert result.status is IdentificationStatus.UNSUPPORTED
    assert CausalDiagnosticCode.UNSUPPORTED_DESIGN in diagnostic_codes(result)


def test_identified_result_retains_expected_evidence_limitations() -> None:
    result = CausalIdentificationService().identify(request())
    codes = {limitation.code.value for limitation in result.evidence_limitations}
    assert "unmeasured_confounding_possible" in codes
    assert "overlap_not_evaluated" in codes
    assert "no_sensitivity_analysis" in codes
    assert "adjustment_set_not_graph_validated" in codes


def test_time_invariant_adjustment_is_valid() -> None:
    declared = variables(adjustment_timing=MeasurementTiming.TIME_INVARIANT)
    result = CausalIdentificationService().identify(request(declared_variables=declared))
    assert result.status is IdentificationStatus.IDENTIFIED


def test_adjustment_variable_missing_from_request_is_invalid() -> None:
    candidate = request(
        adjustment=adjustment_set().model_copy(update={"variable_ids": ("undeclared",)})
    )
    result = CausalIdentificationService().identify(candidate)
    assert result.status is IdentificationStatus.INVALID
    assert CausalDiagnosticCode.MISSING_ADJUSTMENT_VARIABLE in diagnostic_codes(result)


def test_contradictory_measurement_period_is_invalid() -> None:
    declared = list(variables())
    adjustment = next(item for item in declared if item.variable_id == "prior_orders")
    declared[declared.index(adjustment)] = adjustment.model_copy(
        update={
            "timing": adjustment.timing.model_copy(
                update={"reference_period": time_semantics(did=True).post_period}
            )
        }
    )
    result = CausalIdentificationService().identify(request(declared_variables=tuple(declared)))
    assert result.status is IdentificationStatus.INVALID
    assert CausalDiagnosticCode.REVERSED_TIMING in diagnostic_codes(result)


def test_did_missing_post_period_is_invalid() -> None:
    candidate = request(
        design_type=ObservationalDesignType.DID,
        estimand_kind=CausalEstimandKind.DID_ATT,
    )
    identification = candidate.identification.model_copy(
        update={"time": candidate.identification.time.model_copy(update={"post_period": None})}
    )
    result = CausalIdentificationService().identify(
        candidate.model_copy(update={"identification": identification})
    )
    assert result.status is IdentificationStatus.INVALID
    assert CausalDiagnosticCode.MISSING_POST_PERIOD in diagnostic_codes(result)


def test_did_reversed_periods_are_invalid() -> None:
    candidate = request(
        design_type=ObservationalDesignType.DID,
        estimand_kind=CausalEstimandKind.DID_ATT,
    )
    reversed_time = candidate.identification.time.model_copy(
        update={
            "pre_period": time_semantics(did=True).post_period,
            "post_period": time_semantics(did=True).pre_period,
        }
    )
    identification = candidate.identification.model_copy(update={"time": reversed_time})
    result = CausalIdentificationService().identify(
        candidate.model_copy(update={"identification": identification})
    )
    assert result.status is IdentificationStatus.INVALID
    assert CausalDiagnosticCode.REVERSED_TIMING in diagnostic_codes(result)


def test_violated_required_assumption_is_invalid() -> None:
    declared = tuple(
        item.model_copy(update={"status": CausalAssumptionStatus.VIOLATED})
        if item.code is CausalAssumptionCode.CONSISTENCY
        else item
        for item in assumptions()
    )
    result = CausalIdentificationService().identify(request(declared_assumptions=declared))
    assert result.status is IdentificationStatus.INVALID
    assert CausalDiagnosticCode.VIOLATED_ASSUMPTION in diagnostic_codes(result)


def test_graph_unknown_variable_and_duplicate_node_are_invalid() -> None:
    candidate = request()
    graph = CausalGraph(
        graph_version="1",
        is_dag=True,
        nodes=(
            CausalGraphNode(node_id="unknown", variable_id="not_declared"),
            CausalGraphNode(node_id="unknown", variable_id="treated"),
        ),
        edges=(),
        source="user_supplied",
        provenance=provenance("graph"),
    )
    identification = candidate.identification.model_copy(update={"causal_graph": graph})
    result = CausalIdentificationService().identify(
        candidate.model_copy(update={"identification": identification})
    )
    assert result.status is IdentificationStatus.INVALID
    assert CausalDiagnosticCode.GRAPH_DUPLICATE_NODE in diagnostic_codes(result)
    assert CausalDiagnosticCode.GRAPH_UNKNOWN_VARIABLE in diagnostic_codes(result)
    assert {item.code.value for item in result.evidence_limitations} >= {"user_supplied_graph"}


def test_identified_result_marks_contract_validated_adjustment_set_valid() -> None:
    result = CausalIdentificationService().identify(request())
    assert result.adjustment_set is not None
    assert result.adjustment_set.validation_status.value == "valid"
    assert result.adjustment_set.diagnostics == ()


def test_treatment_outcome_and_time_references_require_matching_roles() -> None:
    declared = tuple(
        variable(
            item.variable_id,
            VariableRole.IDENTIFIER if item.variable_id == "treated" else item.roles[0],
            timing=item.timing.measurement_timing,
        )
        for item in variables()
    )
    candidate = request(declared_variables=declared)
    identification = candidate.identification.model_copy(
        update={
            "time": candidate.identification.time.model_copy(update={"time_variable": "conversion"})
        }
    )
    result = CausalIdentificationService().identify(
        candidate.model_copy(update={"identification": identification})
    )
    assert result.status is IdentificationStatus.INVALID
    assert CausalDiagnosticCode.CONTRADICTORY_ROLE in diagnostic_codes(result)


def test_estimand_bindings_must_match_request_declarations() -> None:
    candidate = request()
    mismatched_estimand = candidate.identification.estimand.model_copy(
        update={
            "treatment_contrast": candidate.identification.estimand.treatment_contrast.model_copy(
                update={"treatment_variable": "prior_orders"}
            ),
            "outcome_variable": "prior_orders",
            "target_population": candidate.identification.estimand.target_population.model_copy(
                update={
                    "population": candidate.identification.population.model_copy(
                        update={"population_id": "other_population"}
                    )
                }
            ),
        }
    )
    identification = candidate.identification.model_copy(update={"estimand": mismatched_estimand})
    result = CausalIdentificationService().identify(
        candidate.model_copy(update={"identification": identification})
    )
    assert result.status is IdentificationStatus.INVALID
    assert CausalDiagnosticCode.ESTIMAND_REQUEST_MISMATCH in diagnostic_codes(result)


def test_duplicate_covariate_references_are_invalid() -> None:
    candidate = request()
    identification = candidate.identification.model_copy(
        update={"covariates": ("prior_orders", "prior_orders")}
    )
    result = CausalIdentificationService().identify(
        candidate.model_copy(update={"identification": identification})
    )
    assert result.status is IdentificationStatus.INVALID
    assert CausalDiagnosticCode.DUPLICATE_COVARIATE in diagnostic_codes(result)
