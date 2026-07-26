from __future__ import annotations

from collections.abc import Mapping

import pytest

from packages.experiments.analysis import (
    AnalysisRequest,
    AnalysisStatus,
    DiagnosticOutcome,
    DiagnosticSeverity,
    EstimandKind,
    MetricType,
    RandomizedAnalysisMethod,
    RandomizedExperimentDesign,
    eligibility_validation_result_from_json,
    to_canonical_json,
)
from packages.experiments.analysis.validation import (
    AnalysisDataBinding,
    AnalysisEligibilityService,
    AnalysisTable,
    DiagnosticDisposition,
    EligibilityDiagnostic,
    MethodCapabilityRegistry,
    ValidationCategory,
    aggregate_status,
)
from tests.analysis_contract_fixtures import randomized_request
from tests.analysis_validation_fixtures import analysis_binding_fixture


def _diagnostic(
    code: str,
    disposition: DiagnosticDisposition,
) -> EligibilityDiagnostic:
    return EligibilityDiagnostic(
        code=code,
        category=ValidationCategory.SCHEMA,
        severity=(
            DiagnosticSeverity.WARNING
            if disposition is DiagnosticDisposition.WARNING
            else DiagnosticSeverity.ERROR
        ),
        outcome=(
            DiagnosticOutcome.UNAVAILABLE
            if disposition is DiagnosticDisposition.NEEDS_MORE_DATA
            else DiagnosticOutcome.FAILED
        ),
        disposition=disposition,
        message=f"Diagnostic {code}.",
    )


@pytest.mark.parametrize(
    ("diagnostics", "status"),
    [
        (
            (
                _diagnostic("schema.blocked", DiagnosticDisposition.BLOCKING),
                _diagnostic("sample.small", DiagnosticDisposition.NEEDS_MORE_DATA),
                _diagnostic("sample.weak", DiagnosticDisposition.WARNING),
            ),
            AnalysisStatus.INELIGIBLE,
        ),
        (
            (
                _diagnostic("sample.small", DiagnosticDisposition.NEEDS_MORE_DATA),
                _diagnostic("sample.weak", DiagnosticDisposition.WARNING),
            ),
            AnalysisStatus.NEEDS_MORE_DATA,
        ),
        (
            (_diagnostic("sample.weak", DiagnosticDisposition.WARNING),),
            AnalysisStatus.ELIGIBLE_WITH_WARNINGS,
        ),
        ((), AnalysisStatus.ELIGIBLE),
    ],
)
def test_status_precedence(
    diagnostics: tuple[EligibilityDiagnostic, ...],
    status: AnalysisStatus,
) -> None:
    assert aggregate_status(diagnostics) is status


def _eligible_request() -> AnalysisRequest:
    request = randomized_request()
    design = request.study_design
    assert isinstance(design, RandomizedExperimentDesign)
    return request.model_copy(
        update={
            "study_design": design.model_copy(
                update={"randomization_unit": request.unit_of_analysis}
            )
        }
    )


def _eligible_binding() -> AnalysisDataBinding:
    return analysis_binding_fixture().model_copy(update={"randomization_unit_column": "order_id"})


def _eligible_table(*, row_count: int = 100) -> AnalysisTable:
    return AnalysisTable(
        columns=("order_id", "arm", "outcome"),
        rows=tuple(
            (
                f"order-{index}",
                "control" if index % 2 == 0 else "treatment",
                float(index % 2),
            )
            for index in range(row_count)
        ),
    )


def _implemented_service() -> AnalysisEligibilityService:
    return AnalysisEligibilityService(
        capability_registry=MethodCapabilityRegistry.with_implemented_methods(
            (RandomizedAnalysisMethod.FIXED_HORIZON_AB,)
        )
    )


def test_service_never_returns_an_estimate_field() -> None:
    result = _implemented_service().validate(
        _eligible_request(),
        _eligible_table(),
        _eligible_binding(),
    )

    assert result.status is AnalysisStatus.ELIGIBLE
    assert result.method_support.data_eligible is True
    assert result.method_support.executable is True
    assert "estimate" not in result.model_dump(mode="json")


def test_identical_inputs_have_identical_diagnostic_order_and_content() -> None:
    table = AnalysisTable(
        columns=("order_id", "arm", "outcome"),
        rows=tuple(
            (
                "duplicate-order" if index < 2 else f"order-{index}",
                "control" if index % 2 == 0 else "treatment",
                2.0 if index == 0 else float(index % 2),
            )
            for index in range(40)
        ),
    )
    service = _implemented_service()

    first = service.validate(_eligible_request(), table, _eligible_binding())
    second = service.validate(_eligible_request(), table, _eligible_binding())

    assert first.diagnostics == second.diagnostics
    assert to_canonical_json(first) == to_canonical_json(second)


def test_service_runs_request_data_and_design_diagnostics_in_fixed_order() -> None:
    request = _eligible_request()
    continuous = request.outcome.metric.model_copy(update={"metric_type": MetricType.CONTINUOUS})
    request = request.model_copy(
        update={
            "outcome": request.outcome.model_copy(update={"metric": continuous}),
            "estimand": request.estimand.model_copy(
                update={"kind": EstimandKind.DIFFERENCE_IN_PROPORTIONS}
            ),
        }
    )
    table = AnalysisTable(
        columns=("order_id", "arm", "outcome"),
        rows=(
            ("duplicate", "control", "not-numeric"),
            ("duplicate", "treatment", 1.0),
        ),
    )

    result = _implemented_service().validate(request, table, _eligible_binding())
    codes = tuple(item.code for item in result.diagnostics)

    assert codes.index("request.metric_estimand_incompatible") < codes.index(
        "schema.outcome_not_numeric"
    )
    assert codes.index("schema.outcome_not_numeric") < codes.index("unit.duplicate_observation")


def test_unreadable_schema_emits_dependent_rules_unavailable_diagnostic() -> None:
    table = AnalysisTable(
        columns=("order_id", "arm"),
        rows=(("order-1", "control"),),
    )

    result = _implemented_service().validate(
        _eligible_request(),
        table,
        _eligible_binding(),
    )
    diagnostics = {item.code: item for item in result.diagnostics}

    assert diagnostics["schema.required_column_missing"].outcome is DiagnosticOutcome.FAILED
    unavailable = diagnostics["schema.dependent_rules_unavailable"]
    assert unavailable.outcome is DiagnosticOutcome.UNAVAILABLE
    assert unavailable.disposition is DiagnosticDisposition.INFORMATIONAL


def test_structurally_valid_unimplemented_method_abstains() -> None:
    result = AnalysisEligibilityService().validate(
        _eligible_request(),
        _eligible_table(),
        _eligible_binding(),
    )

    assert result.status is AnalysisStatus.INELIGIBLE
    assert result.method_support.data_eligible is True
    assert result.method_support.implementation_status.value == "unavailable"
    assert result.method_support.executable is False
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "method.implementation_unavailable"


def test_abstention_uses_first_highest_precedence_diagnostic_and_all_required_codes() -> None:
    table = AnalysisTable(
        columns=("order_id", "arm", "outcome"),
        rows=(
            ("order-1", "control", "not-numeric"),
            ("order-2", "treatment", 1.0),
        ),
    )

    result = _implemented_service().validate(
        _eligible_request(),
        table,
        _eligible_binding(),
    )

    assert result.status is AnalysisStatus.INELIGIBLE
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "schema.outcome_not_numeric"
    assert result.abstention_reason.missing_or_invalid_information == (
        "schema.outcome_not_numeric",
        "outcome.zero_variance",
        "sample.total_insufficient",
        "sample.arm_insufficient",
    )


def test_invalid_request_payload_becomes_owned_diagnostic_without_rejected_value() -> None:
    payload = _eligible_request().model_dump(mode="json")
    rejected_value = payload["treatment"]["assignment_value"]
    payload["control"]["assignment_value"] = rejected_value

    result = AnalysisEligibilityService().validate_payload(
        payload,
        _eligible_table(),
        _eligible_binding(),
    )

    assert result.status is AnalysisStatus.INELIGIBLE
    assert result.diagnostics[0].code == "request.contract_invalid"
    context: Mapping[str, object] = {
        entry.key: entry.value for entry in result.diagnostics[0].context
    }
    assert set(context) == {"error_count", "error_locations", "error_types"}
    assert rejected_value not in context.values()


def test_validation_result_round_trips_through_public_decoder() -> None:
    result = _implemented_service().validate(
        _eligible_request(),
        _eligible_table(),
        _eligible_binding(),
    )

    assert eligibility_validation_result_from_json(to_canonical_json(result)) == result


def test_ineligible_validation_result_round_trips_through_public_decoder() -> None:
    result = AnalysisEligibilityService().validate(
        _eligible_request(),
        _eligible_table(),
        _eligible_binding(),
    )

    assert result.status is AnalysisStatus.INELIGIBLE
    assert eligibility_validation_result_from_json(to_canonical_json(result)) == result


def test_needs_more_data_validation_result_round_trips_through_public_decoder() -> None:
    result = _implemented_service().validate(
        _eligible_request(),
        _eligible_table(row_count=6),
        _eligible_binding(),
    )

    assert result.status is AnalysisStatus.NEEDS_MORE_DATA
    assert eligibility_validation_result_from_json(to_canonical_json(result)) == result
