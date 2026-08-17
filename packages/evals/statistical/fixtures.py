"""Deterministic Phase 4 inputs used only by the repository-owned baseline."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel

from packages.evals.analysis_validation_cases import (
    ValidationGoldenCase,
    build_validation_golden_cases,
)
from packages.experiments.analysis import (
    AnalysisEligibilityService,
    AnalysisTable,
    ProvenanceRecord,
    ProvenanceSourceType,
)
from packages.experiments.analysis.descriptive import (
    DescriptiveStatisticsInput,
    DescriptiveStatisticsService,
)
from packages.experiments.analysis.randomized import (
    AlternativeHypothesis,
    RandomizedAnalysisExecutionRequest,
    RandomizedAnalysisService,
)
from packages.experiments.analysis.validation.context import ValidationContext
from packages.observability.base import BaseObservabilityProvider

from .models import StatisticalReferenceCase
from .randomized_fixtures import run_randomized_inference_fixture


def run_statistical_fixture(
    case: StatisticalReferenceCase,
    *,
    reverse_rows: bool = False,
    observability_provider: BaseObservabilityProvider | None = None,
) -> BaseModel:
    """Execute one named fixture through the existing Phase 4 service boundary."""
    if case.fixture_id.endswith("_validation"):
        return _run_validation(case.fixture_id, reverse_rows, observability_provider)
    if case.fixture_id.startswith("descriptive_"):
        return _run_descriptive(case.fixture_id, reverse_rows, observability_provider)
    if case.fixture_id.startswith("randomized_"):
        return _run_randomized(case.fixture_id, reverse_rows, observability_provider)
    if case.fixture_id.startswith(("cuped_", "sequential_", "bayesian_")):
        return run_randomized_inference_fixture(
            case.fixture_id,
            reverse_rows=reverse_rows,
            observability_provider=observability_provider,
        )
    raise ValueError(f"unknown statistical fixture_id: {case.fixture_id}")


def _validation_cases() -> dict[str, ValidationGoldenCase]:
    return {case.case_id: case for case in build_validation_golden_cases()}


def _run_validation(
    fixture_id: str,
    reverse_rows: bool,
    provider: BaseObservabilityProvider | None,
) -> BaseModel:
    cases = _validation_cases()
    source_id = {
        "valid_continuous_validation": "fully-eligible",
        "missing_treatment_arm_validation": "empty-treatment-arm",
        "nonfinite_outcome_validation": "non-finite-continuous-outcome",
        "malformed_request_validation": "valid-randomized",
    }[fixture_id]
    case = cases[source_id]
    table = _ordered_table(case.table, reverse_rows)
    service = AnalysisEligibilityService(
        policy=case.policy,
        capability_registry=case.capability_registry,
        configuration_provenance=f"statistical-baseline:{fixture_id}",
        observability_provider=provider,
    )
    if fixture_id == "malformed_request_validation":
        return service.validate_payload({"study_design": {}}, table, case.binding)
    if case.request is None:
        raise RuntimeError(f"validation fixture {source_id} has no typed request")
    return service.validate(case.request, table, case.binding)


def _run_descriptive(
    fixture_id: str,
    reverse_rows: bool,
    provider: BaseObservabilityProvider | None,
) -> BaseModel:
    cases = _validation_cases()
    compact = cases["valid-randomized"]
    request_case = (
        cases["fully-eligible"]
        if fixture_id == "descriptive_continuous_balanced"
        else cases["valid-randomized"]
    )
    if request_case.request is None:
        raise RuntimeError("descriptive fixture is missing its typed request")
    treatment, control = (
        ((2.0, 4.0, 6.0, 8.0), (1.0, 2.0, 3.0, 4.0))
        if fixture_id == "descriptive_continuous_balanced"
        else ((0, 0, 0, 0, 1, 1, 1, 1, 1, 1), (0, 0, 0, 0, 0, 0, 1, 1, 1, 1))
    )
    table = _arm_table(treatment, control)
    table = _ordered_table(table, reverse_rows)
    service = AnalysisEligibilityService(
        policy=compact.policy,
        capability_registry=compact.capability_registry,
        configuration_provenance=f"statistical-baseline:{fixture_id}",
    )
    eligibility = service.validate(request_case.request, table, request_case.binding)
    context = ValidationContext(
        request=request_case.request,
        table=table,
        binding=request_case.binding,
        policy=compact.policy,
    )
    return DescriptiveStatisticsService(observability_provider=provider).summarize(
        DescriptiveStatisticsInput(context=context, eligibility=eligibility)
    )


def _run_randomized(
    fixture_id: str,
    reverse_rows: bool,
    provider: BaseObservabilityProvider | None,
) -> BaseModel:
    cases = _validation_cases()
    compact = cases["valid-randomized"]
    continuous = cases["fully-eligible"]
    binary = cases["valid-randomized"]
    fixture_type = tuple[
        ValidationGoldenCase,
        Sequence[object],
        Sequence[object],
        AlternativeHypothesis,
    ]
    fixtures: dict[str, fixture_type] = {
        "randomized_continuous_balanced": (
            continuous,
            (3.0, 5.0, 7.0, 9.0, 11.0),
            (2.0, 4.0, 6.0, 8.0, 10.0),
            AlternativeHypothesis.TWO_SIDED,
        ),
        "randomized_binary_balanced": (
            binary,
            (1,) * 12 + (0,) * 8,
            (1,) * 8 + (0,) * 12,
            AlternativeHypothesis.TWO_SIDED,
        ),
        "randomized_continuous_zero_baseline": (
            continuous,
            (1.0, 2.0, 3.0),
            (-1.0, 0.0, 1.0),
            AlternativeHypothesis.TWO_SIDED,
        ),
        "randomized_continuous_zero_variance": (
            continuous,
            (2.0, 2.0),
            (1.0, 1.0),
            AlternativeHypothesis.TWO_SIDED,
        ),
        "randomized_binary_sparse": (
            binary,
            (1, 0, 0, 0, 0),
            (0, 0, 0, 0, 0),
            AlternativeHypothesis.TWO_SIDED,
        ),
        "randomized_continuous_tiny": (
            continuous,
            (2.0,),
            (1.0,),
            AlternativeHypothesis.TWO_SIDED,
        ),
        "randomized_continuous_one_sided": (
            continuous,
            (3.0, 5.0, 7.0, 9.0, 11.0),
            (2.0, 4.0, 6.0, 8.0, 10.0),
            AlternativeHypothesis.GREATER_THAN,
        ),
    }
    request_case, treatment, control, alternative = fixtures[fixture_id]
    request = request_case.request
    if request is None:
        raise RuntimeError(f"randomized fixture {fixture_id} has no typed request")
    table = _ordered_table(_arm_table(treatment, control), reverse_rows)
    service = RandomizedAnalysisService(
        validation_policy=compact.policy,
        observability_provider=provider,
    )
    return service.analyze(
        RandomizedAnalysisExecutionRequest(
            request_id="phase4-statistical-reference",
            analysis_request=request,
            alternative=alternative,
        ),
        table,
        request_case.binding,
        provenance=(
            ProvenanceRecord(
                source_type=ProvenanceSourceType.EXTERNAL_REFERENCE,
                source_id="phase4-statistical-fixtures-v1",
            ),
        ),
    )


def _arm_table(
    treatment: Sequence[object],
    control: Sequence[object],
) -> AnalysisTable:
    rows = tuple(
        (f"treatment-{index}", "treatment", value) for index, value in enumerate(treatment)
    ) + tuple((f"control-{index}", "control", value) for index, value in enumerate(control))
    return AnalysisTable(columns=("unit", "arm", "outcome"), rows=rows)


def _ordered_table(table: AnalysisTable, reverse_rows: bool) -> AnalysisTable:
    if not reverse_rows:
        return table
    return AnalysisTable(columns=table.columns, rows=tuple(reversed(table.rows)))


__all__ = ["run_statistical_fixture"]
