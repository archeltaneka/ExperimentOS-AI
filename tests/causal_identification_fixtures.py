from __future__ import annotations

from datetime import UTC, datetime

from packages.experiments.analysis import (
    AnalysisUnit,
    MetricDefinition,
    MetricType,
    MetricUnit,
    OutcomeDirection,
    OutcomeMetric,
    PopulationDefinition,
    ProvenanceRecord,
    ProvenanceSourceType,
    TimePeriod,
    UnitDimension,
    ValueScale,
)
from packages.experiments.analysis.causal import (
    AdjustmentPurpose,
    AdjustmentSet,
    AdjustmentValidationStatus,
    AssumptionApplicability,
    AssumptionTestability,
    CausalAssumption,
    CausalAssumptionCode,
    CausalAssumptionStatus,
    CausalEstimand,
    CausalEstimandKind,
    CausalIdentificationRequest,
    CausalOutcome,
    CausalVariable,
    EffectScale,
    MeasurementTiming,
    ObservationalAnalysisRequest,
    ObservationalDesign,
    ObservationalDesignType,
    TargetPopulation,
    TargetPopulationKind,
    TimeSemantics,
    TreatmentContrast,
    UnitSemantics,
    VariableRole,
    VariableTiming,
)


def utc(day: int) -> datetime:
    return datetime(2026, 7, day, tzinfo=UTC)


def provenance(source_id: str = "issue-97-test") -> tuple[ProvenanceRecord, ...]:
    return (
        ProvenanceRecord(
            source_type=ProvenanceSourceType.USER_SUPPLIED,
            source_id=source_id,
            source_version="1",
        ),
    )


def population() -> PopulationDefinition:
    return PopulationDefinition(
        population_id="eligible_accounts",
        label="Eligible accounts",
        criteria=(),
    )


def outcome_metric() -> OutcomeMetric:
    return OutcomeMetric(
        metric=MetricDefinition(
            metric_id="conversion",
            label="Conversion",
            metric_type=MetricType.BINARY,
            unit=MetricUnit(
                dimension=UnitDimension.PROPORTION,
                value_scale=ValueScale.PROPORTION,
                symbol="1",
                scale_to_base_unit=1.0,
            ),
        ),
        direction=OutcomeDirection.INCREASE,
    )


def variable(
    variable_id: str,
    role: VariableRole,
    *,
    timing: MeasurementTiming,
    additional_roles: tuple[VariableRole, ...] = (),
) -> CausalVariable:
    period = None
    if timing is MeasurementTiming.PRE_TREATMENT:
        period = TimePeriod(start=utc(1), end=utc(5))
    elif timing is MeasurementTiming.AT_TREATMENT:
        period = TimePeriod(start=utc(10), end=utc(11))
    elif timing is MeasurementTiming.POST_TREATMENT:
        period = TimePeriod(start=utc(15), end=utc(20))
    return CausalVariable(
        variable_id=variable_id,
        label=variable_id.replace("_", " ").title(),
        roles=(role, *additional_roles),
        timing=VariableTiming(
            measurement_timing=timing,
            reference_period=period,
            treatment_start=utc(10),
            evidence=provenance(f"timing:{variable_id}"),
        ),
        provenance=provenance(f"variable:{variable_id}"),
    )


def variables(
    *,
    adjustment_timing: MeasurementTiming = MeasurementTiming.PRE_TREATMENT,
    modifier_timing: MeasurementTiming = MeasurementTiming.PRE_TREATMENT,
) -> tuple[CausalVariable, ...]:
    return (
        variable("account_id", VariableRole.IDENTIFIER, timing=MeasurementTiming.TIME_INVARIANT),
        variable("treated", VariableRole.TREATMENT, timing=MeasurementTiming.AT_TREATMENT),
        variable("conversion", VariableRole.OUTCOME, timing=MeasurementTiming.POST_TREATMENT),
        variable("observed_at", VariableRole.TIME, timing=MeasurementTiming.TIME_INVARIANT),
        variable("prior_orders", VariableRole.ADJUSTMENT, timing=adjustment_timing),
        variable("country", VariableRole.EFFECT_MODIFIER, timing=modifier_timing),
    )


def contrast() -> TreatmentContrast:
    return TreatmentContrast(
        treatment_variable="treated",
        treated_value=1,
        control_value=0,
        exposure_definition="Account received the product treatment.",
        provenance=provenance("contrast"),
    )


def estimand(
    kind: CausalEstimandKind = CausalEstimandKind.ATE,
) -> CausalEstimand:
    target_kind = TargetPopulationKind.FULL
    modifiers: tuple[str, ...] = ()
    conditioning = None
    if kind in {CausalEstimandKind.ATT, CausalEstimandKind.DID_ATT}:
        target_kind = TargetPopulationKind.TREATED
    elif kind is CausalEstimandKind.CATE:
        target_kind = TargetPopulationKind.CONDITIONED
        modifiers = ("country",)
        conditioning = "Conditional on the declared country effect modifier."
    return CausalEstimand(
        estimand_type=kind,
        treatment_contrast=contrast(),
        target_population=TargetPopulation(kind=target_kind, population=population()),
        outcome_variable="conversion",
        effect_scale=EffectScale.RISK_DIFFERENCE,
        effect_modifiers=modifiers,
        conditioning_definition=conditioning,
        provenance=provenance("estimand"),
    )


def assumptions(*, did: bool = False) -> tuple[CausalAssumption, ...]:
    codes = [
        CausalAssumptionCode.CONSISTENCY,
        CausalAssumptionCode.INTERFERENCE_LIMITATION,
        CausalAssumptionCode.EXCHANGEABILITY,
        CausalAssumptionCode.POSITIVITY,
        CausalAssumptionCode.TEMPORAL_ORDERING,
        CausalAssumptionCode.STABLE_TREATMENT_DEFINITION,
        CausalAssumptionCode.STABLE_UNIT_POPULATION,
    ]
    if did:
        codes.extend(
            [
                CausalAssumptionCode.PARALLEL_TRENDS,
                CausalAssumptionCode.NO_ANTICIPATION,
            ]
        )
    return tuple(
        CausalAssumption(
            code=code,
            description=f"Declared {code.value} assumption.",
            applicability=AssumptionApplicability.REQUIRED,
            status=CausalAssumptionStatus.ASSERTED,
            testability=(
                AssumptionTestability.NOT_FULLY_TESTABLE
                if code is CausalAssumptionCode.EXCHANGEABILITY
                else AssumptionTestability.PARTIALLY_TESTABLE
            ),
            evidence=provenance(f"assumption:{code.value}"),
            diagnostic_references=(),
            limitations=(f"{code.value} is declared, not proven.",),
        )
        for code in codes
    )


def design(
    design_type: ObservationalDesignType = ObservationalDesignType.GENERIC,
) -> ObservationalDesign:
    return ObservationalDesign(
        design_type=design_type,
        method="declared_observational_method",
        treated_group="treated accounts" if design_type is ObservationalDesignType.DID else None,
        comparison_group=(
            "untreated comparison accounts" if design_type is ObservationalDesignType.DID else None
        ),
        stable_treatment_adoption=(
            "once_treated_always_treated" if design_type is ObservationalDesignType.DID else None
        ),
        provenance=provenance("design"),
    )


def time_semantics(*, did: bool = False) -> TimeSemantics:
    return TimeSemantics(
        time_variable="observed_at",
        treatment_start=utc(10),
        pre_period=TimePeriod(start=utc(1), end=utc(10)) if did else None,
        post_period=TimePeriod(start=utc(10), end=utc(20)) if did else None,
        provenance=provenance("time-semantics"),
    )


def adjustment_set(
    estimand_kind: CausalEstimandKind = CausalEstimandKind.ATE,
) -> AdjustmentSet:
    return AdjustmentSet(
        variable_ids=("prior_orders",),
        purpose=AdjustmentPurpose.CONFOUNDING_CONTROL,
        estimand_type=estimand_kind,
        source="user_supplied",
        validation_status=AdjustmentValidationStatus.UNVALIDATED,
        diagnostics=(),
        provenance=provenance("adjustment-set"),
    )


def request(
    *,
    design_type: ObservationalDesignType = ObservationalDesignType.GENERIC,
    estimand_kind: CausalEstimandKind = CausalEstimandKind.ATE,
    declared_variables: tuple[CausalVariable, ...] | None = None,
    declared_assumptions: tuple[CausalAssumption, ...] | None = None,
    adjustment: AdjustmentSet | None = None,
) -> ObservationalAnalysisRequest:
    did = design_type is ObservationalDesignType.DID
    return ObservationalAnalysisRequest(
        request_id="causal-request-001",
        identification=CausalIdentificationRequest(
            design=design(design_type),
            estimand=estimand(estimand_kind),
            treatment=contrast(),
            outcome=CausalOutcome(variable_id="conversion", metric=outcome_metric()),
            population=population(),
            units=UnitSemantics(
                analysis_unit=AnalysisUnit(unit_id="account", label="Account"),
                observation_unit=AnalysisUnit(unit_id="account-day", label="Account day"),
                clustering_unit=AnalysisUnit(unit_id="account", label="Account"),
            ),
            time=time_semantics(did=did),
            variables=declared_variables or variables(),
            covariates=("prior_orders",),
            adjustment_set=(
                adjustment if adjustment is not None else adjustment_set(estimand_kind)
            ),
            effect_modifiers=("country",) if estimand_kind is CausalEstimandKind.CATE else (),
            assumptions=(
                declared_assumptions if declared_assumptions is not None else assumptions(did=did)
            ),
            evidence_limitations=(),
            provenance=provenance("identification-request"),
        ),
    )
