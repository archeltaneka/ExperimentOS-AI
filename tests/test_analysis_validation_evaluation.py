from __future__ import annotations

from collections.abc import Mapping
from dataclasses import FrozenInstanceError, replace
from datetime import datetime

import pytest

from packages.evals import analysis_validation_cases as validation_cases_module
from packages.evals.analysis_validation_cases import (
    ValidationGoldenCase,
    build_validation_golden_cases,
    evaluate_validation_golden_cases,
)
from packages.experiments.analysis import (
    AnalysisStatus,
    CovariateTiming,
    RandomizedExperimentDesign,
)

EXPECTED_CASES = (
    ("valid-randomized", AnalysisStatus.ELIGIBLE, frozenset()),
    (
        "missing-treatment-column",
        AnalysisStatus.INELIGIBLE,
        frozenset(
            {
                "schema.required_column_missing",
                "schema.dependent_rules_unavailable",
            }
        ),
    ),
    (
        "missing-outcome",
        AnalysisStatus.INELIGIBLE,
        frozenset(
            {
                "schema.required_column_missing",
                "schema.dependent_rules_unavailable",
            }
        ),
    ),
    (
        "empty-dataset",
        AnalysisStatus.INELIGIBLE,
        frozenset({"schema.empty_dataset", "schema.dependent_rules_unavailable"}),
    ),
    (
        "empty-treatment-arm",
        AnalysisStatus.INELIGIBLE,
        frozenset({"treatment.arm_missing", "sample.arm_insufficient"}),
    ),
    (
        "empty-control-arm",
        AnalysisStatus.INELIGIBLE,
        frozenset({"treatment.arm_missing", "sample.arm_insufficient"}),
    ),
    (
        "unexpected-treatment-arm",
        AnalysisStatus.INELIGIBLE,
        frozenset({"treatment.unexpected_value"}),
    ),
    (
        "invalid-binary-outcome",
        AnalysisStatus.INELIGIBLE,
        frozenset({"outcome.invalid_binary"}),
    ),
    (
        "non-finite-continuous-outcome",
        AnalysisStatus.INELIGIBLE,
        frozenset({"outcome.non_finite"}),
    ),
    (
        "duplicate-randomization-unit",
        AnalysisStatus.INELIGIBLE,
        frozenset({"unit.duplicate_observation"}),
    ),
    (
        "unit-multiple-treatments",
        AnalysisStatus.INELIGIBLE,
        frozenset({"treatment.unit_multiple_assignments"}),
    ),
    (
        "post-treatment-leakage",
        AnalysisStatus.INELIGIBLE,
        frozenset({"covariate.post_treatment_leakage"}),
    ),
    (
        "insufficient-total",
        AnalysisStatus.NEEDS_MORE_DATA,
        frozenset({"sample.total_insufficient"}),
    ),
    (
        "insufficient-arm",
        AnalysisStatus.NEEDS_MORE_DATA,
        frozenset({"sample.arm_insufficient"}),
    ),
    (
        "outcome-missingness",
        AnalysisStatus.INELIGIBLE,
        frozenset({"missingness.outcome_exceeds_threshold"}),
    ),
    (
        "invalid-pre-post",
        AnalysisStatus.INELIGIBLE,
        frozenset({"request.contract_invalid"}),
    ),
    (
        "missing-cluster",
        AnalysisStatus.INELIGIBLE,
        frozenset(
            {
                "unit.randomization_identifier_missing",
                "unit.cluster_identifier_missing",
            }
        ),
    ),
    (
        "invalid-segment",
        AnalysisStatus.INELIGIBLE,
        frozenset({"segment.criteria_incompatible"}),
    ),
    (
        "segment-missing-arm",
        AnalysisStatus.NEEDS_MORE_DATA,
        frozenset({"segment.arm_missing"}),
    ),
    (
        "estimator-unavailable",
        AnalysisStatus.INELIGIBLE,
        frozenset({"method.implementation_unavailable"}),
    ),
    (
        "eligible-with-warnings",
        AnalysisStatus.ELIGIBLE_WITH_WARNINGS,
        frozenset({"sample.total_weak", "sample.arm_weak"}),
    ),
    ("fully-eligible", AnalysisStatus.ELIGIBLE, frozenset()),
)


def test_golden_inventory_covers_required_validation_cases() -> None:
    cases = build_validation_golden_cases()

    assert tuple(case.case_id for case in cases) == tuple(item[0] for item in EXPECTED_CASES)
    assert len({case.case_id for case in cases}) == len(cases)
    assert (
        tuple(
            (case.case_id, case.expected_status, case.expected_diagnostic_codes) for case in cases
        )
        == EXPECTED_CASES
    )


def test_golden_case_contract_is_frozen_and_every_case_owns_its_inputs() -> None:
    first = build_validation_golden_cases()
    second = build_validation_golden_cases()

    with pytest.raises(FrozenInstanceError):
        first[0].case_id = "changed"
    for attribute in ("table", "binding", "policy", "capability_registry"):
        assert len({id(getattr(case, attribute)) for case in first}) == len(first)
        assert all(
            getattr(left, attribute) is not getattr(right, attribute)
            for left, right in zip(first, second, strict=True)
        )
    for left, right in zip(first, second, strict=True):
        assert (left.request is None) != (left.request_payload is None)
        if left.request is not None:
            assert left.request is not right.request
        else:
            assert left.request_payload is not right.request_payload
    assert first == second


def test_golden_evaluation_is_deterministic_and_asserts_every_status_and_code() -> None:
    cases = build_validation_golden_cases()
    first = evaluate_validation_golden_cases(cases)
    second = evaluate_validation_golden_cases(build_validation_golden_cases())

    assert first == second
    assert tuple(result.case_id for result in first) == tuple(item[0] for item in EXPECTED_CASES)
    assert len(first) == len(EXPECTED_CASES)
    for case, result, (_, expected_status, expected_codes) in zip(
        cases,
        first,
        EXPECTED_CASES,
        strict=True,
    ):
        assert result.expected_status is expected_status
        assert result.actual_status is expected_status
        assert result.expected_diagnostic_codes == tuple(sorted(expected_codes))
        assert result.actual_diagnostic_codes == tuple(sorted(expected_codes))
        assert result.missing_diagnostic_codes == ()
        assert result.unexpected_diagnostic_codes == ()
        assert result.status_matches is True
        assert result.codes_match is True
        assert result.passed is True
        assert case.expected_status is expected_status
        assert case.expected_diagnostic_codes == expected_codes


def test_evaluator_does_not_mutate_cases_or_caller_tables() -> None:
    cases = build_validation_golden_cases()
    original_cases = tuple(cases)
    original_tables = tuple((case.table.columns, case.table.rows) for case in cases)

    evaluate_validation_golden_cases(cases)

    assert cases == original_cases
    assert tuple((case.table.columns, case.table.rows) for case in cases) == original_tables


def test_evaluator_reports_wrong_status_and_code_expectations_structurally() -> None:
    valid = build_validation_golden_cases()[0]
    wrong_status = replace(valid, expected_status=AnalysisStatus.INELIGIBLE)
    wrong_codes = replace(
        valid,
        case_id="valid-randomized-wrong-codes",
        expected_diagnostic_codes=frozenset({"schema.not_a_real_diagnostic"}),
    )

    status_result, codes_result = evaluate_validation_golden_cases((wrong_status, wrong_codes))

    assert status_result.status_matches is False
    assert status_result.codes_match is True
    assert status_result.passed is False
    assert codes_result.status_matches is True
    assert codes_result.codes_match is False
    assert codes_result.missing_diagnostic_codes == ("schema.not_a_real_diagnostic",)
    assert codes_result.unexpected_diagnostic_codes == ()
    assert codes_result.passed is False


def test_valid_randomized_and_fully_eligible_have_distinct_data_intent() -> None:
    cases_by_id: dict[str, ValidationGoldenCase] = {
        case.case_id: case for case in build_validation_golden_cases()
    }
    compact = cases_by_id["valid-randomized"]
    full = cases_by_id["fully-eligible"]

    assert compact.request.outcome.metric.metric_type != full.request.outcome.metric.metric_type
    assert len(compact.table.rows) < len(full.table.rows)
    assert compact.policy != full.policy


def test_invalid_pre_post_owns_an_overlapping_raw_payload() -> None:
    case = next(
        case for case in build_validation_golden_cases() if case.case_id == "invalid-pre-post"
    )

    assert case.request is None
    assert case.request_payload is not None
    design = case.request_payload["study_design"]
    assert isinstance(design, Mapping)
    pre_period = design["pre_treatment_period"]
    post_period = design["post_treatment_period"]
    assert isinstance(pre_period, Mapping)
    assert isinstance(post_period, Mapping)
    pre_end = datetime.fromisoformat(str(pre_period["end"]))
    post_start = datetime.fromisoformat(str(post_period["start"]))
    assert pre_end > post_start
    with pytest.raises(TypeError):
        case.request_payload["study_design"] = {}


def test_invalid_pre_post_evaluation_routes_through_payload_boundary(monkeypatch) -> None:
    case = next(
        case for case in build_validation_golden_cases() if case.case_id == "invalid-pre-post"
    )
    calls: list[Mapping[str, object]] = []
    validate_payload = validation_cases_module.AnalysisEligibilityService.validate_payload

    def recording_validate_payload(
        service,
        payload,
        table,
        binding,
    ):
        calls.append(payload)
        return validate_payload(service, payload, table, binding)

    monkeypatch.setattr(
        validation_cases_module.AnalysisEligibilityService,
        "validate_payload",
        recording_validate_payload,
    )

    result = evaluate_validation_golden_cases((case,))[0]

    assert calls == [case.request_payload]
    assert result.actual_status is AnalysisStatus.INELIGIBLE
    assert result.actual_diagnostic_codes == ("request.contract_invalid",)
    assert "2026-07-10" not in repr(result)


def test_golden_case_requires_exactly_one_request_input() -> None:
    cases = build_validation_golden_cases()
    valid = cases[0]
    invalid = next(case for case in cases if case.case_id == "invalid-pre-post")

    with pytest.raises(ValueError, match="exactly one"):
        replace(valid, request_payload={"schema_version": "1"})
    with pytest.raises(ValueError, match="exactly one"):
        replace(invalid, request_payload=None)


def test_post_treatment_leakage_period_and_evidence_follow_assignment() -> None:
    case = next(
        case for case in build_validation_golden_cases() if case.case_id == "post-treatment-leakage"
    )

    assert case.request is not None
    design = case.request.study_design
    assert isinstance(design, RandomizedExperimentDesign)
    covariate = case.request.covariates[0]
    assert covariate.timing is CovariateTiming.POST_TREATMENT
    assert covariate.measurement_period.start > design.experiment_period.start
    covariate_index = case.table.columns.index("prior_count")
    timestamp_index = case.table.columns.index("observed_at")
    evidence_timestamps = tuple(
        datetime.fromisoformat(str(row[timestamp_index]).replace("Z", "+00:00"))
        for row in case.table.rows
        if row[covariate_index] is not None
    )
    assert evidence_timestamps
    assert all(
        covariate.measurement_period.start <= timestamp < covariate.measurement_period.end
        for timestamp in evidence_timestamps
    )
    assert all(timestamp > design.experiment_period.start for timestamp in evidence_timestamps)
