"""Deterministic observational causal fixtures for the Phase 4 reliability suite."""

from __future__ import annotations

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
    CausalIdentificationService,
    CausalOutcome,
    CausalVariable,
    EffectScale,
    IdentificationResult,
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
from packages.experiments.analysis.causal.ipw import (
    IPWConfig,
    IPWExecutionRequest,
    IPWOutcomeBinding,
    IPWTreatmentEffectEstimator,
    IPWWeightClippingConfig,
    TreatmentEffectResult,
)
from packages.experiments.analysis.causal.ipw.service import IPWCalculationEngine
from packages.experiments.analysis.causal.propensity import (
    BalanceDiagnostics,
    BalanceStatus,
    CovariateBalanceDiagnostic,
    DeterministicLogisticPropensityEstimator,
    PropensityConfig,
    PropensityCovariateBinding,
    PropensityDataBinding,
    PropensityExecutionRequest,
    PropensityFeatureKind,
    PropensityFitStatus,
    PropensityModelFit,
    PropensityResult,
    PropensityScore,
    PropensityWeight,
    StandardizedMeanDifference,
)
from packages.experiments.analysis.causal.propensity.numerics import (
    assess_overlap,
    build_score_diagnostics,
    build_weight_diagnostics,
    common_support_diagnostic,
    compute_weight_values,
)
from packages.observability.base import BaseObservabilityProvider


def _at(day: int) -> datetime:
    return datetime(2026, 7, day, tzinfo=UTC)


def _provenance(source_id: str) -> tuple[ProvenanceRecord, ...]:
    return (
        ProvenanceRecord(
            source_type=ProvenanceSourceType.EXTERNAL_REFERENCE,
            source_id=source_id,
            source_version="issue-101-v1",
        ),
    )


def _population() -> PopulationDefinition:
    return PopulationDefinition(
        population_id="eligible_accounts",
        label="Eligible accounts",
        criteria=(),
    )


def _contrast() -> TreatmentContrast:
    return TreatmentContrast(
        treatment_variable="treated",
        treated_value=1,
        control_value=0,
        exposure_definition="Account received the declared product treatment.",
        provenance=_provenance("issue-101-treatment-contrast"),
    )


def _outcome_metric() -> OutcomeMetric:
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


def _variable(
    variable_id: str,
    role: VariableRole,
    timing: MeasurementTiming,
) -> CausalVariable:
    reference_period = None
    if timing is MeasurementTiming.PRE_TREATMENT:
        reference_period = TimePeriod(start=_at(1), end=_at(5))
    elif timing is MeasurementTiming.AT_TREATMENT:
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
            evidence=_provenance(f"issue-101-timing:{variable_id}"),
        ),
        provenance=_provenance(f"issue-101-variable:{variable_id}"),
    )


def _variables(
    *,
    adjustment_timing: MeasurementTiming = MeasurementTiming.PRE_TREATMENT,
    modifier_timing: MeasurementTiming = MeasurementTiming.PRE_TREATMENT,
) -> tuple[CausalVariable, ...]:
    return (
        _variable("account_id", VariableRole.IDENTIFIER, MeasurementTiming.TIME_INVARIANT),
        _variable("treated", VariableRole.TREATMENT, MeasurementTiming.AT_TREATMENT),
        _variable("conversion", VariableRole.OUTCOME, MeasurementTiming.POST_TREATMENT),
        _variable("observed_at", VariableRole.TIME, MeasurementTiming.TIME_INVARIANT),
        _variable("prior_orders", VariableRole.ADJUSTMENT, adjustment_timing),
        _variable("country", VariableRole.EFFECT_MODIFIER, modifier_timing),
    )


def _estimand(kind: CausalEstimandKind) -> CausalEstimand:
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
        treatment_contrast=_contrast(),
        target_population=TargetPopulation(kind=target_kind, population=_population()),
        outcome_variable="conversion",
        effect_scale=EffectScale.RISK_DIFFERENCE,
        effect_modifiers=modifiers,
        conditioning_definition=conditioning,
        provenance=_provenance("issue-101-estimand"),
    )


def _assumptions() -> tuple[CausalAssumption, ...]:
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
            evidence=_provenance(f"issue-101-assumption:{code.value}"),
            limitations=(f"{code.value} is declared, not proven.",),
        )
        for code in (
            CausalAssumptionCode.CONSISTENCY,
            CausalAssumptionCode.INTERFERENCE_LIMITATION,
            CausalAssumptionCode.EXCHANGEABILITY,
            CausalAssumptionCode.POSITIVITY,
            CausalAssumptionCode.TEMPORAL_ORDERING,
            CausalAssumptionCode.STABLE_TREATMENT_DEFINITION,
            CausalAssumptionCode.STABLE_UNIT_POPULATION,
        )
    )


def observational_identification_request(
    *,
    estimand_kind: CausalEstimandKind = CausalEstimandKind.ATE,
    design_type: ObservationalDesignType = ObservationalDesignType.PROPENSITY_WEIGHTING,
    variables: tuple[CausalVariable, ...] | None = None,
    assumptions: tuple[CausalAssumption, ...] | None = None,
    adjustment_ids: tuple[str, ...] = ("prior_orders",),
) -> ObservationalAnalysisRequest:
    """Build a complete repository-owned identification request for evaluation fixtures."""
    population = _population()
    return ObservationalAnalysisRequest(
        request_id="issue-101-identification-reference",
        identification=CausalIdentificationRequest(
            design=ObservationalDesign(
                design_type=design_type,
                method="declared_observational_method",
                provenance=_provenance("issue-101-design"),
            ),
            estimand=_estimand(estimand_kind),
            treatment=_contrast(),
            outcome=CausalOutcome(variable_id="conversion", metric=_outcome_metric()),
            population=population,
            units=UnitSemantics(
                analysis_unit=AnalysisUnit(unit_id="account", label="Account"),
                observation_unit=AnalysisUnit(unit_id="account-day", label="Account day"),
                clustering_unit=AnalysisUnit(unit_id="account", label="Account"),
            ),
            time=TimeSemantics(
                time_variable="observed_at",
                treatment_start=_at(10),
                provenance=_provenance("issue-101-time"),
            ),
            variables=variables if variables is not None else _variables(),
            covariates=adjustment_ids,
            adjustment_set=AdjustmentSet(
                variable_ids=adjustment_ids,
                purpose=AdjustmentPurpose.CONFOUNDING_CONTROL,
                estimand_type=estimand_kind,
                source="user_supplied",
                validation_status=AdjustmentValidationStatus.UNVALIDATED,
                diagnostics=(),
                provenance=_provenance("issue-101-adjustment"),
            ),
            effect_modifiers=("country",) if estimand_kind is CausalEstimandKind.CATE else (),
            assumptions=assumptions if assumptions is not None else _assumptions(),
            evidence_limitations=(),
            provenance=_provenance("issue-101-identification"),
        ),
    )


def run_identification_fixture(
    fixture_id: str,
    *,
    reverse_rows: bool = False,
    observability_provider: BaseObservabilityProvider | None = None,
) -> IdentificationResult:
    """Run one deterministic identification case through the production service."""
    del reverse_rows
    estimand_kind = (
        CausalEstimandKind.ATT
        if fixture_id == "identification_att_identified"
        else CausalEstimandKind.ATE
    )
    request = observational_identification_request(estimand_kind=estimand_kind)

    if fixture_id == "identification_post_treatment_adjustment":
        request = observational_identification_request(
            variables=_variables(adjustment_timing=MeasurementTiming.POST_TREATMENT)
        )
    elif fixture_id == "identification_treatment_leakage":
        request = observational_identification_request(adjustment_ids=("treated",))
    elif fixture_id == "identification_outcome_leakage":
        request = observational_identification_request(adjustment_ids=("conversion",))
    elif fixture_id == "identification_post_treatment_modifier":
        request = observational_identification_request(
            estimand_kind=CausalEstimandKind.CATE,
            variables=_variables(modifier_timing=MeasurementTiming.POST_TREATMENT),
        )
    elif fixture_id == "identification_missing_estimand":
        request = request.model_copy(
            update={"identification": request.identification.model_copy(update={"estimand": None})}
        )
    elif fixture_id == "identification_missing_assumptions":
        request = observational_identification_request(assumptions=())
    elif fixture_id == "identification_insufficient_evidence":
        identification = request.identification.model_copy(
            update={"adjustment_set": None, "covariates": ()}
        )
        request = request.model_copy(update={"identification": identification})
    elif fixture_id == "identification_contradictory_timing":
        declared = list(_variables())
        adjustment = next(item for item in declared if item.variable_id == "prior_orders")
        declared[declared.index(adjustment)] = adjustment.model_copy(
            update={
                "timing": adjustment.timing.model_copy(
                    update={"reference_period": TimePeriod(start=_at(15), end=_at(20))}
                )
            }
        )
        request = observational_identification_request(variables=tuple(declared))
    elif fixture_id == "identification_unsupported_design":
        request = observational_identification_request(design_type=ObservationalDesignType.CUSTOM)
    elif fixture_id == "identification_unverified_assumption":
        declared = tuple(
            item.model_copy(update={"status": CausalAssumptionStatus.UNVERIFIED})
            if item.code is CausalAssumptionCode.EXCHANGEABILITY
            else item
            for item in _assumptions()
        )
        request = observational_identification_request(assumptions=declared)
    elif fixture_id not in {
        "identification_ate_identified",
        "identification_att_identified",
    }:
        raise ValueError(f"unknown identification fixture_id: {fixture_id}")

    return CausalIdentificationService(observability_provider=observability_provider).identify(
        request
    )


def _propensity_variables() -> tuple[CausalVariable, ...]:
    return (
        _variable("account_id", VariableRole.IDENTIFIER, MeasurementTiming.TIME_INVARIANT),
        _variable("treated", VariableRole.TREATMENT, MeasurementTiming.AT_TREATMENT),
        _variable("conversion", VariableRole.OUTCOME, MeasurementTiming.POST_TREATMENT),
        _variable("observed_at", VariableRole.TIME, MeasurementTiming.TIME_INVARIANT),
        _variable("prior_orders", VariableRole.ADJUSTMENT, MeasurementTiming.PRE_TREATMENT),
        _variable("country", VariableRole.ADJUSTMENT, MeasurementTiming.PRE_TREATMENT),
    )


def observational_propensity_request(
    *,
    estimand_kind: CausalEstimandKind = CausalEstimandKind.ATE,
) -> ObservationalAnalysisRequest:
    return observational_identification_request(
        estimand_kind=estimand_kind,
        variables=_propensity_variables(),
        adjustment_ids=("country", "prior_orders"),
    )


def _propensity_binding() -> PropensityDataBinding:
    return PropensityDataBinding(
        unit_column="account_id",
        treatment_column="treated",
        covariates=(
            PropensityCovariateBinding(
                variable_id="country",
                column="country",
                feature_kind=PropensityFeatureKind.CATEGORICAL,
            ),
            PropensityCovariateBinding(
                variable_id="prior_orders",
                column="prior_orders",
                feature_kind=PropensityFeatureKind.NUMERIC,
            ),
        ),
    )


def _good_overlap_rows() -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    countries = ("TH", "US", "SG")
    for index in range(30):
        rows.extend(
            (
                {
                    "account_id": f"c-{index:02d}",
                    "treated": 0,
                    "country": countries[index % 3],
                    "prior_orders": float(index % 10),
                },
                {
                    "account_id": f"t-{index:02d}",
                    "treated": 1,
                    "country": countries[(index + 1) % 3],
                    "prior_orders": float(index % 10) + 1.5,
                },
            )
        )
    return tuple(rows)


def _separation_rows() -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for index in range(25):
        rows.extend(
            (
                {
                    "account_id": f"sep-c-{index:02d}",
                    "treated": 0,
                    "country": "TH" if index % 2 else "US",
                    "prior_orders": -30.0 + index * 0.5,
                },
                {
                    "account_id": f"sep-t-{index:02d}",
                    "treated": 1,
                    "country": "TH" if index % 2 else "US",
                    "prior_orders": 18.0 + index * 0.5,
                },
            )
        )
    return tuple(rows)


def _extreme_weight_rows() -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for index in range(40):
        rows.extend(
            (
                {
                    "account_id": f"tail-c-{index:02d}",
                    "treated": 0,
                    "country": "TH" if index % 2 else "US",
                    "prior_orders": -3.0 + index * 0.05,
                },
                {
                    "account_id": f"tail-t-{index:02d}",
                    "treated": 1,
                    "country": "TH" if index % 2 else "US",
                    "prior_orders": 1.0 + index * 0.05,
                },
            )
        )
    rows.extend(
        (
            {
                "account_id": "tail-treated-outlier",
                "treated": 1,
                "country": "TH",
                "prior_orders": -3.0,
            },
            {
                "account_id": "tail-control-outlier",
                "treated": 0,
                "country": "US",
                "prior_orders": 2.95,
            },
        )
    )
    return tuple(rows)


class _NonConvergingAdapter:
    def fit_predict(self, encoded: object, config: PropensityConfig) -> PropensityModelFit:
        del encoded
        return PropensityModelFit(
            status=PropensityFitStatus.NON_CONVERGED,
            converged=False,
            scores=(),
            classes=(0, 1),
            iteration_count=config.maximum_iterations,
            solver=config.solver,
            warning_codes=("model.convergence_failure",),
            sklearn_version="deterministic-evaluation-double",
        )


def run_propensity_fixture(
    fixture_id: str,
    *,
    reverse_rows: bool = False,
    observability_provider: BaseObservabilityProvider | None = None,
    estimand_kind: CausalEstimandKind = CausalEstimandKind.ATE,
) -> PropensityResult:
    """Run one deterministic propensity case through the production estimator."""
    rows = _good_overlap_rows()
    config = PropensityConfig(
        weak_outside_support_fraction=0.30,
        severe_outside_support_fraction=0.60,
    )
    adapter = None
    if fixture_id == "propensity_weak_overlap":
        config = PropensityConfig(weak_support_width=0.99, severe_support_width=0.001)
    elif fixture_id in {"propensity_no_overlap", "propensity_separation"}:
        rows = _separation_rows()
    elif fixture_id == "propensity_convergence_failure":
        adapter = _NonConvergingAdapter()
    elif fixture_id == "propensity_extreme_weights":
        rows = _extreme_weight_rows()
        config = PropensityConfig(
            weak_extreme_score_fraction=0.01,
            severe_extreme_score_fraction=0.99,
            weak_outside_support_fraction=0.01,
            severe_outside_support_fraction=0.99,
            weak_support_width=0.20,
            severe_support_width=0.000001,
            weak_extreme_weight_fraction=0.001,
            severe_extreme_weight_fraction=0.99,
            minimum_effective_sample_size=1.0,
            minimum_ess_ratio=0.001,
        )
    elif fixture_id == "propensity_low_ess":
        config = PropensityConfig(
            weak_outside_support_fraction=0.30,
            severe_outside_support_fraction=0.60,
            minimum_effective_sample_size=29.5,
            minimum_ess_ratio=0.99,
        )
    elif fixture_id != "propensity_good_overlap":
        raise ValueError(f"unknown propensity fixture_id: {fixture_id}")

    if reverse_rows:
        rows = tuple(reversed(rows))
    rows = tuple(sorted(rows, key=lambda row: str(row["account_id"])))
    execution = PropensityExecutionRequest(
        analysis_request=observational_propensity_request(estimand_kind=estimand_kind),
        binding=_propensity_binding(),
        configuration=config,
    )
    return DeterministicLogisticPropensityEstimator(
        adapter=adapter,
        observability_provider=observability_provider,
    ).fit_predict(
        execution,
        AnalysisTable.from_records(rows),
        provenance=_provenance(f"issue-101-propensity:{fixture_id}"),
    )


def _known_effect_rows(
    *,
    binary_null: bool = False,
    unequal_att: bool = False,
) -> tuple[dict[str, object], ...]:
    """Return two exact propensity strata with true ATE 4 and ATT 5."""
    rows: list[dict[str, object]] = []
    for label, treated_count, control_count, baseline, effect in (
        ("low", 10, 30, 0.0, 2.0),
        ("high", 40 if unequal_att else 30, 10, 10.0, 6.0),
    ):
        for index in range(treated_count):
            rows.append(
                {
                    "account_id": f"{label}-t-{index:02d}",
                    "treated": 1,
                    "country": label,
                    "prior_orders": 0.0 if label == "low" else 1.0,
                    "conversion": (
                        (0 if label == "low" else 1) if binary_null else baseline + effect
                    ),
                }
            )
        for index in range(control_count):
            rows.append(
                {
                    "account_id": f"{label}-c-{index:02d}",
                    "treated": 0,
                    "country": label,
                    "prior_orders": 0.0 if label == "low" else 1.0,
                    "conversion": ((0 if label == "low" else 1) if binary_null else baseline),
                }
            )
    return tuple(rows)


def _ipw_request(
    *,
    estimand: CausalEstimandKind,
    binary: bool,
) -> ObservationalAnalysisRequest:
    source = observational_propensity_request(estimand_kind=estimand)
    if binary:
        return source
    metric = OutcomeMetric(
        metric=MetricDefinition(
            metric_id="conversion",
            label="Continuous outcome",
            metric_type=MetricType.CONTINUOUS,
            unit=MetricUnit(
                dimension=UnitDimension.DIMENSIONLESS,
                value_scale=ValueScale.RAW,
                symbol="units",
                scale_to_base_unit=1.0,
            ),
        ),
        direction=OutcomeDirection.INCREASE,
    )
    declared = source.identification.estimand
    assert declared is not None
    return source.model_copy(
        update={
            "identification": source.identification.model_copy(
                update={
                    "estimand": declared.model_copy(
                        update={"effect_scale": EffectScale.MEAN_DIFFERENCE}
                    ),
                    "outcome": CausalOutcome(variable_id="conversion", metric=metric),
                }
            )
        }
    )


def _exact_propensity_result(
    *,
    estimand: CausalEstimandKind,
    binary: bool = False,
    unequal_att: bool = False,
    extreme: bool = False,
) -> PropensityResult:
    request = _ipw_request(estimand=estimand, binary=binary)
    rows = _known_effect_rows(binary_null=binary, unequal_att=unequal_att)
    configuration = (
        PropensityConfig(
            minimum_effective_sample_size=1.0,
            minimum_ess_ratio=0.001,
        )
        if extreme
        else PropensityConfig()
    )
    execution = PropensityExecutionRequest(
        analysis_request=request,
        binding=_propensity_binding(),
        configuration=configuration,
    )
    base = DeterministicLogisticPropensityEstimator().fit_predict(
        execution,
        AnalysisTable.from_records(rows),
        provenance=_provenance("issue-101-exact-score-source"),
    )
    default_high_score = 0.80 if unequal_att else 0.75
    score_values = tuple(
        0.005
        if extreme
        and estimand is CausalEstimandKind.ATE
        and str(row["account_id"]).startswith("low-t")
        else 0.995
        if extreme
        and estimand is CausalEstimandKind.ATT
        and str(row["account_id"]).startswith("high-c")
        else 0.25
        if str(row["account_id"]).startswith("low")
        else default_high_score
        for row in rows
    )
    treated = tuple(row["treated"] == 1 for row in rows)
    unit_ids = tuple(str(row["account_id"]) for row in rows)
    scores = tuple(
        PropensityScore(unit_id=unit_id, treated=arm, score=score)
        for unit_id, arm, score in zip(unit_ids, treated, score_values, strict=True)
    )
    raw_weight_values = compute_weight_values(score_values, treated, estimand)
    raw_weights = tuple(
        PropensityWeight(unit_id=unit_id, treated=arm, value=weight)
        for unit_id, arm, weight in zip(unit_ids, treated, raw_weight_values, strict=True)
    )
    weight_diagnostics = build_weight_diagnostics(raw_weights, estimand, execution.configuration)
    extreme_score_fraction = sum(
        score <= execution.configuration.extreme_score_threshold
        or score >= 1.0 - execution.configuration.extreme_score_threshold
        for score in score_values
    ) / len(score_values)
    model_fit = base.model_fit.model_copy(
        update={"scores": score_values, "extreme_score_fraction": extreme_score_fraction}
    )
    support = common_support_diagnostic(score_values, treated)
    overlap = assess_overlap(
        scores=score_values,
        treated=treated,
        support=support,
        model_fit=model_fit,
        weights=weight_diagnostics,
        estimand=estimand,
        config=execution.configuration,
    )
    assert base.balance is not None
    weighted_mean = 0.5 if estimand is CausalEstimandKind.ATE else None
    weighted_variance = 0.25 if estimand is CausalEstimandKind.ATE else None
    features = tuple(
        CovariateBalanceDiagnostic(
            variable_id=item.variable_id,
            feature_name=item.feature_name,
            raw=item.raw,
            weighted=StandardizedMeanDifference(
                available=True,
                treated_mean=(
                    weighted_mean if weighted_mean is not None else item.raw.treated_mean
                ),
                control_mean=(
                    weighted_mean if weighted_mean is not None else item.raw.treated_mean
                ),
                treated_variance=(
                    weighted_variance
                    if weighted_variance is not None
                    else item.raw.treated_variance
                ),
                control_variance=(
                    weighted_variance
                    if weighted_variance is not None
                    else item.raw.treated_variance
                ),
                smd=0.0,
            ),
            status=BalanceStatus.BALANCED,
        )
        for item in base.balance.features
    )
    raw_smds = tuple(abs(item.raw.smd) for item in features if item.raw.smd is not None)
    balance = BalanceDiagnostics(
        features=features,
        raw_max_absolute_smd=max(raw_smds, default=0.0),
        weighted_max_absolute_smd=0.0,
        raw_above_threshold_count=sum(
            value > execution.configuration.balance_threshold for value in raw_smds
        ),
        weighted_above_threshold_count=0,
        improved_count=sum(value > 0.0 for value in raw_smds),
        worsened_count=0,
    )
    return PropensityResult.model_validate(
        base.model_dump(mode="python")
        | {
            "model_fit": model_fit,
            "scores": scores,
            "score_diagnostics": build_score_diagnostics(
                score_values,
                treated,
                execution.configuration,
            ),
            "common_support": support,
            "overlap": overlap,
            "weights": weight_diagnostics,
            "retained": None,
            "capped_weights": None,
            "balance": balance,
            "diagnostics": (),
            "warnings": (),
            "abstention_reason": None,
        }
    )


def _fatal_ipw_inputs(
    fixture_id: str,
) -> tuple[IdentificationResult, PropensityResult, tuple[dict[str, object], ...]]:
    if fixture_id == "ipw_failed_identification":
        propensity = _exact_propensity_result(estimand=CausalEstimandKind.ATE)
        identification = run_identification_fixture("identification_post_treatment_adjustment")
        return identification, propensity, _known_effect_rows()
    source_id = {
        "ipw_propensity_nonconvergence": "propensity_convergence_failure",
        "ipw_failed_overlap": "propensity_no_overlap",
        "ipw_low_ess": "propensity_low_ess",
        "ipw_att_failed_overlap": "propensity_no_overlap",
        "ipw_att_low_ess": "propensity_low_ess",
    }[fixture_id]
    estimand_kind = (
        CausalEstimandKind.ATT if fixture_id.startswith("ipw_att_") else CausalEstimandKind.ATE
    )
    propensity = run_propensity_fixture(source_id, estimand_kind=estimand_kind)
    identification = CausalIdentificationService().identify(propensity.analysis_request)
    rows = _separation_rows() if source_id == "propensity_no_overlap" else _good_overlap_rows()
    return identification, propensity, rows


def run_ipw_fixture(
    fixture_id: str,
    *,
    reverse_rows: bool = False,
    observability_provider: BaseObservabilityProvider | None = None,
    engine: IPWCalculationEngine | None = None,
) -> TreatmentEffectResult:
    """Run an exact-score ATE/ATT reference or a fatal upstream gate."""
    config = IPWConfig()
    binary = fixture_id == "ipw_ate_null_effect"
    estimand = (
        CausalEstimandKind.ATT if fixture_id.startswith("ipw_att_") else CausalEstimandKind.ATE
    )
    fatal_ids = {
        "ipw_failed_identification",
        "ipw_propensity_nonconvergence",
        "ipw_failed_overlap",
        "ipw_low_ess",
        "ipw_att_failed_overlap",
        "ipw_att_low_ess",
    }
    if fixture_id in fatal_ids:
        identification, propensity, rows = _fatal_ipw_inputs(fixture_id)
    else:
        unequal_att = fixture_id == "ipw_att_known_effect"
        extreme = fixture_id in {"ipw_ate_extreme_scores", "ipw_att_extreme_control_weights"}
        rows = _known_effect_rows(binary_null=binary, unequal_att=unequal_att)
        propensity = _exact_propensity_result(
            estimand=estimand,
            binary=binary,
            unequal_att=unequal_att,
            extreme=extreme,
        )
        identification = CausalIdentificationService().identify(propensity.analysis_request)
        if fixture_id == "ipw_ate_stabilized":
            config = IPWConfig(stabilized=True)
        elif fixture_id == "ipw_ate_clipped":
            config = IPWConfig(
                clipping=IPWWeightClippingConfig(maximum=2.0),
                severe_balance_threshold=1.0,
            )
        elif fixture_id not in {
            "ipw_ate_known_effect",
            "ipw_ate_extreme_scores",
            "ipw_att_known_effect",
            "ipw_att_extreme_control_weights",
            "ipw_ate_null_effect",
        }:
            raise ValueError(f"unknown IPW fixture_id: {fixture_id}")
    if reverse_rows:
        rows = tuple(reversed(rows))
    rows = tuple(sorted(rows, key=lambda row: str(row["account_id"])))
    execution = IPWExecutionRequest(
        identification_result=identification,
        propensity_result=propensity,
        binding=IPWOutcomeBinding(outcome_column="conversion"),
        configuration=config,
    )
    return IPWTreatmentEffectEstimator(
        engine=engine,
        observability_provider=observability_provider,
    ).analyze(
        execution,
        AnalysisTable.from_records(rows),
        provenance=_provenance(f"issue-101-ipw:{fixture_id}"),
    )


__all__ = [
    "observational_identification_request",
    "observational_propensity_request",
    "run_identification_fixture",
    "run_ipw_fixture",
    "run_propensity_fixture",
]
