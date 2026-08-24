"""Diagnostic-only extra pre-period behavior for bounded DiD."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.experiments.analysis import TimePeriod
from packages.experiments.analysis.causal import CausalAssumptionCode
from packages.experiments.analysis.causal.did import (
    DidPretrendAvailability,
    DifferenceInDifferencesExecutionRequest,
)
from packages.experiments.analysis.causal.did.pretrends import evaluate_pretrend
from packages.experiments.analysis.causal.did.validation import (
    DidValidationDisposition,
    validate_did_input,
)
from tests.did_fixtures import (
    add_extra_pre_rows,
    at,
    did_binding,
    did_execution,
    did_request,
    did_table,
    extra_pre_periods,
    positive_effect_rows,
)


def test_no_extra_periods_is_explicitly_not_requested() -> None:
    execution = did_execution()
    validated = validate_did_input(execution, did_table(positive_effect_rows()))

    diagnostic = evaluate_pretrend(validated, execution)

    assert diagnostic.availability is DidPretrendAvailability.NOT_REQUESTED
    assert diagnostic.period_count == 0
    assert "proof" not in diagnostic.message.lower()


def test_one_extra_period_is_insufficient_but_does_not_block_att() -> None:
    periods = extra_pre_periods()[:1]
    rows = add_extra_pre_rows(
        positive_effect_rows(),
        treated_means=(8.0, 9.0),
        control_means=(6.0, 7.0),
    )
    rows = tuple(row for row in rows if row["observed_at"] != extra_pre_periods()[1].start)
    execution = did_execution(extra_pre_periods=periods)
    validated = validate_did_input(execution, did_table(rows))

    diagnostic = evaluate_pretrend(validated, execution)

    assert validated.observations
    assert diagnostic.availability is DidPretrendAvailability.UNAVAILABLE
    assert diagnostic.period_count == 2
    assert "at least three" in diagnostic.message.lower()


def test_overlapping_or_unordered_extra_periods_are_rejected() -> None:
    first, second = extra_pre_periods()
    overlapping = TimePeriod(start=first.start, end=second.end)

    with pytest.raises(ValidationError, match="ordered and non-overlapping"):
        DifferenceInDifferencesExecutionRequest(
            analysis_request=did_request(),
            binding=did_binding(),
            extra_pre_periods=(overlapping, first),
        )
    with pytest.raises(ValidationError, match="end before the canonical pre-period"):
        DifferenceInDifferencesExecutionRequest(
            analysis_request=did_request(),
            binding=did_binding(),
            extra_pre_periods=(TimePeriod(start=at(1), end=at(2)),),
        )


def test_parallel_looking_pretrends_are_evidence_not_proof() -> None:
    execution = did_execution(extra_pre_periods=extra_pre_periods())
    rows = add_extra_pre_rows(
        positive_effect_rows(),
        treated_means=(6.0, 8.0),
        control_means=(4.0, 6.0),
    )
    validated = validate_did_input(execution, did_table(rows))
    original_parallel = next(
        item
        for item in execution.analysis_request.identification.assumptions
        if item.code is CausalAssumptionCode.PARALLEL_TRENDS
    )

    diagnostic = evaluate_pretrend(validated, execution)

    assert diagnostic.availability is DidPretrendAvailability.AVAILABLE
    assert diagnostic.period_count == 3
    assert diagnostic.trend_difference == pytest.approx(0.0, abs=1e-12)
    assert diagnostic.p_value is not None
    assert diagnostic.p_value > 0.05
    assert "evidence" in diagnostic.message.lower()
    assert "proven" not in diagnostic.message.lower()
    assert "verified" not in diagnostic.message.lower()
    assert original_parallel.status.value == "asserted"


def test_divergent_pretrends_surface_warning_evidence() -> None:
    execution = did_execution(extra_pre_periods=extra_pre_periods())
    rows = add_extra_pre_rows(
        positive_effect_rows(),
        treated_means=(-6.0, 2.0),
        control_means=(6.0, 7.0),
    )
    validated = validate_did_input(execution, did_table(rows))

    diagnostic = evaluate_pretrend(validated, execution)

    assert diagnostic.availability is DidPretrendAvailability.AVAILABLE
    assert diagnostic.trend_difference == pytest.approx(7.0, abs=1e-12)
    assert diagnostic.p_value is not None
    assert diagnostic.p_value < 0.05
    assert diagnostic.evidence_concern is True
    assert "proof" not in diagnostic.message.lower()


def test_incomplete_extra_period_coverage_is_unavailable_not_filtered() -> None:
    execution = did_execution(extra_pre_periods=extra_pre_periods())
    rows = list(
        add_extra_pre_rows(
            positive_effect_rows(),
            treated_means=(6.0, 8.0),
            control_means=(4.0, 6.0),
        )
    )
    rows.pop(0)
    validated = validate_did_input(execution, did_table(tuple(rows)))

    diagnostic = evaluate_pretrend(validated, execution)

    assert len(validated.observations) == 40
    assert validated.sample_counts.retained_units == 20
    assert diagnostic.availability is DidPretrendAvailability.UNAVAILABLE
    assert "complete" in diagnostic.message.lower()


def test_extra_pre_period_early_exposure_invalidates_no_anticipation() -> None:
    execution = did_execution(extra_pre_periods=extra_pre_periods())
    rows = list(
        add_extra_pre_rows(
            positive_effect_rows(),
            treated_means=(6.0, 8.0),
            control_means=(4.0, 6.0),
        )
    )
    treated_extra = next(
        row
        for row in rows
        if row["group"] == "treated" and row["observed_at"] == extra_pre_periods()[0].start
    )
    treated_extra["exposed"] = 1

    validated = validate_did_input(execution, did_table(tuple(rows)))

    assert validated.disposition is DidValidationDisposition.INVALID
    assert "did.anticipatory_exposure" in {item.code for item in validated.diagnostics}


def test_extra_pre_period_group_switch_is_not_ignored() -> None:
    execution = did_execution(extra_pre_periods=extra_pre_periods())
    rows = list(
        add_extra_pre_rows(
            positive_effect_rows(),
            treated_means=(6.0, 8.0),
            control_means=(4.0, 6.0),
        )
    )
    treated_extra = next(
        row
        for row in rows
        if row["group"] == "treated" and row["observed_at"] == extra_pre_periods()[0].start
    )
    treated_extra["group"] = "control"

    validated = validate_did_input(execution, did_table(tuple(rows)))

    assert validated.disposition is DidValidationDisposition.INVALID
    assert "did.group_switching" in {item.code for item in validated.diagnostics}
