from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from packages.experiments.analysis import (
    SCHEMA_VERSION,
    AnalysisStatus,
    AnalysisUnit,
    CovariateRole,
    CovariateTiming,
    CriterionOperator,
    EstimandDefinition,
    EstimandKind,
    MeasuredValue,
    MetricDefinition,
    MetricType,
    MetricUnit,
    OutcomeDirection,
    OutcomeMetric,
    PopulationDefinition,
    PreTreatmentMetric,
    QuasiExperimentalDesign,
    QuasiExperimentalMethod,
    RandomizedAnalysisMethod,
    RequestedConfidenceLevel,
    RequestedCredibleLevel,
    SampleCounts,
    SegmentDefinition,
    SelectionCriterion,
    TimePeriod,
    TreatmentRelationship,
    UnitDimension,
    ValueScale,
)
from tests.analysis_contract_fixtures import (
    covariate,
    observational_request,
    randomized_design,
    randomized_request,
    utc,
)


def proportion_unit() -> MetricUnit:
    return MetricUnit(
        dimension=UnitDimension.PROPORTION,
        value_scale=ValueScale.PROPORTION,
        symbol="1",
        scale_to_base_unit=1.0,
    )


def test_task_one_enum_values_are_stable() -> None:
    assert SCHEMA_VERSION == "1"
    assert [member.value for member in AnalysisStatus] == [
        "eligible",
        "eligible_with_warnings",
        "ineligible",
        "needs_more_data",
        "completed",
        "inconclusive",
        "abstained",
        "failed",
    ]
    assert [member.value for member in UnitDimension] == [
        "dimensionless",
        "proportion",
        "count",
        "currency",
        "duration",
        "rate",
        "ratio",
        "custom",
    ]
    assert [member.value for member in ValueScale] == [
        "raw",
        "proportion",
        "percent",
        "percentage_point",
        "basis_point",
        "custom",
    ]
    assert [member.value for member in MetricType] == [
        "continuous",
        "binary",
        "count",
        "proportion",
        "rate",
        "ratio",
    ]
    assert [member.value for member in OutcomeDirection] == [
        "increase",
        "decrease",
        "no_preference",
    ]
    assert [member.value for member in CriterionOperator] == [
        "equal",
        "not_equal",
        "greater_than",
        "greater_than_or_equal",
        "less_than",
        "less_than_or_equal",
        "in",
        "not_in",
    ]
    assert [member.value for member in EstimandKind] == [
        "difference_in_means",
        "difference_in_proportions",
        "absolute_lift",
        "relative_lift",
        "average_treatment_effect",
        "average_treatment_effect_on_treated",
        "conditional_average_treatment_effect",
        "intention_to_treat",
    ]


def test_metric_unit_rejects_ambiguous_or_invalid_units() -> None:
    with pytest.raises(ValidationError):
        MetricUnit.model_validate({"symbol": "%"})
    with pytest.raises(ValidationError, match="proportion dimension"):
        MetricUnit(
            dimension=UnitDimension.COUNT,
            value_scale=ValueScale.PERCENT,
            symbol="%",
            scale_to_base_unit=0.01,
        )
    with pytest.raises(ValidationError, match="currency_code"):
        MetricUnit(
            dimension=UnitDimension.CURRENCY,
            value_scale=ValueScale.RAW,
            symbol="$",
            scale_to_base_unit=1.0,
        )
    with pytest.raises(ValidationError):
        MetricUnit(
            dimension=UnitDimension.COUNT,
            value_scale=ValueScale.RAW,
            symbol="count",
            scale_to_base_unit=float("nan"),
        )


def test_metric_unit_requires_dimension_specific_metadata() -> None:
    with pytest.raises(ValidationError, match="custom_dimension_name"):
        MetricUnit(
            dimension=UnitDimension.CUSTOM,
            value_scale=ValueScale.CUSTOM,
            symbol="orders/user-day",
            scale_to_base_unit=1.0,
        )
    with pytest.raises(ValidationError, match="only valid for currency"):
        MetricUnit(
            dimension=UnitDimension.COUNT,
            value_scale=ValueScale.RAW,
            symbol="count",
            scale_to_base_unit=1.0,
            currency_code="AUD",
        )
    with pytest.raises(ValidationError, match="only valid for custom"):
        MetricUnit(
            dimension=UnitDimension.COUNT,
            value_scale=ValueScale.RAW,
            symbol="count",
            scale_to_base_unit=1.0,
            custom_dimension_name="orders per user-day",
        )


def test_task_one_contracts_compose_without_presentation_values() -> None:
    unit = proportion_unit()
    definition = MetricDefinition(
        metric_id="conversion_rate",
        label="Conversion rate",
        metric_type=MetricType.PROPORTION,
        unit=unit,
    )
    outcome = OutcomeMetric(metric=definition, direction=OutcomeDirection.INCREASE)
    measured = MeasuredValue(value=0.125, unit=unit)
    analysis_unit = AnalysisUnit(unit_id="user", label="User")
    population = PopulationDefinition(
        population_id="eligible_users",
        label="All eligible users",
        criteria=(),
    )

    assert outcome.metric == definition
    assert measured.model_dump()["value"] == 0.125
    assert analysis_unit.unit_id == "user"
    assert population.criteria == ()


def test_selection_criterion_value_shape_matches_operator() -> None:
    criterion = SelectionCriterion(
        attribute="country_code",
        operator=CriterionOperator.IN,
        value=("AU", "NZ"),
    )
    assert criterion.value == ("AU", "NZ")

    with pytest.raises(ValidationError, match="non-empty tuple"):
        SelectionCriterion(
            attribute="country_code",
            operator=CriterionOperator.IN,
            value=(),
        )
    with pytest.raises(ValidationError, match="tuple value"):
        SelectionCriterion(
            attribute="age",
            operator=CriterionOperator.GREATER_THAN_OR_EQUAL,
            value=(18,),
        )
    with pytest.raises(ValidationError, match="scalar value"):
        SelectionCriterion(
            attribute="country_code",
            operator=CriterionOperator.NOT_IN,
            value="AU",
        )


@pytest.mark.parametrize(
    ("total", "treatment", "control"),
    [(0, 0, 0), (10, 0, 10), (10, 5, 4), (-1, 1, 1), (True, 1, 1)],
)
def test_sample_counts_reject_invalid_values(
    total: object,
    treatment: object,
    control: object,
) -> None:
    with pytest.raises(ValidationError):
        SampleCounts(total=total, treatment=treatment, control=control)


def test_cate_requires_a_conditioning_segment_and_other_estimands_forbid_it() -> None:
    segment = SegmentDefinition(segment_id="au", label="Australia", criteria=())
    cate = EstimandDefinition(
        kind=EstimandKind.CONDITIONAL_AVERAGE_TREATMENT_EFFECT,
        conditioning_segment=segment,
    )
    assert cate.conditioning_segment == segment
    with pytest.raises(ValidationError, match="conditioning segment"):
        EstimandDefinition(kind=EstimandKind.CONDITIONAL_AVERAGE_TREATMENT_EFFECT)
    with pytest.raises(ValidationError, match="only valid for CATE"):
        EstimandDefinition(kind=EstimandKind.AVERAGE_TREATMENT_EFFECT, conditioning_segment=segment)


def test_contract_models_are_frozen_and_reject_unknown_fields() -> None:
    unit = proportion_unit()
    with pytest.raises(ValidationError, match="frozen"):
        unit.symbol = "%"  # type: ignore[misc]
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MetricUnit.model_validate({**unit.model_dump(), "presentation": "5%"})


def test_constructs_valid_randomized_experiment_request() -> None:
    request = randomized_request()
    assert request.study_design.design_type == "randomized_experiment"
    assert request.study_design.randomization_unit.unit_id == "account"
    assert request.unit_of_analysis.unit_id == "order"
    assert request.clustering.kind == "none"
    assert request.estimand.kind is EstimandKind.INTENTION_TO_TREAT


def test_constructs_valid_observational_analysis_request() -> None:
    request = observational_request()
    assert request.study_design.design_type == "observational_study"
    assert request.study_design.method == "double_machine_learning"
    assert request.clustering.unit.unit_id == "customer"
    assert request.estimand.kind is EstimandKind.AVERAGE_TREATMENT_EFFECT_ON_TREATED


def test_request_rejects_equal_treatment_and_control_definitions() -> None:
    with pytest.raises(ValidationError, match="assignment values must differ"):
        randomized_request(control_assignment_value="treatment")
    with pytest.raises(ValidationError, match="identifiers must differ"):
        randomized_request(control_id="ranked_payment")
    with pytest.raises(ValidationError, match="labels must differ"):
        randomized_request(control_label="Ranked payment")


@pytest.mark.parametrize(
    ("treatment", "control"),
    [(0.0, 1.0), (1.0, 0.0), (0.7, 0.4), (-0.1, 1.1)],
)
def test_randomized_design_rejects_invalid_allocations(treatment: float, control: float) -> None:
    with pytest.raises(ValidationError):
        randomized_design(treatment_allocation=treatment, control_allocation=control)


def test_time_period_rejects_naive_or_reversed_timestamps() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        TimePeriod(start=datetime(2026, 1, 2), end=datetime(2026, 1, 3))
    with pytest.raises(ValidationError, match="before end"):
        TimePeriod(start=utc(2026, 1, 3), end=utc(2026, 1, 2))


def test_post_treatment_and_unknown_covariates_are_explicitly_representable() -> None:
    post = covariate(timing=CovariateTiming.POST_TREATMENT)
    unknown = covariate(
        timing=CovariateTiming.UNKNOWN,
        treatment_relationship=TreatmentRelationship.UNKNOWN,
    )
    assert post.timing is CovariateTiming.POST_TREATMENT
    assert unknown.timing is CovariateTiming.UNKNOWN
    assert unknown.treatment_relationship is TreatmentRelationship.UNKNOWN


def test_leakage_and_invalid_cuped_roles_remain_representable() -> None:
    questionable = covariate(
        timing=CovariateTiming.POST_TREATMENT,
        role=CovariateRole.CUPED,
        treatment_relationship=TreatmentRelationship.PROXY,
    )
    assert questionable.role is CovariateRole.CUPED
    assert questionable.treatment_relationship is TreatmentRelationship.PROXY


def test_quasi_experimental_periods_must_not_overlap() -> None:
    with pytest.raises(ValidationError, match="must end no later"):
        QuasiExperimentalDesign(
            method=QuasiExperimentalMethod.DIFFERENCE_IN_DIFFERENCES,
            pre_treatment_period=TimePeriod(
                start=utc(2026, 1, 1),
                end=utc(2026, 2, 2),
            ),
            post_treatment_period=TimePeriod(
                start=utc(2026, 2, 1),
                end=utc(2026, 3, 1),
            ),
        )


def test_pre_treatment_metrics_must_end_before_randomized_treatment() -> None:
    metric = PreTreatmentMetric(
        metric=covariate().metric,
        measurement_period=TimePeriod(
            start=utc(2026, 6, 1),
            end=utc(2026, 7, 2),
        ),
    )
    with pytest.raises(ValidationError, match="pre-treatment metric"):
        randomized_request(pre_treatment_metrics=(metric,))


@pytest.mark.parametrize("level", [0.0, 1.0, -0.1, 1.1])
def test_requested_uncertainty_levels_are_open_probabilities(level: float) -> None:
    with pytest.raises(ValidationError):
        RequestedConfidenceLevel(level=level)
    with pytest.raises(ValidationError):
        RequestedCredibleLevel(level=level)


def test_task_two_method_enum_values_are_stable() -> None:
    assert [member.value for member in RandomizedAnalysisMethod] == [
        "fixed_horizon_ab",
        "cuped",
        "sequential_ab",
        "bayesian_ab",
        "heterogeneous_treatment_effect",
    ]
    assert [member.value for member in QuasiExperimentalMethod] == ["difference_in_differences"]
