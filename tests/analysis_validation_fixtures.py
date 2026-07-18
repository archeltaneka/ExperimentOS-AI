from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from packages.experiments.analysis import (
    AbstentionReason,
    AnalysisRequest,
    AnalysisStatus,
    CriterionOperator,
    DiagnosticOutcome,
    DiagnosticSeverity,
    MetricType,
    PopulationDefinition,
    SegmentDefinition,
    SelectionCriterion,
)
from packages.experiments.analysis.study_designs import (
    Clustered,
    RandomizedExperimentDesign,
)
from packages.experiments.analysis.validation import (
    AnalysisDataBinding,
    AnalysisTable,
    DatasetSummary,
    DiagnosticDisposition,
    EligibilityDiagnostic,
    EligibilityValidationResult,
    MethodContractStatus,
    MethodImplementationStatus,
    MethodSupportAssessment,
    MetricColumnBinding,
    MissingnessSummary,
    OutcomeSummary,
    SegmentEligibilitySummary,
    TimeDesignSummary,
    TreatmentSummary,
    UnitIntegritySummary,
    ValidationCategory,
    ValidationPolicy,
)
from packages.experiments.analysis.validation.bindings import OutcomeDataBinding
from packages.experiments.analysis.validation.context import ValidationContext
from tests.analysis_contract_fixtures import (
    covariate,
    quasi_experimental_request,
    randomized_request,
)


def analysis_table_fixture() -> AnalysisTable:
    return AnalysisTable(
        columns=("order_id", "account_id", "arm", "outcome"),
        rows=(
            ("order-1", "account-1", "control", 0.0),
            ("order-2", "account-2", "treatment", 1.0),
        ),
    )


def analysis_binding_fixture() -> AnalysisDataBinding:
    return AnalysisDataBinding(
        treatment_column="arm",
        outcome=OutcomeDataBinding(value_column="outcome"),
        observation_unit_column="order_id",
        randomization_unit_column="account_id",
    )


def context_for(
    request: AnalysisRequest | None = None,
    *,
    table: AnalysisTable | None = None,
    binding: AnalysisDataBinding | None = None,
    policy: ValidationPolicy | None = None,
) -> ValidationContext:
    return ValidationContext(
        request=request if request is not None else randomized_request(),
        table=table if table is not None else analysis_table_fixture(),
        binding=binding if binding is not None else analysis_binding_fixture(),
        policy=policy if policy is not None else ValidationPolicy(),
    )


def context_for_table(table: AnalysisTable) -> ValidationContext:
    return context_for(table=table)


def table_without(column: str) -> AnalysisTable:
    table = analysis_table_fixture()
    column_index = table.columns.index(column)
    return AnalysisTable(
        columns=tuple(name for index, name in enumerate(table.columns) if index != column_index),
        rows=tuple(
            tuple(value for index, value in enumerate(row) if index != column_index)
            for row in table.rows
        ),
    )


def table_with_arm_values(values: tuple[object, ...]) -> AnalysisTable:
    return AnalysisTable(
        columns=("order_id", "account_id", "arm", "outcome"),
        rows=tuple(
            (f"order-{index}", f"account-{index}", value, float(index % 2))
            for index, value in enumerate(values, start=1)
        ),
    )


def control_only_table() -> AnalysisTable:
    return table_with_arm_values(("control", "control"))


def context_with_country_population(countries: tuple[object, ...]) -> ValidationContext:
    request = randomized_request().model_copy(
        update={
            "population": PopulationDefinition(
                population_id="australian_checkout_users",
                label="Australian checkout users",
                criteria=(
                    SelectionCriterion(
                        attribute="country",
                        operator=CriterionOperator.EQUAL,
                        value="AU",
                    ),
                ),
            )
        }
    )
    table = AnalysisTable(
        columns=("order_id", "account_id", "arm", "outcome", "country"),
        rows=tuple(
            (
                f"order-{index}",
                f"account-{index}",
                "control" if index % 2 == 0 else "treatment",
                float(index % 2),
                country,
            )
            for index, country in enumerate(countries)
        ),
    )
    return context_for(request, table=table)


def context_with_outcomes(
    metric_type: MetricType,
    values: tuple[object, ...],
    *,
    policy: ValidationPolicy | None = None,
    outcome_binding: OutcomeDataBinding | None = None,
) -> ValidationContext:
    request = randomized_request()
    metric = request.outcome.metric.model_copy(update={"metric_type": metric_type})
    request = request.model_copy(
        update={"outcome": request.outcome.model_copy(update={"metric": metric})}
    )
    table = AnalysisTable(
        columns=("order_id", "account_id", "arm", "outcome"),
        rows=tuple(
            (
                f"order-{index}",
                f"account-{index}",
                "control" if index % 2 == 0 else "treatment",
                value,
            )
            for index, value in enumerate(values)
        ),
    )
    binding = analysis_binding_fixture()
    if outcome_binding is not None:
        binding = binding.model_copy(update={"outcome": outcome_binding})
    return context_for(request, table=table, binding=binding, policy=policy)


def ratio_context(
    *,
    numerators: tuple[object, ...],
    denominators: tuple[object, ...],
) -> ValidationContext:
    if len(numerators) != len(denominators):
        raise ValueError("ratio fixture columns must have equal lengths")
    request = randomized_request()
    metric = request.outcome.metric.model_copy(update={"metric_type": MetricType.RATIO})
    request = request.model_copy(
        update={"outcome": request.outcome.model_copy(update={"metric": metric})}
    )
    table = AnalysisTable(
        columns=("order_id", "account_id", "arm", "numerator", "denominator"),
        rows=tuple(
            (
                f"order-{index}",
                f"account-{index}",
                "control" if index % 2 == 0 else "treatment",
                numerator,
                denominator,
            )
            for index, (numerator, denominator) in enumerate(
                zip(numerators, denominators, strict=True)
            )
        ),
    )
    binding = analysis_binding_fixture().model_copy(
        update={
            "outcome": OutcomeDataBinding(
                numerator_column="numerator",
                denominator_column="denominator",
            )
        }
    )
    return context_for(request, table=table, binding=binding)


def context_with_arm_outcome_values(
    assignments: tuple[object, ...],
    outcomes: tuple[object, ...],
    *,
    policy: ValidationPolicy | None = None,
) -> ValidationContext:
    if len(assignments) != len(outcomes):
        raise ValueError("assignment and outcome fixture columns must have equal lengths")
    table = AnalysisTable(
        columns=("order_id", "account_id", "arm", "outcome"),
        rows=tuple(
            (f"order-{index}", f"account-{index}", assignment, outcome_value)
            for index, (assignment, outcome_value) in enumerate(
                zip(assignments, outcomes, strict=True)
            )
        ),
    )
    return context_for(table=table, policy=policy)


def context_with_arm_sizes(
    *,
    treatment: int,
    control: int,
    policy: ValidationPolicy | None = None,
) -> ValidationContext:
    assignments = ("treatment",) * treatment + ("control",) * control
    outcomes = tuple(float(index % 2) for index in range(len(assignments)))
    return context_with_arm_outcome_values(assignments, outcomes, policy=policy)


def _table_context(
    columns: tuple[str, ...],
    rows: tuple[tuple[object, ...], ...],
    *,
    request: AnalysisRequest | None = None,
    binding: AnalysisDataBinding | None = None,
    policy: ValidationPolicy | None = None,
) -> ValidationContext:
    return context_for(
        request,
        table=AnalysisTable(columns=columns, rows=rows),
        binding=binding,
        policy=policy,
    )


def context_with_missing_unit() -> ValidationContext:
    return _table_context(
        ("order_id", "account_id", "arm", "outcome"),
        (
            (None, "account-1", "control", 0.0),
            ("order-2", "account-2", "treatment", 1.0),
        ),
    )


def context_with_duplicate_single_row_units() -> ValidationContext:
    return _table_context(
        ("order_id", "account_id", "arm", "outcome"),
        (
            ("order-1", "account-1", "control", 0.0),
            ("order-1", "account-2", "treatment", 1.0),
        ),
    )


def context_with_randomization_unit_in_both_arms() -> ValidationContext:
    return _table_context(
        ("order_id", "account_id", "arm", "outcome"),
        (
            ("order-1", "account-1", "control", 0.0),
            ("order-2", "account-1", "treatment", 1.0),
        ),
    )


def context_with_switching_unit() -> ValidationContext:
    binding = analysis_binding_fixture().model_copy(update={"timestamp_column": "observed_at"})
    return _table_context(
        ("order_id", "account_id", "arm", "outcome", "observed_at"),
        (
            ("order-1", "account-1", "control", 0.0, "2026-06-16T00:00:00Z"),
            ("order-1", "account-1", "treatment", 1.0, "2026-06-17T00:00:00Z"),
        ),
        binding=binding,
    )


def context_with_repeated_rows_without_cluster() -> ValidationContext:
    binding = analysis_binding_fixture().model_copy(update={"timestamp_column": "observed_at"})
    return _table_context(
        ("order_id", "account_id", "arm", "outcome", "observed_at"),
        (
            ("order-1", "account-1", "control", 0.0, "2026-06-16T00:00:00Z"),
            ("order-1", "account-1", "control", 1.0, "2026-06-17T00:00:00Z"),
        ),
        binding=binding,
    )


def _clustered_request() -> AnalysisRequest:
    request = randomized_request()
    design = request.study_design
    if not isinstance(design, RandomizedExperimentDesign):
        raise RuntimeError("randomized fixture returned a non-randomized design")
    return request.model_copy(
        update={"clustering": Clustered(unit=design.randomization_unit)}
    )


def context_with_missing_cluster() -> ValidationContext:
    binding = analysis_binding_fixture().model_copy(update={"clustering_unit_column": "account_id"})
    return _table_context(
        ("order_id", "account_id", "arm", "outcome"),
        (
            ("order-1", None, "control", 0.0),
            ("order-2", "account-2", "treatment", 1.0),
        ),
        request=_clustered_request(),
        binding=binding,
    )


def context_with_three_clusters() -> ValidationContext:
    binding = analysis_binding_fixture().model_copy(update={"clustering_unit_column": "account_id"})
    rows = tuple(
        (
            f"order-{index}",
            f"account-{index % 3}",
            "control" if index % 2 == 0 else "treatment",
            float(index % 2),
        )
        for index in range(6)
    )
    return _table_context(
        ("order_id", "account_id", "arm", "outcome"),
        rows,
        request=_clustered_request(),
        binding=binding,
    )


def _request_with_covariate() -> AnalysisRequest:
    return randomized_request().model_copy(update={"covariates": (covariate(),)})


def _covariate_binding(*, with_timestamp: bool) -> AnalysisDataBinding:
    update: dict[str, object] = {
        "covariates": (
            MetricColumnBinding(metric_id="prior_order_count", column="prior_orders"),
        )
    }
    if with_timestamp:
        update["timestamp_column"] = "observed_at"
    return analysis_binding_fixture().model_copy(update=update)


def context_with_covariate_missing_in_required_period() -> ValidationContext:
    return _table_context(
        ("order_id", "account_id", "arm", "outcome", "prior_orders", "observed_at"),
        (
            ("order-1", "account-1", "control", 0.0, 3, "2026-06-16T00:00:00Z"),
            ("order-2", "account-2", "treatment", 1.0, 4, "2026-06-17T00:00:00Z"),
        ),
        request=_request_with_covariate(),
        binding=_covariate_binding(with_timestamp=True),
    )


def context_with_missing_optional_covariate_values() -> ValidationContext:
    return _table_context(
        ("order_id", "account_id", "arm", "outcome", "prior_orders"),
        (
            ("order-1", "account-1", "control", 0.0, None),
            ("order-2", "account-2", "treatment", 1.0, 4),
        ),
        request=_request_with_covariate(),
        binding=_covariate_binding(with_timestamp=False),
    )


def context_with_invalid_period_rows() -> ValidationContext:
    binding = analysis_binding_fixture().model_copy(update={"timestamp_column": "observed_at"})
    return _table_context(
        ("order_id", "account_id", "arm", "outcome", "observed_at"),
        (
            ("order-1", "account-1", "control", 0.0, "2026-06-10T00:00:00Z"),
            ("order-1", "account-1", "control", 1.0, "not-a-timestamp"),
            ("order-2", "account-2", "treatment", 0.0, "2026-06-11T00:00:00Z"),
        ),
        request=quasi_experimental_request(),
        binding=binding,
    )


def context_with_aware_datetime_rows() -> ValidationContext:
    binding = analysis_binding_fixture().model_copy(update={"timestamp_column": "observed_at"})
    rows = (
        ("order-1", "account-1", "control", 0.0, datetime(2026, 6, 16, tzinfo=UTC)),
        ("order-2", "account-2", "treatment", 1.0, datetime(2026, 6, 17, tzinfo=UTC)),
    )
    return _table_context(
        ("order_id", "account_id", "arm", "outcome", "observed_at"),
        rows,
        binding=binding,
    )


def _request_with_segment(
    *,
    operator: CriterionOperator = CriterionOperator.EQUAL,
    value: object = "AU",
) -> AnalysisRequest:
    segment = SegmentDefinition.model_validate(
        {
            "segment_id": "australian_users",
            "label": "Australian users",
            "criteria": (
                SelectionCriterion(
                    attribute="country",
                    operator=operator,
                    value=value,
                ),
            ),
        }
    )
    return randomized_request().model_copy(update={"segment": segment})


def _segment_context(
    countries: tuple[object, ...],
    assignments: tuple[object, ...],
    *,
    request: AnalysisRequest | None = None,
    policy: ValidationPolicy | None = None,
) -> ValidationContext:
    rows = tuple(
        (
            f"order-{index}",
            f"account-{index}",
            assignment,
            float(index % 2),
            country,
        )
        for index, (country, assignment) in enumerate(
            zip(countries, assignments, strict=True)
        )
    )
    return _table_context(
        ("order_id", "account_id", "arm", "outcome", "country"),
        rows,
        request=request or _request_with_segment(),
        policy=policy,
    )


def context_with_missing_segment_column() -> ValidationContext:
    return context_for(_request_with_segment())


def context_with_absent_segment_value() -> ValidationContext:
    return _segment_context(("NZ",) * 10, ("control", "treatment") * 5)


def context_with_segment_missing_control() -> ValidationContext:
    return _segment_context(
        ("AU",) * 5 + ("NZ",) * 5,
        ("treatment",) * 5 + ("control",) * 5,
    )


def context_with_small_segment() -> ValidationContext:
    return _segment_context(
        ("AU",) * 4 + ("NZ",) * 6,
        ("control", "treatment") * 5,
    )


def context_with_missing_segment_assignment() -> ValidationContext:
    return _segment_context(
        (None,) + ("AU",) * 10,
        ("control",) + ("control", "treatment") * 5,
    )


def context_with_high_cardinality_segment() -> ValidationContext:
    request = _request_with_segment(
        operator=CriterionOperator.NOT_EQUAL,
        value="not-present",
    )
    return _segment_context(
        tuple(f"country-{index}" for index in range(10)),
        ("control", "treatment") * 5,
        request=request,
        policy=ValidationPolicy(maximum_segment_cardinality=3),
    )


def context_with_incompatible_segment_values() -> ValidationContext:
    request = _request_with_segment(
        operator=CriterionOperator.GREATER_THAN,
        value=5,
    )
    return _segment_context(
        ("unknown",) * 10,
        ("control", "treatment") * 5,
        request=request,
    )


def context_with_schema_failure_and_segment() -> ValidationContext:
    table = table_without("arm")
    return context_for(_request_with_segment(), table=table)


def diagnostic_fixture(
    *,
    code: str = "schema.checked",
    disposition: DiagnosticDisposition = DiagnosticDisposition.INFORMATIONAL,
    context: Mapping[str, bool | int | float | str] | None = None,
) -> EligibilityDiagnostic:
    return EligibilityDiagnostic.model_validate(
        {
            "code": code,
            "category": ValidationCategory.SCHEMA,
            "severity": DiagnosticSeverity.INFO,
            "outcome": DiagnosticOutcome.PASSED,
            "disposition": disposition,
            "message": "Schema validation completed.",
            "context": context or {},
        }
    )


def dataset_summary_fixture() -> DatasetSummary:
    return DatasetSummary(input_row_count=40, population_row_count=40, column_count=3)


def treatment_summary_fixture() -> TreatmentSummary:
    return TreatmentSummary(
        treatment_count=20,
        control_count=20,
        missing_count=0,
        unknown_count=0,
    )


def outcome_summary_fixture() -> OutcomeSummary:
    return OutcomeSummary(
        valid_count=40,
        missing_count=0,
        invalid_type_count=0,
        non_finite_count=0,
        invalid_value_count=0,
        treatment_valid_count=20,
        control_valid_count=20,
        has_variation=True,
    )


def unit_integrity_summary_fixture() -> UnitIntegritySummary:
    return UnitIntegritySummary(
        observation_unit_count=40,
        missing_identifier_count=0,
        duplicate_identifier_count=0,
        repeated_observation_count=0,
        assignment_conflict_count=0,
        cluster_count=None,
    )


def method_support_fixture(
    *,
    data_eligible: bool = True,
    executable: bool = True,
) -> MethodSupportAssessment:
    return MethodSupportAssessment(
        requested_method="fixed_horizon_ab",
        contract_status=MethodContractStatus.SUPPORTED,
        implementation_status=MethodImplementationStatus.AVAILABLE,
        data_eligible=data_eligible,
        executable=executable,
    )


def abstention_reason_fixture() -> AbstentionReason:
    return AbstentionReason(
        code="validation_blocked",
        message="Analysis validation did not establish eligibility.",
        missing_or_invalid_information=("analysis input",),
    )


def eligible_result_fixture(
    *,
    diagnostics: tuple[EligibilityDiagnostic, ...] = (),
) -> EligibilityValidationResult:
    return EligibilityValidationResult(
        status=AnalysisStatus.ELIGIBLE,
        requested_method="fixed_horizon_ab",
        experiment_design="randomized_experiment",
        diagnostics=diagnostics,
        blocking_diagnostics=(),
        warnings=(),
        dataset_summary=dataset_summary_fixture(),
        treatment_summary=treatment_summary_fixture(),
        outcome_summary=outcome_summary_fixture(),
        missingness_summary=(
            MissingnessSummary(
                role="outcome",
                column="outcome",
                total_count=40,
                missing_count=0,
                missing_rate=0.0,
            ),
        ),
        unit_integrity_summary=unit_integrity_summary_fixture(),
        time_summary=None,
        segment_summary=None,
        method_support=method_support_fixture(),
        abstention_reason=None,
        policy_version="analysis-validation-v1",
        configuration_provenance="explicit defaults",
    )


def unused_summary_contracts_fixture() -> tuple[TimeDesignSummary, SegmentEligibilitySummary]:
    return (
        TimeDesignSummary(
            total_count=40,
            valid_count=40,
            missing_count=0,
            invalid_count=0,
            pre_period_count=20,
            post_period_count=20,
        ),
        SegmentEligibilitySummary(
            segment_id="returning_users",
            selected_count=20,
            treatment_count=10,
            control_count=10,
            treatment_valid_outcome_count=10,
            control_valid_outcome_count=10,
        ),
    )
