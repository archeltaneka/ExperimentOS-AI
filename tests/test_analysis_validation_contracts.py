from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.experiments.analysis import AnalysisStatus
from packages.experiments.analysis.serialization import to_canonical_json
from packages.experiments.analysis.validation import (
    AnalysisDataBinding,
    AnalysisTable,
    AnalysisTableError,
    DiagnosticDisposition,
    EligibilityDiagnostic,
    EligibilityValidationResult,
    MethodContractStatus,
    MethodImplementationStatus,
    MethodSupportAssessment,
    MetricColumnBinding,
    OutcomeDataBinding,
    ValidationCategory,
    ValidationPolicy,
)
from tests.analysis_validation_fixtures import (
    abstention_reason_fixture,
    diagnostic_fixture,
    eligible_result_fixture,
    method_support_fixture,
    unused_summary_contracts_fixture,
)


def test_analysis_table_snapshots_records_without_mutating_callers() -> None:
    records = [{"unit": "u1", "arm": "control", "outcome": 0}]
    table = AnalysisTable.from_records(records)
    records[0]["outcome"] = 1
    assert table.columns == ("unit", "arm", "outcome")
    assert table.rows == (("u1", "control", 0),)


def test_validation_policy_defaults_and_invalid_thresholds() -> None:
    policy = ValidationPolicy()
    assert policy.policy_version == "analysis-validation-v1"
    assert (policy.minimum_total, policy.minimum_per_arm) == (30, 10)
    with pytest.raises(ValidationError):
        ValidationPolicy(
            allocation_warning_deviation=0.3,
            allocation_blocking_deviation=0.2,
        )


def test_analysis_table_rejects_inconsistent_record_columns_and_row_widths() -> None:
    with pytest.raises(AnalysisTableError, match="same columns"):
        AnalysisTable.from_records(({"unit": "u1"}, {"arm": "control"}))
    with pytest.raises(AnalysisTableError, match="declared column count"):
        AnalysisTable(columns=("unit", "arm"), rows=(("u1",),))


def test_outcome_binding_requires_one_supported_shape() -> None:
    assert OutcomeDataBinding(value_column="outcome").value_column == "outcome"
    ratio = OutcomeDataBinding(
        numerator_column="successes",
        denominator_column="attempts",
    )
    assert (ratio.numerator_column, ratio.denominator_column) == ("successes", "attempts")
    with pytest.raises(ValidationError):
        OutcomeDataBinding()
    with pytest.raises(ValidationError):
        OutcomeDataBinding(value_column="outcome", numerator_column="successes")


def test_analysis_binding_rejects_duplicate_metric_and_role_columns() -> None:
    covariate = MetricColumnBinding(metric_id="prior_orders", column="prior_orders")
    binding = AnalysisDataBinding(
        treatment_column="arm",
        outcome=OutcomeDataBinding(value_column="outcome"),
        observation_unit_column="unit",
        covariates=(covariate,),
    )
    assert binding.covariates == (covariate,)

    with pytest.raises(ValidationError):
        AnalysisDataBinding(
            treatment_column="arm",
            outcome=OutcomeDataBinding(value_column="outcome"),
            observation_unit_column="unit",
            covariates=(
                covariate,
                MetricColumnBinding(metric_id="prior_orders", column="account_age"),
            ),
        )
    with pytest.raises(ValidationError):
        AnalysisDataBinding(
            treatment_column="arm",
            outcome=OutcomeDataBinding(value_column="outcome"),
            observation_unit_column="unit",
            covariates=(MetricColumnBinding(metric_id="arm_copy", column="arm"),),
        )


def test_validation_result_has_no_estimate_and_serializes() -> None:
    result = eligible_result_fixture()
    payload = to_canonical_json(result)
    assert '"outcome_type":"eligibility_validation"' in payload
    assert "estimate" not in result.model_dump(mode="json")


def test_diagnostic_context_order_is_canonical() -> None:
    diagnostic = diagnostic_fixture(context={"z": 2, "a": 1})
    assert [entry.key for entry in diagnostic.context] == ["a", "z"]


def test_diagnostic_context_is_sorted_after_key_normalization() -> None:
    diagnostic = diagnostic_fixture(context={" z": 2, "a ": 1})
    assert [entry.key for entry in diagnostic.context] == ["a", "z"]


def test_diagnostic_context_rejects_duplicate_normalized_keys() -> None:
    with pytest.raises(ValidationError, match="context keys must be unique"):
        diagnostic_fixture(context={"a": 1, " a ": 2})


def test_policy_defaults_ignore_ambient_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXPERIMENTOS_MINIMUM_TOTAL", "999")
    assert ValidationPolicy().minimum_total == 30


def test_result_requires_exact_diagnostic_subsets() -> None:
    blocking = diagnostic_fixture(
        code="schema.required_column_missing",
        disposition=DiagnosticDisposition.BLOCKING,
    )
    with pytest.raises(ValidationError, match="blocking_diagnostics"):
        eligible_result_fixture(diagnostics=(blocking,))


@pytest.mark.parametrize(
    ("diagnostics", "status"),
    [
        (
            (
                diagnostic_fixture(
                    code="schema.required_column_missing",
                    disposition=DiagnosticDisposition.BLOCKING,
                ),
            ),
            AnalysisStatus.ELIGIBLE,
        ),
        (
            (
                diagnostic_fixture(
                    code="sample.total_insufficient",
                    disposition=DiagnosticDisposition.NEEDS_MORE_DATA,
                ),
            ),
            AnalysisStatus.ELIGIBLE,
        ),
        (
            (
                diagnostic_fixture(
                    code="sample.total_weak",
                    disposition=DiagnosticDisposition.WARNING,
                ),
            ),
            AnalysisStatus.ELIGIBLE,
        ),
        ((diagnostic_fixture(),), AnalysisStatus.ELIGIBLE_WITH_WARNINGS),
    ],
)
def test_result_status_matches_diagnostic_disposition_precedence(
    diagnostics: tuple[EligibilityDiagnostic, ...],
    status: AnalysisStatus,
) -> None:
    eligible = eligible_result_fixture()
    blocking = tuple(
        item for item in diagnostics if item.disposition is DiagnosticDisposition.BLOCKING
    )
    warnings = tuple(
        item for item in diagnostics if item.disposition is DiagnosticDisposition.WARNING
    )
    method_support = method_support_fixture(
        data_eligible=not any(
            item.disposition
            in {DiagnosticDisposition.BLOCKING, DiagnosticDisposition.NEEDS_MORE_DATA}
            for item in diagnostics
        ),
        executable=not any(
            item.disposition
            in {DiagnosticDisposition.BLOCKING, DiagnosticDisposition.NEEDS_MORE_DATA}
            for item in diagnostics
        ),
    )

    with pytest.raises(ValidationError, match="status.*diagnostic disposition precedence"):
        EligibilityValidationResult.model_validate(
            {
                **eligible.model_dump(),
                "status": status,
                "diagnostics": diagnostics,
                "blocking_diagnostics": blocking,
                "warnings": warnings,
                "method_support": method_support,
            }
        )


def test_abstention_reason_matches_final_eligibility_status() -> None:
    eligible = eligible_result_fixture()
    with pytest.raises(ValidationError, match="abstention_reason"):
        EligibilityValidationResult.model_validate(
            {**eligible.model_dump(), "abstention_reason": abstention_reason_fixture()}
        )

    with pytest.raises(ValidationError, match="abstention_reason"):
        EligibilityValidationResult.model_validate(
            {
                **eligible.model_dump(),
                "status": AnalysisStatus.NEEDS_MORE_DATA,
                "method_support": method_support_fixture(
                    data_eligible=False,
                    executable=False,
                ),
            }
        )


def test_ineligible_result_forbids_executable_method_support() -> None:
    eligible = eligible_result_fixture()
    blocking = diagnostic_fixture(
        code="schema.required_column_missing",
        disposition=DiagnosticDisposition.BLOCKING,
    )
    with pytest.raises(ValidationError, match="executable"):
        EligibilityValidationResult.model_validate(
            {
                **eligible.model_dump(),
                "status": AnalysisStatus.INELIGIBLE,
                "diagnostics": (blocking,),
                "blocking_diagnostics": (blocking,),
                "abstention_reason": abstention_reason_fixture(),
            }
        )


def test_needs_more_data_result_forbids_executable_method_support() -> None:
    eligible = eligible_result_fixture()
    needs_data = diagnostic_fixture(
        code="sample.total_insufficient",
        disposition=DiagnosticDisposition.NEEDS_MORE_DATA,
    )

    with pytest.raises(ValidationError, match="executable"):
        EligibilityValidationResult.model_validate(
            {
                **eligible.model_dump(),
                "status": AnalysisStatus.NEEDS_MORE_DATA,
                "diagnostics": (needs_data,),
                "method_support": method_support_fixture(),
                "abstention_reason": abstention_reason_fixture(),
            }
        )


@pytest.mark.parametrize(
    ("diagnostic", "status"),
    [
        (
            diagnostic_fixture(
                code="schema.required_column_missing",
                disposition=DiagnosticDisposition.BLOCKING,
            ),
            AnalysisStatus.INELIGIBLE,
        ),
        (
            diagnostic_fixture(
                code="sample.total_insufficient",
                disposition=DiagnosticDisposition.NEEDS_MORE_DATA,
            ),
            AnalysisStatus.NEEDS_MORE_DATA,
        ),
    ],
)
def test_data_eligible_rejects_non_capability_blockers_and_needs_data(
    diagnostic: EligibilityDiagnostic,
    status: AnalysisStatus,
) -> None:
    eligible = eligible_result_fixture()
    blocking = (diagnostic,) if diagnostic.disposition is DiagnosticDisposition.BLOCKING else ()

    with pytest.raises(ValidationError, match="data_eligible"):
        EligibilityValidationResult.model_validate(
            {
                **eligible.model_dump(),
                "status": status,
                "diagnostics": (diagnostic,),
                "blocking_diagnostics": blocking,
                "method_support": MethodSupportAssessment(
                    requested_method="fixed_horizon_ab",
                    contract_status=MethodContractStatus.SUPPORTED,
                    implementation_status=MethodImplementationStatus.UNAVAILABLE,
                    data_eligible=True,
                    executable=False,
                ),
                "abstention_reason": abstention_reason_fixture(),
            }
        )


def test_capability_only_blocker_preserves_data_eligibility() -> None:
    eligible = eligible_result_fixture()
    unavailable = diagnostic_fixture(
        code="method.implementation_unavailable",
        disposition=DiagnosticDisposition.BLOCKING,
    ).model_copy(update={"category": ValidationCategory.METHOD})

    result = EligibilityValidationResult.model_validate(
        {
            **eligible.model_dump(),
            "status": AnalysisStatus.INELIGIBLE,
            "diagnostics": (unavailable,),
            "blocking_diagnostics": (unavailable,),
            "method_support": MethodSupportAssessment(
                requested_method="fixed_horizon_ab",
                contract_status=MethodContractStatus.SUPPORTED,
                implementation_status=MethodImplementationStatus.UNAVAILABLE,
                data_eligible=True,
                executable=False,
            ),
            "abstention_reason": abstention_reason_fixture(),
        }
    )

    assert result.method_support.data_eligible is True


def test_method_support_executable_requires_all_support_dimensions() -> None:
    with pytest.raises(ValidationError, match="executable"):
        MethodSupportAssessment(
            requested_method="fixed_horizon_ab",
            contract_status=MethodContractStatus.SUPPORTED,
            implementation_status=MethodImplementationStatus.UNAVAILABLE,
            data_eligible=True,
            executable=True,
        )


def test_optional_summary_contracts_are_constructible() -> None:
    time_summary, segment_summary = unused_summary_contracts_fixture()
    assert (time_summary.pre_period_count, segment_summary.selected_count) == (20, 20)
