from __future__ import annotations

from collections.abc import Mapping

from packages.experiments.analysis import (
    AbstentionReason,
    AnalysisRequest,
    AnalysisStatus,
    DiagnosticOutcome,
    DiagnosticSeverity,
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
