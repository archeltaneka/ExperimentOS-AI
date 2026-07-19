from __future__ import annotations

import pytest

from packages.experiments.analysis import (
    CriterionOperator,
    MetricType,
    PreTreatmentMetric,
    SegmentDefinition,
    SelectionCriterion,
    TimePeriod,
)
from packages.experiments.analysis.validation import (
    AnalysisDataBinding,
    AnalysisTable,
    DiagnosticDisposition,
    MetricDataBinding,
    OutcomeDataBinding,
    ValidationPolicy,
)
from packages.experiments.analysis.validation.criteria import evaluate_criteria
from packages.experiments.analysis.validation.data_rules import validate_data
from tests.analysis_contract_fixtures import covariate, randomized_request, utc
from tests.analysis_validation_fixtures import (
    analysis_binding_fixture,
    context_for,
    context_for_table,
    context_with_arm_outcome_values,
    context_with_arm_sizes,
    context_with_country_population,
    context_with_outcomes,
    control_only_table,
    ratio_context,
    table_with_arm_values,
    table_without,
)


@pytest.mark.parametrize(
    ("table", "code"),
    [
        (
            AnalysisTable(
                columns=("unit", "arm", "arm"),
                rows=(("u1", "control", "control"),),
            ),
            "schema.duplicate_column",
        ),
        (AnalysisTable(columns=(), rows=()), "schema.empty_dataset"),
        (table_without("arm"), "schema.required_column_missing"),
        (table_with_arm_values(("control", "variant-b")), "treatment.unexpected_value"),
        (table_with_arm_values((None, "treatment")), "treatment.assignment_missing"),
        (control_only_table(), "treatment.arm_missing"),
    ],
)
def test_schema_and_treatment_diagnostics(table: AnalysisTable, code: str) -> None:
    result = validate_data(context_for_table(table))

    assert code in {item.code for item in result.diagnostics}


def test_population_criteria_preserve_before_and_after_counts() -> None:
    result = validate_data(context_with_country_population(("AU", "NZ", "AU")))

    assert result.dataset_summary.input_row_count == 3
    assert result.dataset_summary.population_row_count == 2
    assert result.population_row_indexes == (0, 2)


@pytest.mark.parametrize(
    ("operator", "criterion_value", "row_value", "expected"),
    [
        (CriterionOperator.EQUAL, 2, 2, True),
        (CriterionOperator.NOT_EQUAL, 2, 3, True),
        (CriterionOperator.GREATER_THAN, 2, 3, True),
        (CriterionOperator.GREATER_THAN_OR_EQUAL, 2, 2, True),
        (CriterionOperator.LESS_THAN, 2, 1, True),
        (CriterionOperator.LESS_THAN_OR_EQUAL, 2, 2, True),
        (CriterionOperator.IN, ("AU", "NZ"), "AU", True),
        (CriterionOperator.NOT_IN, ("AU", "NZ"), "US", True),
        (CriterionOperator.EQUAL, 1, True, False),
        (CriterionOperator.IN, (1, 2), True, False),
    ],
)
def test_shared_criteria_evaluator_uses_typed_operator_semantics(
    operator: CriterionOperator,
    criterion_value: object,
    row_value: object,
    expected: bool,
) -> None:
    criterion = SelectionCriterion.model_validate(
        {"attribute": "value", "operator": operator, "value": criterion_value}
    )

    assert evaluate_criteria({"value": row_value}, (criterion,)) is expected


def test_treatment_comparison_uses_exact_type_and_equality() -> None:
    result = validate_data(context_for_table(table_with_arm_values((True, "control"))))

    assert result.treatment_summary.treatment_count == 0
    assert result.treatment_summary.unknown_count == 1
    assert "treatment.unexpected_value" in {item.code for item in result.diagnostics}


def test_observed_allocation_uses_only_exactly_recognized_assignments() -> None:
    result = validate_data(context_for_table(table_with_arm_values(("treatment", "control", True))))

    assert result.observed_allocation.assigned_count == 2
    assert result.observed_allocation.treatment_rate == 0.5
    assert result.observed_allocation.control_rate == 0.5


def test_schema_failure_prevents_downstream_indexing_cascades() -> None:
    result = validate_data(
        context_for_table(
            AnalysisTable(
                columns=("unit", "arm", "arm"),
                rows=(("u1", "control", "control"),),
            )
        )
    )

    assert tuple(item.code for item in result.diagnostics) == ("schema.duplicate_column",)


def test_empty_explicit_population_is_reported_without_mutating_input_rows() -> None:
    context = context_with_country_population(("NZ", "NZ"))

    result = validate_data(context)

    assert "population.empty" in {item.code for item in result.diagnostics}
    assert result.population_row_indexes == ()
    assert context.table.rows == (
        ("order-0", "account-0", "control", 0.0, "NZ"),
        ("order-1", "account-1", "treatment", 1.0, "NZ"),
    )


@pytest.mark.parametrize(
    ("metric_type", "values", "code"),
    [
        (MetricType.BINARY, (0, 2, 1), "outcome.invalid_binary"),
        (MetricType.CONTINUOUS, (1.0, float("nan"), 2.0), "outcome.non_finite"),
        (MetricType.CONTINUOUS, (1.0, float("inf"), 2.0), "outcome.non_finite"),
        (MetricType.CONTINUOUS, ("1.0", 2.0, 3.0), "schema.outcome_not_numeric"),
        (MetricType.COUNT, (1, -1, 2), "outcome.negative"),
        (MetricType.CONTINUOUS, (5.0, 5.0, 5.0), "outcome.zero_variance"),
    ],
)
def test_outcome_diagnostics(
    metric_type: MetricType,
    values: tuple[object, ...],
    code: str,
) -> None:
    result = validate_data(context_with_outcomes(metric_type, values))

    assert code in {item.code for item in result.diagnostics}


def test_ratio_denominator_reports_zero_and_invalid_sign() -> None:
    result = validate_data(ratio_context(numerators=(1, 2), denominators=(0, -1)))

    assert {item.code for item in result.diagnostics} >= {
        "outcome.denominator_zero",
        "outcome.denominator_invalid_sign",
    }


def test_ratio_with_non_finite_derived_value_is_not_usable() -> None:
    result = validate_data(ratio_context(numerators=(1e308, 1.0), denominators=(1e-308, 1.0)))

    assert "outcome.non_finite" in {item.code for item in result.diagnostics}
    assert result.outcome_summary.non_finite_count == 1
    assert result.valid_row_indexes == (1,)


def test_outcome_classification_counts_are_disjoint_and_preserve_source_indexes() -> None:
    context = context_with_outcomes(
        MetricType.CONTINUOUS,
        (None, "2.0", float("nan"), 4.0),
    )

    result = validate_data(context)

    assert result.outcome_summary.missing_count == 1
    assert result.outcome_summary.invalid_type_count == 1
    assert result.outcome_summary.non_finite_count == 1
    assert result.outcome_summary.invalid_value_count == 0
    assert result.outcome_summary.valid_count == 1
    assert result.valid_row_indexes == (3,)
    assert context.table.rows[0][3] is None
    assert context.table.rows[1][3] == "2.0"


def test_large_distinct_integer_outcomes_preserve_variation_without_float_coercion() -> None:
    result = validate_data(context_with_outcomes(MetricType.CONTINUOUS, (2**53, 2**53 + 1)))

    assert result.outcome_summary.has_variation is True
    assert "outcome.zero_variance" not in {item.code for item in result.diagnostics}
    assert result.valid_row_indexes == (0, 1)


def test_arbitrarily_large_integer_outcome_returns_a_deterministic_result() -> None:
    result = validate_data(context_with_outcomes(MetricType.CONTINUOUS, (10**10000, 1)))

    assert result.outcome_summary.valid_count == 2
    assert result.outcome_summary.has_variation is True
    assert result.valid_row_indexes == (0, 1)


def test_outcome_binding_bounds_are_validated_without_clamping_values() -> None:
    context = context_with_outcomes(
        MetricType.CONTINUOUS,
        (-0.5, 0.5, 1.5),
        outcome_binding=OutcomeDataBinding(
            value_column="outcome",
            lower_bound=0.0,
            upper_bound=1.0,
        ),
    )

    result = validate_data(context)

    assert "outcome.out_of_bounds" in {item.code for item in result.diagnostics}
    assert result.outcome_summary.invalid_value_count == 2
    assert result.valid_row_indexes == (1,)
    assert context.table.rows[0][3] == -0.5
    assert context.table.rows[2][3] == 1.5


def test_missingness_summaries_are_emitted_for_bound_roles() -> None:
    result = validate_data(
        context_with_arm_outcome_values(
            ("treatment", "treatment", "control", "control"),
            (None, None, 1.0, None),
        )
    )

    summaries = {item.role: item for item in result.missingness_summary}
    assert tuple(summaries) == (
        "treatment",
        "outcome",
        "observation_unit",
        "randomization_unit",
    )
    assert summaries["outcome"].missing_count == 3
    assert summaries["outcome"].missing_rate == 0.75
    assert summaries["outcome"].treatment_missing_rate == 1.0
    assert summaries["outcome"].control_missing_rate == 0.5
    assert summaries["outcome"].differential_missingness == 0.5
    assert "missingness.differential" not in {item.code for item in result.diagnostics}


def test_differential_missingness_requires_an_explicit_threshold() -> None:
    policy = ValidationPolicy(maximum_differential_missingness=0.25)

    result = validate_data(
        context_with_arm_outcome_values(
            ("treatment", "treatment", "control", "control"),
            (None, None, 1.0, None),
            policy=policy,
        )
    )

    assert "missingness.differential" in {item.code for item in result.diagnostics}


def test_segment_missingness_is_summarized_once_per_unique_attribute() -> None:
    segment = SegmentDefinition(
        segment_id="australian_users",
        label="Australian users",
        criteria=(
            SelectionCriterion(
                attribute="country",
                operator=CriterionOperator.EQUAL,
                value="AU",
            ),
            SelectionCriterion(
                attribute="country",
                operator=CriterionOperator.NOT_EQUAL,
                value="NZ",
            ),
        ),
    )
    request = randomized_request().model_copy(update={"segment": segment})
    table = AnalysisTable(
        columns=("order_id", "account_id", "arm", "outcome", "country"),
        rows=(
            ("order-1", "account-1", "treatment", 0.0, None),
            ("order-2", "account-2", "treatment", 1.0, None),
            ("order-3", "account-3", "control", 0.0, "AU"),
            ("order-4", "account-4", "control", 1.0, None),
        ),
    )
    policy = ValidationPolicy(maximum_differential_missingness=0.25)

    result = validate_data(context_for(request, table=table, policy=policy))

    segment_summaries = [
        item for item in result.missingness_summary if item.role == "segment:country"
    ]
    assert len(segment_summaries) == 1
    assert segment_summaries[0].total_count == 4
    assert segment_summaries[0].missing_count == 3
    assert segment_summaries[0].missing_rate == 0.75
    assert segment_summaries[0].treatment_missing_rate == 1.0
    assert segment_summaries[0].control_missing_rate == 0.5
    assert segment_summaries[0].differential_missingness == 0.5
    item = next(item for item in result.diagnostics if item.code == "missingness.differential")
    assert {entry.key: entry.value for entry in item.context} == {
        "column": "country",
        "differential": 0.5,
        "threshold": 0.25,
    }


def test_missing_segment_column_does_not_cascade_into_missingness_failure() -> None:
    segment = SegmentDefinition(
        segment_id="australian_users",
        label="Australian users",
        criteria=(
            SelectionCriterion(
                attribute="country",
                operator=CriterionOperator.EQUAL,
                value="AU",
            ),
        ),
    )
    request = randomized_request().model_copy(update={"segment": segment})

    result = validate_data(context_for(request))

    assert "schema.required_column_missing" not in {item.code for item in result.diagnostics}
    assert all(item.role != "segment:country" for item in result.missingness_summary)


def test_bound_pre_treatment_metric_columns_are_required_by_the_dataset_schema() -> None:
    metric = covariate().metric
    request = randomized_request(
        pre_treatment_metrics=(
            PreTreatmentMetric(
                metric=metric,
                measurement_period=TimePeriod(
                    start=utc(2026, 5, 1),
                    end=utc(2026, 6, 1),
                ),
            ),
        )
    )
    binding: AnalysisDataBinding = analysis_binding_fixture().model_copy(
        update={
            "pre_treatment_metrics": (
                MetricDataBinding(
                    metric_id=metric.metric_id,
                    value_column="prior_orders",
                ),
            )
        }
    )

    result = validate_data(context_for(request, binding=binding))

    item = next(
        item for item in result.diagnostics if item.code == "schema.required_column_missing"
    )
    assert {entry.key: entry.value for entry in item.context} == {"column": "prior_orders"}


def test_outcome_missingness_limit_is_opt_in() -> None:
    context = context_with_arm_outcome_values(
        ("treatment", "treatment", "control", "control"),
        (None, None, 1.0, None),
        policy=ValidationPolicy(maximum_outcome_missingness=0.5),
    )

    result = validate_data(context)

    assert "missingness.outcome_exceeds_threshold" in {item.code for item in result.diagnostics}


def test_insufficient_samples_are_needs_more_data_diagnostics() -> None:
    diagnostics = validate_data(context_with_arm_sizes(treatment=9, control=10)).diagnostics

    item = next(item for item in diagnostics if item.code == "sample.arm_insufficient")
    assert item.disposition is DiagnosticDisposition.NEEDS_MORE_DATA


def test_one_row_arm_reports_exact_counts_and_needs_more_data() -> None:
    policy = ValidationPolicy(
        minimum_total=1,
        weak_total=1,
        minimum_per_arm=2,
        weak_per_arm=2,
        allocation_warning_deviation=1.0,
        allocation_blocking_deviation=1.0,
    )

    result = validate_data(context_with_arm_sizes(treatment=1, control=10, policy=policy))

    assert result.treatment_summary.treatment_count == 1
    assert result.treatment_summary.control_count == 10
    assert result.outcome_summary.treatment_valid_count == 1
    assert result.outcome_summary.control_valid_count == 10
    item = next(item for item in result.diagnostics if item.code == "sample.arm_insufficient")
    assert item.disposition is DiagnosticDisposition.NEEDS_MORE_DATA
    assert {entry.key: entry.value for entry in item.context} == {
        "control_count": 10,
        "threshold": 2,
        "treatment_count": 1,
    }


def test_declared_allocation_deviation_uses_policy_thresholds() -> None:
    warning = validate_data(context_with_arm_sizes(treatment=35, control=65)).diagnostics

    assert "allocation.deviation_warning" in {item.code for item in warning}


def test_severe_declared_allocation_deviation_is_blocking() -> None:
    diagnostics = validate_data(context_with_arm_sizes(treatment=20, control=80)).diagnostics

    item = next(item for item in diagnostics if item.code == "allocation.deviation_blocking")
    assert item.disposition is DiagnosticDisposition.BLOCKING


def test_allocation_warning_threshold_is_inclusive_despite_float_representation() -> None:
    diagnostics = validate_data(context_with_arm_sizes(treatment=40, control=60)).diagnostics

    assert "allocation.deviation_warning" in {item.code for item in diagnostics}


def test_weak_samples_warn_only_after_minimum_thresholds_are_met() -> None:
    diagnostics = validate_data(context_with_arm_sizes(treatment=20, control=20)).diagnostics
    by_code = {item.code: item for item in diagnostics}

    assert by_code["sample.total_weak"].disposition is DiagnosticDisposition.WARNING
    assert by_code["sample.arm_weak"].disposition is DiagnosticDisposition.WARNING
    assert "sample.total_insufficient" not in by_code
    assert "sample.arm_insufficient" not in by_code


def test_sample_rules_use_derived_valid_rows_without_dropping_source_rows() -> None:
    assignments = ("treatment",) * 10 + ("control",) * 10
    outcomes: tuple[object, ...] = (None, None) + tuple(float(index % 2) for index in range(18))
    context = context_with_arm_outcome_values(assignments, outcomes)

    result = validate_data(context)

    assert "sample.arm_insufficient" in {item.code for item in result.diagnostics}
    assert result.treatment_summary.treatment_count == 10
    assert result.outcome_summary.treatment_valid_count == 8
    assert len(result.valid_row_indexes) == 18
    assert len(context.table.rows) == 20


def test_sample_diagnostics_precede_allocation_diagnostics() -> None:
    codes = tuple(
        item.code
        for item in validate_data(context_with_arm_sizes(treatment=9, control=21)).diagnostics
    )

    assert codes.index("sample.arm_insufficient") < codes.index("allocation.deviation_warning")
