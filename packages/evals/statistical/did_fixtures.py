"""Deterministic, hand-calculable Difference-in-Differences evaluation fixtures."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from packages.experiments.analysis import (
    AnalysisTable,
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
from packages.experiments.analysis.causal.did import (
    DifferenceInDifferencesDataBinding,
    DifferenceInDifferencesExecutionRequest,
    DifferenceInDifferencesResult,
    DifferenceInDifferencesService,
)
from packages.observability.base import BaseObservabilityProvider

_DEVIATIONS = (-4.5, -3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5, 4.5)
_POST_DEVIATIONS = (1.5, -2.5, 4.5, -0.5, 2.5, -4.5, 0.5, -3.5, 3.5, -1.5)


def _at(day: int) -> datetime:
    return datetime(2026, 7, day, tzinfo=UTC)


def _provenance(source_id: str) -> tuple[ProvenanceRecord, ...]:
    return (
        ProvenanceRecord(
            source_type=ProvenanceSourceType.USER_SUPPLIED,
            source_id=source_id,
            source_version="1",
        ),
    )


def _variable(
    variable_id: str,
    role: VariableRole,
    timing: MeasurementTiming,
) -> CausalVariable:
    reference_period = None
    if timing is MeasurementTiming.AT_TREATMENT:
        reference_period = TimePeriod(start=_at(10), end=_at(11))
    elif timing is MeasurementTiming.POST_TREATMENT:
        reference_period = TimePeriod(start=_at(15), end=_at(20))
    return CausalVariable(
        variable_id=variable_id,
        label=variable_id.replace("_", " ").title(),
        roles=(role,),
        timing=VariableTiming(
            measurement_timing=timing,
            reference_period=reference_period,
            treatment_start=_at(10),
            evidence=_provenance(f"did-eval-timing:{variable_id}"),
        ),
        provenance=_provenance(f"did-eval-variable:{variable_id}"),
    )


def _assumptions() -> tuple[CausalAssumption, ...]:
    codes = (
        CausalAssumptionCode.CONSISTENCY,
        CausalAssumptionCode.INTERFERENCE_LIMITATION,
        CausalAssumptionCode.EXCHANGEABILITY,
        CausalAssumptionCode.POSITIVITY,
        CausalAssumptionCode.TEMPORAL_ORDERING,
        CausalAssumptionCode.STABLE_TREATMENT_DEFINITION,
        CausalAssumptionCode.STABLE_UNIT_POPULATION,
        CausalAssumptionCode.PARALLEL_TRENDS,
        CausalAssumptionCode.NO_ANTICIPATION,
    )
    return tuple(
        CausalAssumption(
            code=code,
            description=f"Declared {code.value} assumption.",
            applicability=AssumptionApplicability.REQUIRED,
            status=CausalAssumptionStatus.ASSERTED,
            testability=AssumptionTestability.PARTIALLY_TESTABLE,
            evidence=_provenance(f"did-eval-assumption:{code.value}"),
            limitations=(f"{code.value} is declared, not proven.",),
        )
        for code in codes
    )


def did_evaluation_request() -> ObservationalAnalysisRequest:
    """Build the issue #98 reference identification request without test imports."""
    population = PopulationDefinition(
        population_id="eligible_accounts",
        label="Eligible accounts",
        criteria=(),
    )
    treatment = TreatmentContrast(
        treatment_variable="treated",
        treated_value=1,
        control_value=0,
        exposure_definition="Account received the product treatment.",
        provenance=_provenance("did-eval-contrast"),
    )
    outcome = OutcomeMetric(
        metric=MetricDefinition(
            metric_id="conversion",
            label="Revenue per account",
            metric_type=MetricType.CONTINUOUS,
            unit=MetricUnit(
                dimension=UnitDimension.CURRENCY,
                value_scale=ValueScale.RAW,
                symbol="USD",
                scale_to_base_unit=1.0,
                currency_code="USD",
            ),
        ),
        direction=OutcomeDirection.INCREASE,
    )
    estimand = CausalEstimand(
        estimand_type=CausalEstimandKind.DID_ATT,
        treatment_contrast=treatment,
        target_population=TargetPopulation(
            kind=TargetPopulationKind.TREATED,
            population=population,
        ),
        outcome_variable="conversion",
        effect_scale=EffectScale.MEAN_DIFFERENCE,
        provenance=_provenance("did-eval-estimand"),
    )
    identification = CausalIdentificationRequest(
        design=ObservationalDesign(
            design_type=ObservationalDesignType.DID,
            method="two_group_two_period_did",
            treated_group="treated accounts",
            comparison_group="untreated comparison accounts",
            stable_treatment_adoption="once_treated_always_treated",
            provenance=_provenance("did-eval-design"),
        ),
        estimand=estimand,
        treatment=treatment,
        outcome=CausalOutcome(variable_id="conversion", metric=outcome),
        population=population,
        units=UnitSemantics(
            analysis_unit=AnalysisUnit(unit_id="account", label="Account"),
            observation_unit=AnalysisUnit(unit_id="account-period", label="Account period"),
            clustering_unit=AnalysisUnit(unit_id="account", label="Account"),
        ),
        time=TimeSemantics(
            time_variable="observed_at",
            treatment_start=_at(10),
            pre_period=TimePeriod(start=_at(1), end=_at(10)),
            post_period=TimePeriod(start=_at(10), end=_at(20)),
            provenance=_provenance("did-eval-time"),
        ),
        variables=(
            _variable("account_id", VariableRole.IDENTIFIER, MeasurementTiming.TIME_INVARIANT),
            _variable("treated", VariableRole.TREATMENT, MeasurementTiming.AT_TREATMENT),
            _variable("conversion", VariableRole.OUTCOME, MeasurementTiming.POST_TREATMENT),
            _variable("observed_at", VariableRole.TIME, MeasurementTiming.TIME_INVARIANT),
            _variable("prior_orders", VariableRole.ADJUSTMENT, MeasurementTiming.PRE_TREATMENT),
        ),
        covariates=("prior_orders",),
        adjustment_set=AdjustmentSet(
            variable_ids=("prior_orders",),
            purpose=AdjustmentPurpose.CONFOUNDING_CONTROL,
            estimand_type=CausalEstimandKind.DID_ATT,
            source="user_supplied",
            validation_status=AdjustmentValidationStatus.UNVALIDATED,
            diagnostics=(),
            provenance=_provenance("did-eval-adjustment"),
        ),
        assumptions=_assumptions(),
        evidence_limitations=(),
        provenance=_provenance("did-eval-identification"),
    )
    return ObservationalAnalysisRequest(
        request_id="did-eval-request",
        identification=identification,
    )


def _rows(treated_post_mean: float) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for group, prefix, pre_mean, post_mean in (
        ("treated", "t", 10.0, treated_post_mean),
        ("control", "c", 8.0, 10.0),
    ):
        for index, (pre_deviation, post_deviation) in enumerate(
            zip(_DEVIATIONS, _POST_DEVIATIONS, strict=True),
            start=1,
        ):
            unit_id = f"{prefix}-{index:02d}"
            start = _at(10) if group == "treated" else None
            rows.extend(
                (
                    {
                        "unit_id": unit_id,
                        "observed_at": _at(5),
                        "group": group,
                        "exposed": 0,
                        "treatment_start": start,
                        "outcome": pre_mean + pre_deviation,
                    },
                    {
                        "unit_id": unit_id,
                        "observed_at": _at(15),
                        "group": group,
                        "exposed": int(group == "treated"),
                        "treatment_start": start,
                        "outcome": post_mean + post_deviation,
                    },
                )
            )
    return tuple(rows)


def _binding() -> DifferenceInDifferencesDataBinding:
    return DifferenceInDifferencesDataBinding(
        unit_column="unit_id",
        time_column="observed_at",
        group_column="group",
        treatment_column="exposed",
        treatment_start_column="treatment_start",
        outcome_column="outcome",
        treated_group_value="treated",
        control_group_value="control",
    )


def _post_only_treated_unit(rows: Sequence[dict[str, object]]) -> tuple[dict[str, object], ...]:
    return tuple(rows) + (
        {
            "unit_id": "t-new",
            "observed_at": _at(15),
            "group": "treated",
            "exposed": 1,
            "treatment_start": _at(10),
            "outcome": 15.0,
        },
    )


def run_did_fixture(
    fixture_id: str,
    *,
    reverse_rows: bool = False,
    observability_provider: BaseObservabilityProvider | None = None,
) -> DifferenceInDifferencesResult:
    """Execute one deterministic DiD fixture through the production service."""
    rows = _rows(15.0)
    if fixture_id == "did_post_only_treated_unit":
        rows = _post_only_treated_unit(rows)
    elif fixture_id != "did_known_positive_effect":
        raise ValueError(f"unknown DiD fixture_id: {fixture_id}")
    if reverse_rows:
        rows = tuple(reversed(rows))
    execution = DifferenceInDifferencesExecutionRequest(
        analysis_request=did_evaluation_request(),
        binding=_binding(),
    )
    return DifferenceInDifferencesService(
        observability_provider=observability_provider
    ).analyze(
        execution,
        AnalysisTable.from_records(rows),
        provenance=_provenance(f"did-eval-input:{fixture_id}"),
    )


__all__ = ["did_evaluation_request", "run_did_fixture"]
