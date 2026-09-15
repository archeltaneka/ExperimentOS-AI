"""Owned request and effect-modifier contracts for bounded HTE analysis."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from ...base import ContractModel, FiniteFloat, NonEmptyStr, ScalarValue
from ...provenance import ProvenanceRecord, ProvenanceRecords
from ..dml.models import DMLConfig, DMLCovariateBinding
from ..models import IdentificationResult
from ..variables import MeasurementTiming, VariableRole

type PositiveCount = Annotated[int, Field(strict=True, gt=0)]


class HTEModifierType(StrEnum):
    BINARY_CATEGORICAL = "binary_categorical"
    FINITE_CATEGORICAL = "finite_categorical"
    CONTINUOUS_BINNED = "continuous_binned"


class HTEPreSpecificationStatus(StrEnum):
    CONFIRMATORY_PRE_SPECIFIED = "confirmatory_pre_specified"
    EXPLORATORY = "exploratory"
    DATA_MINED = "data_mined"


class HTERegistrationStatus(StrEnum):
    REGISTERED = "registered"
    UNREGISTERED = "unregistered"


class HTEMultiplicityMethod(StrEnum):
    HOLM = "holm"


class HTEModifierDerivation(StrEnum):
    DIRECT_MEASUREMENT = "direct_measurement"
    PREDEFINED_TRANSFORMATION = "predefined_transformation"
    OUTCOME_DERIVED = "outcome_derived"
    TREATMENT_DERIVED = "treatment_derived"
    DATA_MINED = "data_mined"


class CategoricalSubgroup(ContractModel):
    kind: Literal["categorical"] = "categorical"
    subgroup_id: NonEmptyStr
    label: NonEmptyStr
    value: ScalarValue


class ContinuousBinSubgroup(ContractModel):
    kind: Literal["continuous_bin"] = "continuous_bin"
    subgroup_id: NonEmptyStr
    label: NonEmptyStr
    lower: FiniteFloat | None
    upper: FiniteFloat | None
    lower_inclusive: Literal[True] = True
    upper_inclusive: Literal[False] = False

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if self.lower is None and self.upper is None:
            raise ValueError("a continuous bin requires at least one finite boundary")
        if self.lower is not None and self.upper is not None and self.lower >= self.upper:
            raise ValueError("continuous bin lower boundary must be below upper boundary")
        return self


type HTESubgroupDefinition = Annotated[
    CategoricalSubgroup | ContinuousBinSubgroup,
    Field(discriminator="kind"),
]


class EffectModifierDefinition(ContractModel):
    """Prespecified pre-treatment groups for conditional causal effects."""

    variable_id: NonEmptyStr
    column: NonEmptyStr
    role: Literal[VariableRole.EFFECT_MODIFIER]
    measurement_timing: MeasurementTiming
    modifier_type: HTEModifierType
    derivation: HTEModifierDerivation
    subgroups: Annotated[tuple[HTESubgroupDefinition, ...], Field(min_length=2)]
    pre_specification: HTEPreSpecificationStatus
    registration_status: HTERegistrationStatus
    registration_id: NonEmptyStr | None = None
    definition_provenance: ProvenanceRecords
    registration_provenance: tuple[ProvenanceRecord, ...] | None = None

    @model_validator(mode="after")
    def validate_definition(self) -> Self:
        ids = tuple(item.subgroup_id for item in self.subgroups)
        labels = tuple(item.label for item in self.subgroups)
        if len(ids) != len(set(ids)) or len(labels) != len(set(labels)):
            raise ValueError("subgroup identifiers and labels must be unique")
        registered = self.registration_status is HTERegistrationStatus.REGISTERED
        if registered != (self.registration_id is not None):
            raise ValueError("registered modifiers require a registration identifier")
        if registered != bool(self.registration_provenance):
            raise ValueError("registered modifiers require registration provenance")
        if self.modifier_type is HTEModifierType.CONTINUOUS_BINNED:
            self._validate_continuous_bins()
        else:
            self._validate_categorical_groups()
        return self

    def _validate_categorical_groups(self) -> None:
        groups = tuple(item for item in self.subgroups if isinstance(item, CategoricalSubgroup))
        if len(groups) != len(self.subgroups):
            raise ValueError("categorical modifiers require categorical subgroups")
        if self.modifier_type is HTEModifierType.BINARY_CATEGORICAL and len(self.subgroups) != 2:
            raise ValueError("binary categorical modifiers require exactly two subgroups")
        keys = tuple(_scalar_key(item.value) for item in groups)
        if len(keys) != len(set(keys)):
            raise ValueError("categorical subgroup values must be unique")

    def _validate_continuous_bins(self) -> None:
        if not all(isinstance(item, ContinuousBinSubgroup) for item in self.subgroups):
            raise ValueError("continuous modifiers require continuous-bin subgroups")
        bins = tuple(item for item in self.subgroups if isinstance(item, ContinuousBinSubgroup))
        if bins[0].lower is not None or bins[-1].upper is not None:
            raise ValueError("continuous bins must exhaust the real line")
        for previous, current in zip(bins, bins[1:], strict=False):
            if previous.upper != current.lower:
                raise ValueError("continuous bins must be ordered and contiguous")


class HTEDataBinding(ContractModel):
    observation_id_column: NonEmptyStr
    treatment_variable_id: NonEmptyStr
    treatment_column: NonEmptyStr
    outcome_variable_id: NonEmptyStr
    outcome_column: NonEmptyStr
    modifier_variable_id: NonEmptyStr
    modifier_column: NonEmptyStr
    covariates: Annotated[tuple[DMLCovariateBinding, ...], Field(min_length=1)]

    @field_validator("covariates")
    @classmethod
    def require_unique_covariates(
        cls, value: tuple[DMLCovariateBinding, ...]
    ) -> tuple[DMLCovariateBinding, ...]:
        if len(value) != len({item.variable_id for item in value}):
            raise ValueError("HTE covariate variable IDs must be unique")
        if len(value) != len({item.column for item in value}):
            raise ValueError("HTE covariate columns must be unique")
        return value

    @model_validator(mode="after")
    def require_distinct_columns_and_variables(self) -> Self:
        columns = {
            self.observation_id_column,
            self.treatment_column,
            self.outcome_column,
            self.modifier_column,
            *(item.column for item in self.covariates),
        }
        if len(columns) != len(self.covariates) + 4:
            raise ValueError("HTE role and covariate columns must be distinct")
        variables = {
            self.treatment_variable_id,
            self.outcome_variable_id,
            self.modifier_variable_id,
            *(item.variable_id for item in self.covariates),
        }
        if len(variables) != len(self.covariates) + 3:
            raise ValueError("HTE role and covariate variable IDs must be distinct")
        return self


class HTEConfig(ContractModel):
    """Deterministic HTE support, overlap and uncertainty configuration."""

    dml: DMLConfig
    minimum_subgroup_retained: PositiveCount = 20
    minimum_subgroup_treated: PositiveCount = 5
    minimum_subgroup_control: PositiveCount = 5
    multiplicity_method: Literal[HTEMultiplicityMethod.HOLM] = HTEMultiplicityMethod.HOLM
    analysis_version: Literal["hte-dml-v1", "hte-dr-v1"] = "hte-dml-v1"

    @model_validator(mode="after")
    def validate_sparse_thresholds(self) -> Self:
        if (
            self.minimum_subgroup_treated + self.minimum_subgroup_control
            > self.minimum_subgroup_retained
        ):
            raise ValueError("subgroup arm minima cannot exceed the retained minimum")
        return self


class HTEExecutionRequest(ContractModel):
    """Owned identified request, data binding and modifier declaration."""

    schema_version: Literal["1"] = "1"
    identification_result: IdentificationResult
    binding: HTEDataBinding
    modifier: EffectModifierDefinition
    configuration: HTEConfig

    @property
    def request_id(self) -> str:
        return self.identification_result.request_id


def _scalar_key(value: ScalarValue) -> str:
    return json.dumps(
        {"type": type(value).__name__, "value": value},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


__all__ = [
    "CategoricalSubgroup",
    "ContinuousBinSubgroup",
    "EffectModifierDefinition",
    "HTEConfig",
    "HTEDataBinding",
    "HTEExecutionRequest",
    "HTEModifierType",
    "HTEModifierDerivation",
    "HTEMultiplicityMethod",
    "HTEPreSpecificationStatus",
    "HTERegistrationStatus",
    "HTESubgroupDefinition",
]
