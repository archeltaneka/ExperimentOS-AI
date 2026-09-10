"""Identification, modifier, and complete-case validation for HTE."""

from __future__ import annotations

import pytest

from packages.experiments.analysis.causal import MeasurementTiming
from packages.experiments.analysis.causal.hte import (
    HTEModifierDerivation,
    HTEPreSpecificationStatus,
    HTERegistrationStatus,
)
from packages.experiments.analysis.causal.hte.validation import (
    HTEValidationDisposition,
    validate_hte_input,
)
from tests.hte_fixtures import hte_execution, hte_identification, hte_modifier, hte_table
from tests.test_hte_assignment import _rows


def test_valid_input_attributes_complete_case_exclusions_to_subgroups() -> None:
    result = validate_hte_input(hte_execution(), hte_table(_rows()))

    assert result.disposition is HTEValidationDisposition.VALID
    assert tuple(row.subgroup_id for row in result.rows) == ("id", "sg", "id", "sg")
    assert result.feature_names == ("prior_orders", "country::sg")
    assert tuple(
        (item.subgroup_id, item.raw_count, item.retained_count, item.dropped_count)
        for item in result.subgroup_counts
    ) == (("id", 3, 2, 1), ("sg", 2, 2, 0))
    assert result.unassigned_count == 1


@pytest.mark.parametrize(
    ("modifier", "code"),
    [
        (hte_modifier(timing=MeasurementTiming.POST_TREATMENT), "hte.modifier.post_treatment"),
        (hte_modifier(timing=MeasurementTiming.UNKNOWN), "hte.modifier.unknown_timing"),
        (
            hte_modifier(derivation=HTEModifierDerivation.OUTCOME_DERIVED),
            "hte.modifier.outcome_derived",
        ),
        (
            hte_modifier(derivation=HTEModifierDerivation.TREATMENT_DERIVED),
            "hte.modifier.treatment_derived",
        ),
        (
            hte_modifier(
                pre_specification=HTEPreSpecificationStatus.EXPLORATORY,
                registration=HTERegistrationStatus.UNREGISTERED,
            ),
            "hte.modifier.exploratory",
        ),
    ],
)
def test_ineligible_modifier_definitions_abstain_before_cross_fitting(modifier, code: str) -> None:
    result = validate_hte_input(hte_execution(modifier=modifier), hte_table(_rows()))

    assert result.disposition in {
        HTEValidationDisposition.INVALID,
        HTEValidationDisposition.ABSTAINED,
    }
    assert result.rows == ()
    assert result.diagnostics[0].code == code


def test_identification_timing_failure_is_blocking() -> None:
    result = validate_hte_input(
        hte_execution(
            identification_result=hte_identification(
                modifier_timing=MeasurementTiming.POST_TREATMENT
            )
        ),
        hte_table(_rows()),
    )

    assert result.disposition is HTEValidationDisposition.INVALID
    assert result.rows == ()
    assert result.diagnostics[0].code == "hte.identification.invalid"
