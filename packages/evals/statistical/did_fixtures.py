"""Deterministic, hand-calculable Difference-in-Differences evaluation fixtures."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from random import Random

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
    DidStatus,
    DifferenceInDifferencesDataBinding,
    DifferenceInDifferencesExecutionRequest,
    DifferenceInDifferencesResult,
    DifferenceInDifferencesService,
)
from packages.observability.base import BaseObservabilityProvider

from .models import ObservationalCoverageResult, ObservationalSimulationSpecification

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


def _extra_pre_periods() -> tuple[TimePeriod, TimePeriod]:
    return (
        TimePeriod(start=datetime(2026, 6, 1, tzinfo=UTC), end=datetime(2026, 6, 2, tzinfo=UTC)),
        TimePeriod(start=datetime(2026, 6, 3, tzinfo=UTC), end=datetime(2026, 6, 4, tzinfo=UTC)),
    )


def _add_extra_pre_rows(
    canonical_rows: tuple[dict[str, object], ...],
) -> tuple[dict[str, object], ...]:
    periods = _extra_pre_periods()
    means = {"treated": (4.0, 8.0), "control": (8.0, 8.0)}
    units = tuple(canonical_rows[index] for index in range(0, len(canonical_rows), 2))
    extra: list[dict[str, object]] = []
    for unit_index, unit in enumerate(units):
        group = str(unit["group"])
        for period_index, period in enumerate(periods):
            deviations = _POST_DEVIATIONS if period_index == 0 else _DEVIATIONS
            extra.append(
                {
                    "unit_id": unit["unit_id"],
                    "observed_at": period.start,
                    "group": group,
                    "exposed": 0,
                    "treatment_start": unit["treatment_start"],
                    "outcome": means[group][period_index] + deviations[unit_index % 10],
                }
            )
    return tuple(extra) + canonical_rows


def run_did_fixture(
    fixture_id: str,
    *,
    reverse_rows: bool = False,
    observability_provider: BaseObservabilityProvider | None = None,
) -> DifferenceInDifferencesResult:
    """Execute one deterministic DiD fixture through the production service."""
    rows = _rows(15.0)
    request = did_evaluation_request()
    extra_pre_periods: tuple[TimePeriod, ...] = ()
    if fixture_id == "did_post_only_treated_unit":
        rows = _post_only_treated_unit(rows)
    elif fixture_id == "did_null_effect":
        rows = _rows(12.0)
    elif fixture_id == "did_staggered_adoption":
        rows = tuple(
            row | {"treatment_start": _at(11)} if row["unit_id"] == "t-10" else row for row in rows
        )
    elif fixture_id == "did_reversed_timing":
        identification = request.identification
        request = request.model_copy(
            update={
                "identification": identification.model_copy(
                    update={
                        "time": identification.time.model_copy(
                            update={
                                "pre_period": TimePeriod(start=_at(1), end=_at(12)),
                                "post_period": TimePeriod(start=_at(10), end=_at(20)),
                            }
                        )
                    }
                )
            }
        )
    elif fixture_id == "did_missing_treated_group":
        rows = tuple(row for row in rows if row["group"] == "control")
    elif fixture_id == "did_missing_control_group":
        rows = tuple(row for row in rows if row["group"] == "treated")
    elif fixture_id == "did_incomplete_periods":
        rows = tuple(
            row for row in rows if not (row["unit_id"] == "t-10" and row["observed_at"] == _at(15))
        )
    elif fixture_id == "did_divergent_pretrend":
        rows = _add_extra_pre_rows(rows)
        extra_pre_periods = _extra_pre_periods()
    elif fixture_id not in {"did_known_positive_effect", "did_few_clusters"}:
        raise ValueError(f"unknown DiD fixture_id: {fixture_id}")
    if reverse_rows:
        rows = tuple(reversed(rows))
    execution = DifferenceInDifferencesExecutionRequest(
        analysis_request=request,
        binding=_binding(),
        extra_pre_periods=extra_pre_periods,
    )
    return DifferenceInDifferencesService(observability_provider=observability_provider).analyze(
        execution,
        AnalysisTable.from_records(rows),
        provenance=_provenance(f"did-eval-input:{fixture_id}"),
    )


def run_did_coverage_simulation(
    specification: ObservationalSimulationSpecification,
) -> ObservationalCoverageResult:
    """Run a fully declared seeded DiD DGP through the production estimator."""
    if specification.dgp_name != "did_parallel_trends_gaussian":
        raise ValueError(f"unsupported observational DGP: {specification.dgp_name}")
    if specification.dgp_version != "1.0.0":
        raise ValueError(f"unsupported observational DGP version: {specification.dgp_version}")
    if specification.estimand != "did_att" or specification.sample_size % 2:
        raise ValueError("DiD coverage v1 requires did_att and an even sample size")
    generator = Random(specification.seed)
    estimates: list[float] = []
    intervals_containing = 0
    half = specification.sample_size // 2
    request = did_evaluation_request()
    for repetition in range(specification.repetitions):
        rows: list[dict[str, object]] = []
        for treated in (False, True):
            group = "treated" if treated else "control"
            for index in range(half):
                unit_id = f"r{repetition:03d}-{group}-{index:03d}"
                unit_baseline = generator.gauss(0.0, 1.0)
                pre_error = generator.gauss(0.0, 1.0)
                post_error = generator.gauss(0.0, 1.0)
                baseline = 8.0 + (2.0 if treated else 0.0) + unit_baseline
                treatment_start = _at(10) if treated else None
                rows.extend(
                    (
                        {
                            "unit_id": unit_id,
                            "observed_at": _at(5),
                            "group": group,
                            "exposed": 0,
                            "treatment_start": treatment_start,
                            "outcome": baseline + pre_error,
                        },
                        {
                            "unit_id": unit_id,
                            "observed_at": _at(15),
                            "group": group,
                            "exposed": int(treated),
                            "treatment_start": treatment_start,
                            "outcome": baseline
                            + 2.0
                            + (specification.true_causal_effect if treated else 0.0)
                            + post_error,
                        },
                    )
                )
        result = DifferenceInDifferencesService().analyze(
            DifferenceInDifferencesExecutionRequest(
                analysis_request=request,
                binding=_binding(),
            ),
            AnalysisTable.from_records(rows),
            provenance=_provenance(
                f"{specification.dgp_name}:{specification.dgp_version}:{repetition}"
            ),
        )
        if result.status is not DidStatus.COMPLETED:
            raise RuntimeError(f"coverage repetition {repetition} did not complete")
        assert result.cell_means is not None
        assert result.test_result is not None
        estimate = result.cell_means.did_estimate
        interval = result.test_result.confidence_interval
        estimates.append(estimate)
        intervals_containing += int(
            interval.lower <= specification.true_causal_effect <= interval.upper
        )
    coverage = intervals_containing / specification.repetitions
    return ObservationalCoverageResult(
        method="did",
        estimand=specification.estimand,
        true_effect=specification.true_causal_effect,
        repetitions=specification.repetitions,
        completed_repetitions=specification.repetitions,
        intervals_containing=intervals_containing,
        interval_coverage=coverage,
        mean_estimate=sum(estimates) / len(estimates),
        coverage_status=(
            "within_aspirational_range"
            if specification.coverage_lower <= coverage <= specification.coverage_upper
            else "outside_aspirational_range"
        ),
        simulation=specification,
    )


__all__ = ["did_evaluation_request", "run_did_coverage_simulation", "run_did_fixture"]
