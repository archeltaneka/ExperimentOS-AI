"""Small hand-checkable orthogonal-score fixtures for HTE tests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from packages.experiments.analysis import AnalysisTable
from packages.experiments.analysis.causal import (
    CausalEstimandKind,
    CausalIdentificationService,
    IdentificationResult,
    MeasurementTiming,
    ObservationalAnalysisRequest,
    ObservationalDesignType,
    VariableRole,
)
from packages.experiments.analysis.causal.dml import DMLConfig, DMLCovariateBinding
from packages.experiments.analysis.causal.hte import (
    CategoricalSubgroup,
    EffectModifierDefinition,
    HTEConfig,
    HTEDataBinding,
    HTEExecutionRequest,
    HTEModifierDerivation,
    HTEModifierType,
    HTEPreSpecificationStatus,
    HTERegistrationStatus,
)
from tests.causal_identification_fixtures import provenance, variable
from tests.dml_fixtures import dml_request, dml_variables


@dataclass(frozen=True)
class OrthogonalFixture:
    outcomes: tuple[float, ...]
    treatments: tuple[float, ...]
    outcome_predictions: tuple[float, ...]
    treatment_predictions: tuple[float, ...]
    subgroup_ids: tuple[str, ...]


def grouped_orthogonal_fixture(
    effects: tuple[tuple[str, float], ...],
    *,
    pairs_per_group: int = 20,
    noise: float = 0.2,
) -> OrthogonalFixture:
    """Return residuals whose group slopes equal the declared effects exactly."""
    outcomes: list[float] = []
    treatments: list[float] = []
    subgroup_ids: list[str] = []
    for subgroup_id, effect in effects:
        for _ in range(pairs_per_group):
            for treatment in (0.0, 1.0):
                treatment_residual = treatment - 0.5
                outcomes.append(effect * treatment_residual + noise)
                treatments.append(treatment)
                subgroup_ids.append(subgroup_id)
    count = len(outcomes)
    return OrthogonalFixture(
        outcomes=tuple(outcomes),
        treatments=tuple(treatments),
        outcome_predictions=(0.0,) * count,
        treatment_predictions=(0.5,) * count,
        subgroup_ids=tuple(subgroup_ids),
    )


def significance_trap_fixture() -> OrthogonalFixture:
    """A is significant, B is not, and the direct A-B difference is not."""
    return grouped_orthogonal_fixture(
        (("a", 1.0), ("b", 0.5)),
        pairs_per_group=10,
        noise=0.87,
    )


def hte_request(
    *, modifier_timing: MeasurementTiming = MeasurementTiming.PRE_TREATMENT
) -> ObservationalAnalysisRequest:
    source = dml_request(
        estimand_kind=CausalEstimandKind.CATE,
        design_type=ObservationalDesignType.HETEROGENEOUS_EFFECTS,
    )
    modifier_variable = variable("country", VariableRole.EFFECT_MODIFIER, timing=modifier_timing)
    identification = source.identification.model_copy(
        update={
            "design": source.identification.design.model_copy(
                update={"method": "partialling_out_dml_subgroup_interactions"}
            ),
            "variables": (*dml_variables(), modifier_variable),
            "effect_modifiers": ("country",),
        }
    )
    return source.model_copy(update={"identification": identification})


def hte_identification(**kwargs: object) -> IdentificationResult:
    return CausalIdentificationService().identify(hte_request(**kwargs))


def hte_modifier(
    *,
    timing: MeasurementTiming = MeasurementTiming.PRE_TREATMENT,
    derivation: HTEModifierDerivation = HTEModifierDerivation.DIRECT_MEASUREMENT,
    pre_specification: HTEPreSpecificationStatus = (
        HTEPreSpecificationStatus.CONFIRMATORY_PRE_SPECIFIED
    ),
    registration: HTERegistrationStatus = HTERegistrationStatus.REGISTERED,
) -> EffectModifierDefinition:
    return EffectModifierDefinition(
        variable_id="country",
        column="country",
        role=VariableRole.EFFECT_MODIFIER,
        measurement_timing=timing,
        modifier_type=HTEModifierType.BINARY_CATEGORICAL,
        derivation=derivation,
        subgroups=(
            CategoricalSubgroup(subgroup_id="id", label="Indonesia", value="ID"),
            CategoricalSubgroup(subgroup_id="sg", label="Singapore", value="SG"),
        ),
        pre_specification=pre_specification,
        registration_status=registration,
        registration_id="hte-registry-103"
        if registration is HTERegistrationStatus.REGISTERED
        else None,
        definition_provenance=provenance("hte-definition"),
        registration_provenance=(
            provenance("hte-registration")
            if registration is HTERegistrationStatus.REGISTERED
            else None
        ),
    )


def hte_execution(
    *,
    identification_result: IdentificationResult | None = None,
    modifier: EffectModifierDefinition | None = None,
    fold_count: int = 2,
    seed: int = 103,
    minimum_retained: int = 20,
    minimum_treated: int = 5,
    minimum_control: int = 5,
) -> HTEExecutionRequest:
    return HTEExecutionRequest(
        identification_result=identification_result or hte_identification(),
        binding=HTEDataBinding(
            observation_id_column="account_id",
            treatment_variable_id="treated",
            treatment_column="treated",
            outcome_variable_id="outcome",
            outcome_column="outcome",
            modifier_variable_id="country",
            modifier_column="country",
            covariates=(DMLCovariateBinding(variable_id="prior_orders", column="prior_orders"),),
        ),
        modifier=modifier or hte_modifier(),
        configuration=HTEConfig(
            dml=DMLConfig(fold_count=fold_count, random_seed=seed),
            minimum_subgroup_retained=minimum_retained,
            minimum_subgroup_treated=minimum_treated,
            minimum_subgroup_control=minimum_control,
        ),
    )


def hte_table(records: Sequence[Mapping[str, object]]) -> AnalysisTable:
    return AnalysisTable.from_records(records)


def effect_rows(
    effects: tuple[tuple[str, float], ...] = (("ID", 1.0), ("SG", 3.0)),
    *,
    rows_per_group: int = 80,
) -> tuple[dict[str, object], ...]:
    noise = (-0.30, 0.10, 0.20, -0.10, 0.40, -0.20, 0.05, -0.15)
    return tuple(
        {
            "account_id": f"{group}-{index:03d}",
            "treated": index % 2,
            "outcome": (
                2.0
                + 0.4 * (((index // 2) % 20 - 9.5) / 5.0)
                + effect * (index % 2)
                + noise[index % len(noise)]
            ),
            "prior_orders": ((index // 2) % 20 - 9.5) / 5.0,
            "country": group,
        }
        for group, effect in effects
        for index in range(rows_per_group)
    )
