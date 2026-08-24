"""Identification, timing, adoption, and strict-panel validation tests."""

from __future__ import annotations

from datetime import timedelta

import pytest

from packages.experiments.analysis import MetricType
from packages.experiments.analysis.causal import (
    CausalAssumptionCode,
    CausalAssumptionStatus,
)
from packages.experiments.analysis.causal.did.validation import (
    DidValidationDisposition,
    validate_did_input,
)
from tests.did_fixtures import (
    at,
    did_execution,
    did_request,
    did_table,
    positive_effect_rows,
)


def _codes(result: object) -> set[str]:
    return {item.code for item in result.diagnostics}  # type: ignore[attr-defined]


def _replace_row(
    rows: tuple[dict[str, object], ...],
    index: int,
    **updates: object,
) -> tuple[dict[str, object], ...]:
    changed = list(rows)
    changed[index] = {**changed[index], **updates}
    return tuple(changed)


def test_valid_identified_balanced_panel_is_eligible() -> None:
    result = validate_did_input(did_execution(), did_table(positive_effect_rows()))

    assert result.disposition is DidValidationDisposition.VALID
    assert len(result.observations) == 40
    assert result.sample_counts.rows == 40
    assert result.sample_counts.total_units == 20
    assert result.sample_counts.treated_units == 10
    assert result.sample_counts.control_units == 10
    assert result.sample_counts.units_with_both_periods == 20
    assert result.sample_counts.retained_units == 20
    assert result.sample_counts.retention_rate == 1.0
    assert result.diagnostics == ()


def test_partially_identified_request_abstains() -> None:
    candidate = did_request()
    assumptions = tuple(
        item.model_copy(update={"status": CausalAssumptionStatus.UNVERIFIED})
        if item.code is CausalAssumptionCode.PARALLEL_TRENDS
        else item
        for item in candidate.identification.assumptions
    )
    candidate = candidate.model_copy(
        update={
            "identification": candidate.identification.model_copy(
                update={"assumptions": assumptions}
            )
        }
    )

    result = validate_did_input(did_execution(candidate), did_table(positive_effect_rows()))

    assert result.disposition is DidValidationDisposition.ABSTAINED
    assert "did.identification_partially_identified" in _codes(result)


def test_binary_metric_is_unsupported() -> None:
    candidate = did_request()
    outcome = candidate.identification.outcome
    assert outcome is not None
    binary_metric = outcome.metric.metric.model_copy(update={"metric_type": MetricType.BINARY})
    candidate = candidate.model_copy(
        update={
            "identification": candidate.identification.model_copy(
                update={
                    "outcome": outcome.model_copy(
                        update={
                            "metric": outcome.metric.model_copy(
                                update={"metric": binary_metric}
                            )
                        }
                    )
                }
            )
        }
    )

    result = validate_did_input(did_execution(candidate), did_table(positive_effect_rows()))

    assert result.disposition is DidValidationDisposition.UNSUPPORTED
    assert "did.unsupported_metric" in _codes(result)


@pytest.mark.parametrize(
    ("start", "code"),
    (
        (at(9), "did.treatment_too_early"),
        (at(11), "did.treatment_too_late"),
    ),
)
def test_declared_treatment_start_must_fall_between_periods(start: object, code: str) -> None:
    candidate = did_request()
    candidate = candidate.model_copy(
        update={
            "identification": candidate.identification.model_copy(
                update={
                    "time": candidate.identification.time.model_copy(
                        update={"treatment_start": start}
                    )
                }
            )
        }
    )

    result = validate_did_input(did_execution(candidate), did_table(positive_effect_rows()))

    assert result.disposition is DidValidationDisposition.INVALID
    assert code in _codes(result)


def test_reversed_canonical_periods_are_invalid() -> None:
    candidate = did_request()
    time = candidate.identification.time
    candidate = candidate.model_copy(
        update={
            "identification": candidate.identification.model_copy(
                update={
                    "time": time.model_copy(
                        update={"pre_period": time.post_period, "post_period": time.pre_period}
                    )
                }
            )
        }
    )

    result = validate_did_input(did_execution(candidate), did_table(positive_effect_rows()))

    assert result.disposition is DidValidationDisposition.INVALID
    assert "did.reversed_timing" in _codes(result)


@pytest.mark.parametrize(
    ("rows", "code", "disposition"),
    (
        (
            tuple(row for row in positive_effect_rows() if row["group"] != "treated"),
            "did.missing_treated_group",
            DidValidationDisposition.ABSTAINED,
        ),
        (
            tuple(row for row in positive_effect_rows() if row["group"] != "control"),
            "did.missing_control_group",
            DidValidationDisposition.ABSTAINED,
        ),
    ),
)
def test_both_groups_are_required(
    rows: tuple[dict[str, object], ...],
    code: str,
    disposition: DidValidationDisposition,
) -> None:
    result = validate_did_input(did_execution(), did_table(rows))

    assert result.disposition is disposition
    assert code in _codes(result)


def test_group_membership_switch_is_invalid() -> None:
    rows = positive_effect_rows()
    rows = _replace_row(rows, 1, group="control", exposed=0, treatment_start=None)

    result = validate_did_input(did_execution(), did_table(rows))

    assert result.disposition is DidValidationDisposition.INVALID
    assert "did.group_switching" in _codes(result)


def test_staggered_treatment_start_is_invalid() -> None:
    rows = positive_effect_rows()
    rows = tuple(
        {**row, "treatment_start": at(10) + timedelta(hours=1)}
        if row["unit_id"] == "t-01"
        else row
        for row in rows
    )

    result = validate_did_input(did_execution(), did_table(rows))

    assert result.disposition is DidValidationDisposition.INVALID
    assert "did.staggered_adoption" in _codes(result)


def test_treated_reversal_is_invalid() -> None:
    rows = _replace_row(positive_effect_rows(), 1, exposed=0)

    result = validate_did_input(did_execution(), did_table(rows))

    assert result.disposition is DidValidationDisposition.INVALID
    assert "did.treatment_reversal" in _codes(result)


def test_control_adoption_is_invalid() -> None:
    rows = _replace_row(positive_effect_rows(), 21, exposed=1, treatment_start=at(10))

    result = validate_did_input(did_execution(), did_table(rows))

    assert result.disposition is DidValidationDisposition.INVALID
    assert "did.control_adoption" in _codes(result)


@pytest.mark.parametrize(
    ("drop_index", "code", "missing_field"),
    (
        (1, "did.incomplete_unit_coverage", "units_missing_post"),
        (20, "did.incomplete_unit_coverage", "units_missing_pre"),
    ),
)
def test_unbalanced_panel_abstains_without_filtering(
    drop_index: int,
    code: str,
    missing_field: str,
) -> None:
    rows = list(positive_effect_rows())
    rows.pop(drop_index)

    result = validate_did_input(did_execution(), did_table(tuple(rows)))

    assert result.disposition is DidValidationDisposition.ABSTAINED
    assert code in _codes(result)
    assert getattr(result.sample_counts, missing_field) == 1
    assert result.sample_counts.retained_units == 19
    assert result.sample_counts.excluded_units == 1
    assert result.sample_counts.retention_rate == 0.95


def test_post_only_entry_is_reported_as_composition_change() -> None:
    rows = positive_effect_rows() + (
        {
            "unit_id": "t-new",
            "observed_at": at(15),
            "group": "treated",
            "exposed": 1,
            "treatment_start": at(10),
            "outcome": 15.0,
        },
    )

    result = validate_did_input(did_execution(), did_table(rows))

    assert result.disposition is DidValidationDisposition.ABSTAINED
    assert {"did.composition_change", "did.incomplete_unit_coverage"} <= _codes(result)
    assert result.sample_counts.units_missing_pre == 1


def test_duplicate_unit_period_is_invalid() -> None:
    rows = positive_effect_rows() + (dict(positive_effect_rows()[0]),)

    result = validate_did_input(did_execution(), did_table(rows))

    assert result.disposition is DidValidationDisposition.INVALID
    assert "did.duplicate_unit_period" in _codes(result)


@pytest.mark.parametrize("value", (None, float("nan"), float("inf")))
def test_missing_or_nonfinite_outcome_never_becomes_zero(value: object) -> None:
    rows = _replace_row(positive_effect_rows(), 0, outcome=value)

    result = validate_did_input(did_execution(), did_table(rows))

    expected = (
        DidValidationDisposition.ABSTAINED
        if value is None
        else DidValidationDisposition.INVALID
    )
    assert result.disposition is expected
    assert (
        "did.missing_outcome" if value is None else "did.nonfinite_outcome"
    ) in _codes(result)
    assert result.sample_counts.treated_missing_pre_outcomes == 1
