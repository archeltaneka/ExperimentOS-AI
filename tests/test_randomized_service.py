"""Request-driven orchestration tests for unadjusted randomized analysis."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from packages.experiments.analysis import (
    AnalysisRequest,
    AnalysisUnit,
    EstimandDefinition,
    EstimandKind,
    MetricType,
    RequestedConfidenceLevel,
    RequestedCredibleLevel,
    SampleCounts,
)
from packages.experiments.analysis.randomized import (
    AlternativeHypothesis,
    ComputationStatus,
    RandomizedAnalysisExecutionRequest,
    RandomizedAnalysisService,
    RandomizedTestType,
)
from packages.experiments.analysis.validation import (
    AnalysisDataBinding,
    AnalysisTable,
    OutcomeDataBinding,
)
from tests.analysis_contract_fixtures import randomized_request, source


def _request(metric_type: MetricType, *, confidence_level: float = 0.95) -> AnalysisRequest:
    request = randomized_request(
        uncertainty=RequestedConfidenceLevel(level=confidence_level),
    )
    unit = AnalysisUnit(unit_id="account", label="Account")
    estimand = (
        EstimandKind.DIFFERENCE_IN_PROPORTIONS
        if metric_type is MetricType.BINARY
        else EstimandKind.DIFFERENCE_IN_MEANS
    )
    outcome = request.outcome.model_copy(
        update={"metric": request.outcome.metric.model_copy(update={"metric_type": metric_type})}
    )
    return request.model_copy(
        update={
            "estimand": EstimandDefinition(kind=estimand),
            "outcome": outcome,
            "sample_counts": SampleCounts(total=40, treatment=20, control=20),
            "unit_of_analysis": unit,
        }
    )


def _table(treatment: Sequence[object], control: Sequence[object]) -> AnalysisTable:
    rows = tuple(
        (f"treatment-{index}", "treatment", value)
        for index, value in enumerate(treatment)
    ) + tuple(
        (f"control-{index}", "control", value)
        for index, value in enumerate(control)
    )
    return AnalysisTable(columns=("unit_id", "arm", "outcome"), rows=rows)


def _binding() -> AnalysisDataBinding:
    return AnalysisDataBinding(
        treatment_column="arm",
        outcome=OutcomeDataBinding(value_column="outcome"),
        observation_unit_column="unit_id",
        randomization_unit_column="unit_id",
    )


def _execution_request(
    analysis_request: AnalysisRequest,
    alternative: AlternativeHypothesis = AlternativeHypothesis.TWO_SIDED,
) -> RandomizedAnalysisExecutionRequest:
    return RandomizedAnalysisExecutionRequest(
        request_id="request-091",
        analysis_request=analysis_request,
        alternative=alternative,
    )


def test_service_runs_eligible_continuous_request_through_welch() -> None:
    request = _request(MetricType.CONTINUOUS, confidence_level=0.90)
    treatment = tuple(float(value) for value in range(11, 31))
    control = tuple(float(value) for value in range(1, 21))

    result = RandomizedAnalysisService().analyze(
        _execution_request(request),
        _table(treatment, control),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is ComputationStatus.COMPLETED
    assert result.analysis_request == request
    assert result.test_result is not None
    assert result.test_result.test_type is RandomizedTestType.WELCH_T
    assert result.test_result.confidence_interval.confidence_level == pytest.approx(0.90)
    assert result.point_effect is not None
    assert result.point_effect.absolute_effect.value == pytest.approx(10.0)
    assert result.hypothesis.alternative is AlternativeHypothesis.TWO_SIDED
    assert any(item.code.startswith("eligibility.") for item in result.diagnostics)


def test_service_contracts_are_exported_from_analysis_boundary() -> None:
    from packages.experiments.analysis import (
        RandomizedAnalysisExecutionRequest as ExportedExecutionRequest,
    )
    from packages.experiments.analysis import RandomizedAnalysisService as ExportedService

    assert ExportedExecutionRequest is RandomizedAnalysisExecutionRequest
    assert ExportedService is RandomizedAnalysisService


def test_service_runs_eligible_binary_request_through_two_proportion_z() -> None:
    request = _request(MetricType.BINARY)
    treatment = (1,) * 14 + (0,) * 6
    control = (1,) * 8 + (0,) * 12

    result = RandomizedAnalysisService().analyze(
        _execution_request(request),
        _table(treatment, control),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is ComputationStatus.COMPLETED
    assert result.analysis_request == request
    assert result.test_result is not None
    assert result.test_result.test_type is RandomizedTestType.TWO_PROPORTION_Z
    assert result.point_effect is not None
    assert result.point_effect.absolute_effect.value == pytest.approx(0.30)


@pytest.mark.parametrize(
    "alternative",
    [AlternativeHypothesis.GREATER_THAN, AlternativeHypothesis.LESS_THAN],
)
def test_service_rejects_declared_one_sided_alternative(
    alternative: AlternativeHypothesis,
) -> None:
    request = _request(MetricType.CONTINUOUS)

    result = RandomizedAnalysisService().analyze(
        _execution_request(request, alternative),
        _table(range(11, 31), range(1, 21)),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is ComputationStatus.UNSUPPORTED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "unsupported_alternative_hypothesis"
    assert result.assumptions
    assert result.point_effect is None
    assert result.test_result is None


def test_service_translates_eligibility_failure_without_estimating() -> None:
    request = _request(MetricType.CONTINUOUS)
    repeated_table = AnalysisTable(
        columns=("unit_id", "arm", "outcome"),
        rows=(("same-unit", "treatment", 1.0),) * 20
        + (("same-unit", "control", 0.0),) * 20,
    )

    result = RandomizedAnalysisService().analyze(
        _execution_request(request),
        repeated_table,
        _binding(),
        provenance=(source(),),
    )

    assert result.status is ComputationStatus.ABSTAINED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code.startswith("eligibility.")
    assert result.treatment_summary is None
    assert result.control_summary is None
    assert result.point_effect is None
    assert result.test_result is None


def test_service_abstains_explicitly_instead_of_dropping_incomplete_outcomes() -> None:
    request = _request(MetricType.CONTINUOUS)
    treatment = tuple(float(value) for value in range(11, 31))
    control: tuple[object, ...] = (None,) + tuple(float(value) for value in range(2, 21))

    result = RandomizedAnalysisService().analyze(
        _execution_request(request),
        _table(treatment, control),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is ComputationStatus.ABSTAINED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "incomplete_outcome_data"
    assert result.point_effect is None
    assert result.test_result is None


def test_service_is_deterministic_row_order_invariant_and_does_not_mutate_inputs() -> None:
    request = _request(MetricType.CONTINUOUS)
    table = _table(range(11, 31), range(1, 21))
    reversed_table = AnalysisTable(columns=table.columns, rows=tuple(reversed(table.rows)))
    before = table.rows
    service = RandomizedAnalysisService()

    first = service.analyze(
        _execution_request(request), table, _binding(), provenance=(source(),)
    )
    repeated = service.analyze(
        _execution_request(request), table, _binding(), provenance=(source(),)
    )
    reordered = service.analyze(
        _execution_request(request), reversed_table, _binding(), provenance=(source(),)
    )

    assert first.model_dump_json() == repeated.model_dump_json()
    assert first.model_dump_json() == reordered.model_dump_json()
    assert table.rows == before
    assert "NaN" not in first.model_dump_json()
    assert "Infinity" not in first.model_dump_json()


def test_service_records_complete_unverified_assumptions_and_request_provenance() -> None:
    request = _request(MetricType.CONTINUOUS)

    result = RandomizedAnalysisService().analyze(
        _execution_request(request),
        _table(range(11, 31), range(1, 21)),
        _binding(),
        provenance=(source(),),
    )

    assert {assumption.code for assumption in result.assumptions} == {
        "random_assignment",
        "treatment_control_consistency",
        "stable_unit_treatment_value",
        "no_interference",
        "compatible_analysis_randomization_units",
        "independent_supported_units",
        "valid_outcome_measurement",
        "fixed_horizon_analysis",
        "no_uncorrected_repeated_peeking",
    }
    request_sources = [
        item for item in result.provenance if item.source_type.value == "analysis_request"
    ]
    assert len(request_sources) == 1
    assert request_sources[0].source_id == "request-091"
    assert request_sources[0].source_version == "alternative=two_sided"


def test_service_rejects_credible_uncertainty_without_frequentist_inference() -> None:
    request = _request(MetricType.CONTINUOUS).model_copy(
        update={"uncertainty": RequestedCredibleLevel(level=0.95)}
    )

    result = RandomizedAnalysisService().analyze(
        _execution_request(request),
        _table(range(11, 31), range(1, 21)),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is ComputationStatus.UNSUPPORTED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "unsupported_uncertainty"
    assert result.test_result is None


@pytest.mark.parametrize(
    ("metric_type", "estimand", "expected_code"),
    [
        (MetricType.COUNT, EstimandKind.DIFFERENCE_IN_MEANS, "unsupported_outcome_type"),
        (
            MetricType.CONTINUOUS,
            EstimandKind.AVERAGE_TREATMENT_EFFECT_ON_TREATED,
            "incompatible_estimand",
        ),
    ],
)
def test_service_rejects_unsupported_outcomes_and_estimands(
    metric_type: MetricType,
    estimand: EstimandKind,
    expected_code: str,
) -> None:
    request = _request(metric_type).model_copy(
        update={"estimand": EstimandDefinition(kind=estimand)}
    )

    result = RandomizedAnalysisService().analyze(
        _execution_request(request),
        _table(range(11, 31), range(1, 21)),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is ComputationStatus.UNSUPPORTED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == expected_code
    assert result.point_effect is None
    assert result.test_result is None
    assert any(item.code.startswith("eligibility.") for item in result.diagnostics)
