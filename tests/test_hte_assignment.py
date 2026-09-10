"""Deterministic subgroup assignment tests."""

from __future__ import annotations

import pytest

from packages.experiments.analysis.causal import MeasurementTiming, VariableRole
from packages.experiments.analysis.causal.hte import (
    ContinuousBinSubgroup,
    EffectModifierDefinition,
    HTEModifierDerivation,
    HTEModifierType,
    HTEPreSpecificationStatus,
    HTERegistrationStatus,
)
from packages.experiments.analysis.causal.hte.assignment import assign_subgroups
from tests.causal_identification_fixtures import provenance
from tests.hte_fixtures import hte_execution, hte_modifier, hte_table


def _rows() -> tuple[dict[str, object], ...]:
    return (
        {"account_id": "a", "treated": 0, "outcome": 1.0, "prior_orders": 0.0, "country": "ID"},
        {"account_id": "b", "treated": 1, "outcome": 2.0, "prior_orders": 1.0, "country": "SG"},
        {"account_id": "c", "treated": 0, "outcome": None, "prior_orders": 2.0, "country": "ID"},
        {"account_id": "d", "treated": 1, "outcome": 4.0, "prior_orders": 3.0, "country": None},
        {"account_id": "e", "treated": 1, "outcome": 5.0, "prior_orders": 4.0, "country": "ID"},
        {"account_id": "f", "treated": 0, "outcome": 6.0, "prior_orders": 5.0, "country": "SG"},
    )


def test_assignment_is_row_order_invariant_and_reports_aggregate_groups() -> None:
    execution = hte_execution()
    first = assign_subgroups(execution, hte_table(_rows()))
    reversed_result = assign_subgroups(execution, hte_table(tuple(reversed(_rows()))))

    assert first.fingerprint_sha256 == reversed_result.fingerprint_sha256
    assert tuple((item.subgroup_id, item.raw_count) for item in first.groups) == (
        ("id", 3),
        ("sg", 2),
    )
    assert first.groups[0].rule == 'country == "ID"'
    assert first.unassigned_count == 1
    assert "account_id" not in repr(first.groups)


def test_continuous_assignment_has_declared_half_open_boundary() -> None:
    source = hte_modifier()
    modifier = EffectModifierDefinition(
        variable_id="country",
        column="country",
        role=VariableRole.EFFECT_MODIFIER,
        measurement_timing=MeasurementTiming.PRE_TREATMENT,
        modifier_type=HTEModifierType.CONTINUOUS_BINNED,
        derivation=HTEModifierDerivation.PREDEFINED_TRANSFORMATION,
        subgroups=(
            ContinuousBinSubgroup(subgroup_id="low", label="Low", lower=None, upper=0.0),
            ContinuousBinSubgroup(subgroup_id="high", label="High", lower=0.0, upper=None),
        ),
        pre_specification=HTEPreSpecificationStatus.CONFIRMATORY_PRE_SPECIFIED,
        registration_status=HTERegistrationStatus.REGISTERED,
        registration_id=source.registration_id,
        definition_provenance=provenance("continuous-definition"),
        registration_provenance=source.registration_provenance,
    )
    rows = tuple(
        {**row, "country": value} for row, value in zip(_rows()[:3], (-1.0, 0.0, 1.0), strict=True)
    )
    result = assign_subgroups(hte_execution(modifier=modifier), hte_table(rows))

    assert tuple((item.subgroup_id, item.raw_count) for item in result.groups) == (
        ("low", 1),
        ("high", 2),
    )
    assert result.groups[0].rule == "country in [-inf, 0.0)"


def test_nonmissing_unregistered_category_is_rejected() -> None:
    rows = ({**_rows()[0], "country": "XX"},)
    with pytest.raises(ValueError, match="declared subgroup"):
        assign_subgroups(hte_execution(), hte_table(rows))
