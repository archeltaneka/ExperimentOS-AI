from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.experiments.analysis import (
    AnalysisUnit,
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
    SampleCounts,
    SegmentDefinition,
    SelectionCriterion,
    UnitDimension,
    ValueScale,
)


def proportion_unit() -> MetricUnit:
    return MetricUnit(
        dimension=UnitDimension.PROPORTION,
        value_scale=ValueScale.PROPORTION,
        symbol="1",
        scale_to_base_unit=1.0,
    )


def test_task_one_enum_values_are_stable() -> None:
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
