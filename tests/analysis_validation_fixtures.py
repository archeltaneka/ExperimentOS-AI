from __future__ import annotations

from collections.abc import Mapping

from packages.experiments.analysis import (
    AbstentionReason,
    AnalysisRequest,
    AnalysisStatus,
    CriterionOperator,
    DiagnosticOutcome,
    DiagnosticSeverity,
    MetricType,
    PopulationDefinition,
    SelectionCriterion,
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
from tests.analysis_contract_fixtures import randomized_request


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
