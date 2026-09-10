"""Owned contracts for bounded heterogeneous-effect estimation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.experiments.analysis.causal import MeasurementTiming, VariableRole
from packages.experiments.analysis.causal.dml import DMLConfig
from packages.experiments.analysis.causal.hte import (
    CategoricalSubgroup,
    ContinuousBinSubgroup,
    EffectModifierDefinition,
    HTEConfig,
    HTEModifierDerivation,
    HTEModifierType,
    HTEPreSpecificationStatus,
    HTERegistrationStatus,
    HTESubgroupStatus,
    SubgroupEffectResult,
    SubgroupSampleCounts,
)
from tests.causal_identification_fixtures import provenance


def binary_modifier(
    *,
    timing: MeasurementTiming = MeasurementTiming.PRE_TREATMENT,
    pre_specification: HTEPreSpecificationStatus = (
        HTEPreSpecificationStatus.CONFIRMATORY_PRE_SPECIFIED
    ),
    registration: HTERegistrationStatus = HTERegistrationStatus.REGISTERED,
) -> EffectModifierDefinition:
    return EffectModifierDefinition(
        variable_id="market_tier",
        column="market_tier",
        role=VariableRole.EFFECT_MODIFIER,
        measurement_timing=timing,
        modifier_type=HTEModifierType.BINARY_CATEGORICAL,
        derivation=HTEModifierDerivation.DIRECT_MEASUREMENT,
        subgroups=(
            CategoricalSubgroup(subgroup_id="standard", label="Standard", value="standard"),
            CategoricalSubgroup(subgroup_id="priority", label="Priority", value="priority"),
        ),
        pre_specification=pre_specification,
        registration_status=registration,
        registration_id="registry-103"
        if registration is HTERegistrationStatus.REGISTERED
        else None,
        definition_provenance=provenance("modifier-definition"),
        registration_provenance=(
            provenance("modifier-registration")
            if registration is HTERegistrationStatus.REGISTERED
            else None
        ),
    )


def test_binary_modifier_records_role_timing_registration_and_order() -> None:
    modifier = binary_modifier()

    assert modifier.role is VariableRole.EFFECT_MODIFIER
    assert modifier.measurement_timing is MeasurementTiming.PRE_TREATMENT
    assert tuple(group.subgroup_id for group in modifier.subgroups) == ("standard", "priority")
    assert modifier.registration_id == "registry-103"
    assert modifier.model_dump(mode="json")["subgroups"][0]["value"] == "standard"


def test_modifier_can_represent_blocking_timing_and_exploratory_registration() -> None:
    post_treatment = binary_modifier(timing=MeasurementTiming.POST_TREATMENT)
    exploratory = binary_modifier(
        pre_specification=HTEPreSpecificationStatus.EXPLORATORY,
        registration=HTERegistrationStatus.UNREGISTERED,
    )

    assert post_treatment.measurement_timing is MeasurementTiming.POST_TREATMENT
    assert exploratory.registration_id is None
    assert exploratory.registration_provenance is None


def test_binary_and_categorical_modifiers_reject_duplicate_or_wrong_group_counts() -> None:
    payload = binary_modifier().model_dump()
    payload["subgroups"] = (
        *payload["subgroups"],
        {"kind": "categorical", "subgroup_id": "other", "label": "Other", "value": "other"},
    )
    with pytest.raises(ValidationError, match="exactly two"):
        EffectModifierDefinition.model_validate(payload)

    payload = binary_modifier().model_dump()
    payload["modifier_type"] = HTEModifierType.FINITE_CATEGORICAL
    payload["subgroups"] = (payload["subgroups"][0], payload["subgroups"][0])
    with pytest.raises(ValidationError, match="unique"):
        EffectModifierDefinition.model_validate(payload)


def test_continuous_bins_are_explicit_ordered_and_exhaustive() -> None:
    modifier = EffectModifierDefinition(
        variable_id="baseline_score",
        column="baseline_score",
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
        registration_id="registry-bins",
        definition_provenance=provenance("bin-definition"),
        registration_provenance=provenance("bin-registration"),
    )

    assert modifier.subgroups[0].upper == 0.0
    assert modifier.subgroups[1].lower_inclusive is True

    payload = modifier.model_dump()
    payload["subgroups"][1]["lower"] = 1.0
    with pytest.raises(ValidationError, match="contiguous"):
        EffectModifierDefinition.model_validate(payload)


def test_configuration_centralizes_sparse_thresholds_and_dml_policy() -> None:
    config = HTEConfig(dml=DMLConfig(fold_count=4, random_seed=103))

    assert config.minimum_subgroup_retained == 20
    assert config.minimum_subgroup_treated == 5
    assert config.minimum_subgroup_control == 5
    assert config.multiplicity_method.value == "holm"
    assert config.analysis_version == "hte-dml-v1"


def test_subgroup_status_shape_never_exposes_point_estimate_without_uncertainty() -> None:
    counts = SubgroupSampleCounts(
        raw_count=30,
        retained_count=28,
        treated_count=14,
        control_count=14,
        dropped_count=2,
    )
    with pytest.raises(ValidationError, match="uncertainty"):
        SubgroupEffectResult(
            subgroup_id="standard",
            label="Standard",
            rule="market_tier == 'standard'",
            sample_counts=counts,
            status=HTESubgroupStatus.COMPLETED,
            estimate=1.0,
        )

    abstained = SubgroupEffectResult(
        subgroup_id="standard",
        label="Standard",
        rule="market_tier == 'standard'",
        sample_counts=counts,
        status=HTESubgroupStatus.ABSTAINED,
        abstention_reason="hte.subgroup.sparse",
    )
    assert abstained.estimate is None
