from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError

import pytest

from packages.experiments.analysis import (
    AnalysisRequest,
    AnalysisUnit,
    Clustered,
    CovariateRole,
    CovariateTiming,
    CriterionOperator,
    EstimandDefinition,
    EstimandKind,
    MetricType,
    ObservationalAnalysisMethod,
    PreTreatmentMetric,
    QuasiExperimentalMethod,
    RandomizedAnalysisMethod,
    SegmentDefinition,
    SelectionCriterion,
    TimePeriod,
    TreatmentRelationship,
)
from packages.experiments.analysis.validation.capabilities import (
    MethodCapability,
    MethodCapabilityRegistry,
)
from packages.experiments.analysis.validation.context import ValidationContext
from packages.experiments.analysis.validation.models import (
    DiagnosticDisposition,
    MethodContractStatus,
    MethodImplementationStatus,
)
from packages.experiments.analysis.validation.request_rules import (
    validate_request_consistency,
)
from tests.analysis_contract_fixtures import (
    covariate,
    observational_request,
    quasi_experimental_request,
    randomized_request,
    utc,
)
from tests.analysis_validation_fixtures import analysis_binding_fixture, context_for


def _with_method(request: AnalysisRequest, method: object) -> AnalysisRequest:
    design = request.study_design.model_copy(update={"method": method})
    return request.model_copy(update={"study_design": design})


@pytest.mark.parametrize(
    ("request_factory", "methods"),
    [
        (randomized_request, tuple(RandomizedAnalysisMethod)),
        (quasi_experimental_request, tuple(QuasiExperimentalMethod)),
        (observational_request, tuple(ObservationalAnalysisMethod)),
    ],
)
def test_every_contract_method_has_central_capability_entry(
    request_factory: Callable[[], AnalysisRequest],
    methods: tuple[object, ...],
) -> None:
    registry = MethodCapabilityRegistry.default()

    for method in methods:
        capability = registry.for_request(_with_method(request_factory(), method))
        assert capability.contract_status is MethodContractStatus.SUPPORTED
        assert capability.implementation_status is MethodImplementationStatus.UNAVAILABLE


def test_registry_can_declare_future_implementation_without_an_estimator() -> None:
    registry = MethodCapabilityRegistry.with_implemented_methods(
        (RandomizedAnalysisMethod.FIXED_HORIZON_AB,)
    )

    capability = registry.for_request(randomized_request())
    assessment = registry.assess(randomized_request(), data_eligible=True)

    assert capability.implementation_status is MethodImplementationStatus.AVAILABLE
    assert assessment.data_eligible is True
    assert assessment.executable is True


def test_registry_keeps_same_valued_method_families_distinct() -> None:
    registry = MethodCapabilityRegistry.with_implemented_methods(
        (RandomizedAnalysisMethod.HETEROGENEOUS_TREATMENT_EFFECT,)
    )

    randomized = _with_method(
        randomized_request(),
        RandomizedAnalysisMethod.HETEROGENEOUS_TREATMENT_EFFECT,
    )
    observational = _with_method(
        observational_request(),
        ObservationalAnalysisMethod.HETEROGENEOUS_TREATMENT_EFFECT,
    )

    assert registry.for_request(randomized).implementation_status is (
        MethodImplementationStatus.AVAILABLE
    )
    assert registry.for_request(observational).implementation_status is (
        MethodImplementationStatus.UNAVAILABLE
    )


def test_registry_rejects_duplicate_design_and_method_entries() -> None:
    entry = MethodCapability(
        design_type="randomized_experiment",
        method="fixed_horizon_ab",
        contract_status=MethodContractStatus.SUPPORTED,
        implementation_status=MethodImplementationStatus.UNAVAILABLE,
    )

    with pytest.raises(ValueError, match="duplicate method capability"):
        MethodCapabilityRegistry(entries=(entry, entry))


def test_registry_snapshots_caller_owned_entry_collections() -> None:
    entry = MethodCapability(
        design_type="randomized_experiment",
        method="fixed_horizon_ab",
        contract_status=MethodContractStatus.SUPPORTED,
        implementation_status=MethodImplementationStatus.UNAVAILABLE,
    )
    entries = [entry]
    registry = MethodCapabilityRegistry(entries=entries)  # type: ignore[arg-type]

    entries.append(entry)

    assert registry.entries == (entry,)


def test_context_normalizes_design_and_method_without_mutating_inputs() -> None:
    context = context_for()

    assert context.design_type == "randomized_experiment"
    assert context.method == "fixed_horizon_ab"
    with pytest.raises(FrozenInstanceError):
        context.policy = context.policy  # type: ignore[misc]


def test_capability_assessment_keeps_data_eligibility_separate() -> None:
    registry = MethodCapabilityRegistry.with_implemented_methods(
        (RandomizedAnalysisMethod.FIXED_HORIZON_AB,)
    )

    assessment = registry.assess(randomized_request(), data_eligible=False)

    assert assessment.implementation_status is MethodImplementationStatus.AVAILABLE
    assert assessment.data_eligible is False
    assert assessment.executable is False


def with_difference_in_proportions_on_continuous_metric(
    request: AnalysisRequest,
) -> AnalysisRequest:
    metric = request.outcome.metric.model_copy(update={"metric_type": MetricType.CONTINUOUS})
    outcome = request.outcome.model_copy(update={"metric": metric})
    estimand = EstimandDefinition(kind=EstimandKind.DIFFERENCE_IN_PROPORTIONS)
    return request.model_copy(update={"outcome": outcome, "estimand": estimand})


def with_post_treatment_adjustment(request: AnalysisRequest) -> AnalysisRequest:
    return request.model_copy(
        update={"covariates": (covariate(timing=CovariateTiming.POST_TREATMENT),)}
    )


def with_unknown_adjustment_timing(request: AnalysisRequest) -> AnalysisRequest:
    return request.model_copy(update={"covariates": (covariate(timing=CovariateTiming.UNKNOWN),)})


def with_pre_treatment_covariate_measured_after_assignment(
    request: AnalysisRequest,
) -> AnalysisRequest:
    adjustment = covariate().model_copy(
        update={
            "measurement_period": TimePeriod(
                start=utc(2026, 6, 15),
                end=utc(2026, 7, 2),
            )
        }
    )
    return request.model_copy(update={"covariates": (adjustment,)})


def with_outcome_reused_as_covariate(request: AnalysisRequest) -> AnalysisRequest:
    adjustment = covariate().model_copy(update={"metric": request.outcome.metric})
    return request.model_copy(update={"covariates": (adjustment,)})


def with_duplicate_covariate(request: AnalysisRequest) -> AnalysisRequest:
    adjustment = covariate()
    return request.model_copy(update={"covariates": (adjustment, adjustment)})


def with_unclustered_order_analysis_for_account_randomization(
    request: AnalysisRequest,
) -> AnalysisRequest:
    return request


@pytest.mark.parametrize(
    ("mutator", "expected_code"),
    [
        (
            with_difference_in_proportions_on_continuous_metric,
            "request.metric_estimand_incompatible",
        ),
        (with_post_treatment_adjustment, "covariate.post_treatment_leakage"),
        (with_unknown_adjustment_timing, "covariate.timing_unknown"),
        (
            with_pre_treatment_covariate_measured_after_assignment,
            "covariate.measurement_after_treatment",
        ),
        (with_outcome_reused_as_covariate, "request.covariate_role_conflict"),
        (with_duplicate_covariate, "request.duplicate_covariate"),
        (
            with_unclustered_order_analysis_for_account_randomization,
            "unit.cluster_required",
        ),
    ],
)
def test_request_consistency_codes(
    mutator: Callable[[AnalysisRequest], AnalysisRequest],
    expected_code: str,
) -> None:
    diagnostics = validate_request_consistency(context_for(mutator(randomized_request())))

    assert expected_code in {item.code for item in diagnostics}


def test_cate_segment_must_match_request_segment() -> None:
    requested = SegmentDefinition(segment_id="au", label="Australia", criteria=())
    conditioned = SegmentDefinition(segment_id="nz", label="New Zealand", criteria=())
    request = randomized_request().model_copy(
        update={
            "segment": requested,
            "estimand": EstimandDefinition(
                kind=EstimandKind.CONDITIONAL_AVERAGE_TREATMENT_EFFECT,
                conditioning_segment=conditioned,
            ),
        }
    )

    diagnostics = validate_request_consistency(context_for(request))

    assert "request.cate_segment_mismatch" in {item.code for item in diagnostics}


def test_cuped_requires_a_declared_pre_treatment_input() -> None:
    request = _with_method(randomized_request(), RandomizedAnalysisMethod.CUPED)

    diagnostics = validate_request_consistency(context_for(request))

    assert "method.pre_treatment_input_required" in {item.code for item in diagnostics}


def test_treatment_indicator_cannot_be_reused_as_adjustment_covariate() -> None:
    request = randomized_request().model_copy(
        update={"covariates": (covariate(role=CovariateRole.TREATMENT_INDICATOR),)}
    )

    diagnostics = validate_request_consistency(context_for(request))

    assert "request.covariate_role_conflict" in {item.code for item in diagnostics}


def test_equal_text_in_distinct_identifier_namespaces_is_not_a_role_conflict() -> None:
    adjustment = covariate()
    metric = adjustment.metric.model_copy(update={"metric_id": "order"})
    request = randomized_request().model_copy(
        update={"covariates": (adjustment.model_copy(update={"metric": metric}),)}
    )

    diagnostics = validate_request_consistency(context_for(request))

    assert "request.covariate_role_conflict" not in {item.code for item in diagnostics}


def test_declared_cluster_must_match_randomization_unit() -> None:
    request = randomized_request().model_copy(
        update={"clustering": Clustered(unit=requested_unit("store"))}
    )

    diagnostics = validate_request_consistency(context_for(request))

    assert "unit.cluster_mismatch" in {item.code for item in diagnostics}


def requested_unit(unit_id: str) -> AnalysisUnit:
    return randomized_request().unit_of_analysis.model_copy(
        update={"unit_id": unit_id, "label": unit_id.title()}
    )


@pytest.mark.parametrize(
    "analysis_request",
    [
        _with_method(
            randomized_request(),
            RandomizedAnalysisMethod.HETEROGENEOUS_TREATMENT_EFFECT,
        ),
        randomized_request().model_copy(
            update={
                "segment": SegmentDefinition(segment_id="au", label="Australia", criteria=()),
                "estimand": EstimandDefinition(
                    kind=EstimandKind.CONDITIONAL_AVERAGE_TREATMENT_EFFECT,
                    conditioning_segment=SegmentDefinition(
                        segment_id="au",
                        label="Australia",
                        criteria=(),
                    ),
                ),
            }
        ),
    ],
)
def test_hte_method_and_cate_estimand_must_be_paired(
    analysis_request: AnalysisRequest,
) -> None:
    diagnostics = validate_request_consistency(context_for(analysis_request))

    assert "method.estimand_incompatible" in {item.code for item in diagnostics}


@pytest.mark.parametrize(
    "analysis_request",
    [
        _with_method(randomized_request(), RandomizedAnalysisMethod.SEQUENTIAL_AB),
        quasi_experimental_request(),
    ],
)
def test_time_dependent_methods_require_timestamp_binding(
    analysis_request: AnalysisRequest,
) -> None:
    diagnostics = validate_request_consistency(context_for(analysis_request))

    assert "method.timestamp_required" in {item.code for item in diagnostics}


def test_observational_methods_require_declared_covariates() -> None:
    request = observational_request().model_copy(update={"covariates": ()})

    diagnostics = validate_request_consistency(context_for(request))

    assert "method.covariate_required" in {item.code for item in diagnostics}


def test_duplicate_pre_treatment_metrics_are_rejected() -> None:
    metric = covariate().metric
    pre_treatment_metric = PreTreatmentMetric(
        metric=metric,
        measurement_period=TimePeriod(
            start=utc(2026, 5, 1),
            end=utc(2026, 6, 1),
        ),
    )
    request = randomized_request().model_copy(
        update={"pre_treatment_metrics": (pre_treatment_metric, pre_treatment_metric)}
    )

    diagnostics = validate_request_consistency(context_for(request))

    assert "request.duplicate_pre_treatment_metric" in {item.code for item in diagnostics}


def test_segment_attribute_cannot_reuse_protected_binding_role() -> None:
    segment = SegmentDefinition(
        segment_id="control_arm",
        label="Control arm",
        criteria=(
            SelectionCriterion(
                attribute="arm",
                operator=CriterionOperator.EQUAL,
                value="control",
            ),
        ),
    )
    request = randomized_request().model_copy(update={"segment": segment})

    diagnostics = validate_request_consistency(context_for(request))

    assert "request.segment_role_conflict" in {item.code for item in diagnostics}


@pytest.mark.parametrize(
    "relationship",
    [TreatmentRelationship.ASSIGNMENT_DERIVED, TreatmentRelationship.PROXY],
)
def test_treatment_related_adjustment_is_rejected(
    relationship: TreatmentRelationship,
) -> None:
    request = randomized_request().model_copy(
        update={"covariates": (covariate(treatment_relationship=relationship),)}
    )

    diagnostics = validate_request_consistency(context_for(request))

    assert "covariate.treatment_relationship_conflict" in {item.code for item in diagnostics}


def test_unknown_treatment_relationship_is_rejected() -> None:
    request = randomized_request().model_copy(
        update={"covariates": (covariate(treatment_relationship=TreatmentRelationship.UNKNOWN),)}
    )

    diagnostics = validate_request_consistency(context_for(request))

    assert "covariate.relationship_unknown" in {item.code for item in diagnostics}


def test_randomized_design_requires_randomization_identifier_binding() -> None:
    binding = analysis_binding_fixture().model_copy(update={"randomization_unit_column": None})

    diagnostics = validate_request_consistency(context_for(binding=binding))

    assert "unit.randomization_identifier_required" in {item.code for item in diagnostics}


def test_clustered_request_requires_cluster_identifier_binding() -> None:
    request = randomized_request().model_copy(
        update={"clustering": Clustered(unit=requested_unit("account"))}
    )

    diagnostics = validate_request_consistency(context_for(request))

    assert "unit.cluster_identifier_required" in {item.code for item in diagnostics}


def randomization_clustering_binding_mismatch_context() -> ValidationContext:
    request = randomized_request().model_copy(
        update={"clustering": Clustered(unit=requested_unit("account"))}
    )
    binding = analysis_binding_fixture().model_copy(update={"clustering_unit_column": "order_id"})
    return context_for(request, binding=binding)


def randomization_observation_binding_mismatch_context() -> ValidationContext:
    request = randomized_request()
    design = request.study_design.model_copy(
        update={"randomization_unit": request.unit_of_analysis}
    )
    return context_for(request.model_copy(update={"study_design": design}))


def clustering_observation_binding_mismatch_context() -> ValidationContext:
    binding = analysis_binding_fixture().model_copy(
        update={
            "randomization_unit_column": None,
            "clustering_unit_column": "account_id",
        }
    )
    return context_for(observational_request(), binding=binding)


@pytest.mark.parametrize(
    ("context_factory", "expected_context"),
    [
        (
            randomization_clustering_binding_mismatch_context,
            {
                "first_column": "account_id",
                "first_role": "randomization_unit",
                "second_column": "order_id",
                "second_role": "clustering_unit",
                "unit_id": "account",
            },
        ),
        (
            randomization_observation_binding_mismatch_context,
            {
                "first_column": "account_id",
                "first_role": "randomization_unit",
                "second_column": "order_id",
                "second_role": "observation_unit",
                "unit_id": "order",
            },
        ),
        (
            clustering_observation_binding_mismatch_context,
            {
                "first_column": "order_id",
                "first_role": "observation_unit",
                "second_column": "account_id",
                "second_role": "clustering_unit",
                "unit_id": "customer",
            },
        ),
    ],
)
def test_equal_logical_units_require_equal_physical_bindings(
    context_factory: Callable[[], ValidationContext],
    expected_context: dict[str, str],
) -> None:
    diagnostics = validate_request_consistency(context_factory())

    item = next(item for item in diagnostics if item.code == "unit.binding_mismatch")
    assert item.disposition is DiagnosticDisposition.BLOCKING
    assert {entry.key: entry.value for entry in item.context} == expected_context
    assert tuple(entry.key for entry in item.context) == tuple(sorted(expected_context))


def test_request_diagnostics_follow_fixed_rule_order() -> None:
    adjustment = covariate(timing=CovariateTiming.POST_TREATMENT)
    request = with_difference_in_proportions_on_continuous_metric(randomized_request()).model_copy(
        update={"covariates": (adjustment, adjustment)}
    )

    codes = tuple(item.code for item in validate_request_consistency(context_for(request)))

    assert codes.index("request.metric_estimand_incompatible") < codes.index(
        "request.duplicate_covariate"
    )
    assert codes.index("request.duplicate_covariate") < codes.index(
        "covariate.post_treatment_leakage"
    )
    assert codes.index("covariate.post_treatment_leakage") < codes.index("unit.cluster_required")
