from __future__ import annotations

from datetime import UTC, datetime

from packages.experiments.analysis import (
    AbstainedAnalysisResult,
    AbstentionReason,
    AnalysisRequest,
    AnalysisStatus,
    AnalysisUnit,
    BusinessImpactInputs,
    BusinessImpactProjection,
    Clustered,
    ConclusionType,
    ConfidenceInterval,
    ControlDefinition,
    CovariateDefinition,
    CovariateRole,
    CovariateTiming,
    EffectEstimateDetails,
    EstimandDefinition,
    EstimandKind,
    MeasuredValue,
    MetricDefinition,
    MetricType,
    MetricUnit,
    NoClustering,
    ObservationalAnalysisMethod,
    ObservationalStudyDesign,
    OutcomeDirection,
    OutcomeMetric,
    PopulationDefinition,
    PreTreatmentMetric,
    ProjectedValue,
    ProvenanceRecord,
    ProvenanceSourceType,
    QuasiExperimentalDesign,
    QuasiExperimentalMethod,
    RandomizedAnalysisMethod,
    RandomizedExperimentDesign,
    RandomizedExperimentEstimate,
    RequestedConfidenceLevel,
    RequestedUncertainty,
    SampleCounts,
    SourcedCount,
    SourcedCurrency,
    SourcedMoney,
    SourcedProportion,
    SourcedQuantity,
    SourcedTimePeriod,
    TimePeriod,
    TreatmentDefinition,
    TreatmentRelationship,
    UncertaintyBundle,
    UnitDimension,
    ValueScale,
)

RANDOMIZED_START = datetime(2026, 7, 1, tzinfo=UTC)
RANDOMIZED_END = datetime(2026, 7, 15, tzinfo=UTC)
OBSERVATIONAL_START = datetime(2026, 6, 1, tzinfo=UTC)
OBSERVATIONAL_END = datetime(2026, 6, 30, tzinfo=UTC)
QUASI_PRE_START = datetime(2026, 6, 1, tzinfo=UTC)
QUASI_POST_START = datetime(2026, 7, 1, tzinfo=UTC)
QUASI_POST_END = datetime(2026, 7, 15, tzinfo=UTC)


def utc(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


def proportion_unit() -> MetricUnit:
    return MetricUnit(
        dimension=UnitDimension.PROPORTION,
        value_scale=ValueScale.PROPORTION,
        symbol="1",
        scale_to_base_unit=1.0,
    )


def count_unit() -> MetricUnit:
    return MetricUnit(
        dimension=UnitDimension.COUNT,
        value_scale=ValueScale.RAW,
        symbol="count",
        scale_to_base_unit=1.0,
    )


def currency_unit(currency_code: str = "USD") -> MetricUnit:
    return MetricUnit(
        dimension=UnitDimension.CURRENCY,
        value_scale=ValueScale.RAW,
        symbol=currency_code,
        scale_to_base_unit=1.0,
        currency_code=currency_code,
    )


def population(
    *,
    population_id: str = "checkout_users",
    label: str = "Checkout users",
) -> PopulationDefinition:
    return PopulationDefinition(population_id=population_id, label=label, criteria=())


def outcome(
    *,
    metric_id: str = "payment_success_rate",
    label: str = "Payment success rate",
) -> OutcomeMetric:
    return OutcomeMetric(
        metric=MetricDefinition(
            metric_id=metric_id,
            label=label,
            metric_type=MetricType.PROPORTION,
            unit=proportion_unit(),
        ),
        direction=OutcomeDirection.INCREASE,
    )


def randomized_design(
    *,
    treatment_allocation: float = 0.5,
    control_allocation: float = 0.5,
) -> RandomizedExperimentDesign:
    return RandomizedExperimentDesign(
        method=RandomizedAnalysisMethod.FIXED_HORIZON_AB,
        experiment_period=TimePeriod(start=RANDOMIZED_START, end=RANDOMIZED_END),
        randomization_unit=AnalysisUnit(unit_id="account", label="Account"),
        treatment_allocation=treatment_allocation,
        control_allocation=control_allocation,
    )


def covariate(
    *,
    timing: CovariateTiming = CovariateTiming.PRE_TREATMENT,
    role: CovariateRole = CovariateRole.ADJUSTMENT,
    treatment_relationship: TreatmentRelationship = TreatmentRelationship.NONE_KNOWN,
) -> CovariateDefinition:
    return CovariateDefinition(
        metric=MetricDefinition(
            metric_id="prior_order_count",
            label="Prior order count",
            metric_type=MetricType.COUNT,
            unit=count_unit(),
        ),
        timing=timing,
        role=role,
        treatment_relationship=treatment_relationship,
        measurement_period=TimePeriod(start=utc(2026, 5, 1), end=utc(2026, 6, 1)),
    )


def randomized_request(
    *,
    control_id: str = "standard_payment",
    control_label: str = "Standard payment",
    control_assignment_value: str = "control",
    pre_treatment_metrics: tuple[PreTreatmentMetric, ...] = (),
    uncertainty: RequestedUncertainty | None = None,
) -> AnalysisRequest:
    return AnalysisRequest(
        population=population(),
        treatment=TreatmentDefinition(
            treatment_id="ranked_payment",
            label="Ranked payment",
            assignment_value="treatment",
            description="Rank payment methods using the recommendation model.",
        ),
        control=ControlDefinition(
            control_id=control_id,
            label=control_label,
            assignment_value=control_assignment_value,
            description="Use the standard payment-method ordering.",
        ),
        outcome=outcome(),
        estimand=EstimandDefinition(kind=EstimandKind.INTENTION_TO_TREAT),
        study_design=randomized_design(),
        unit_of_analysis=AnalysisUnit(unit_id="order", label="Order"),
        clustering=NoClustering(),
        sample_counts=SampleCounts(total=200, treatment=100, control=100),
        uncertainty=uncertainty or RequestedConfidenceLevel(level=0.95),
        pre_treatment_metrics=pre_treatment_metrics,
    )


def quasi_experimental_request(
    *,
    pre_treatment_metrics: tuple[PreTreatmentMetric, ...] = (),
) -> AnalysisRequest:
    return AnalysisRequest(
        population=population(),
        treatment=TreatmentDefinition(
            treatment_id="ranked_payment",
            label="Ranked payment",
            assignment_value="treatment",
            description="Rank payment methods using the recommendation model.",
        ),
        control=ControlDefinition(
            control_id="standard_payment",
            label="Standard payment",
            assignment_value="control",
            description="Use the standard payment-method ordering.",
        ),
        outcome=outcome(),
        estimand=EstimandDefinition(kind=EstimandKind.AVERAGE_TREATMENT_EFFECT),
        study_design=QuasiExperimentalDesign(
            method=QuasiExperimentalMethod.DIFFERENCE_IN_DIFFERENCES,
            pre_treatment_period=TimePeriod(
                start=QUASI_PRE_START,
                end=QUASI_POST_START,
            ),
            post_treatment_period=TimePeriod(
                start=QUASI_POST_START,
                end=QUASI_POST_END,
            ),
        ),
        unit_of_analysis=AnalysisUnit(unit_id="order", label="Order"),
        clustering=NoClustering(),
        sample_counts=SampleCounts(total=200, treatment=100, control=100),
        uncertainty=RequestedConfidenceLevel(level=0.95),
        pre_treatment_metrics=pre_treatment_metrics,
    )


def observational_request() -> AnalysisRequest:
    customer = AnalysisUnit(unit_id="customer", label="Customer")
    return AnalysisRequest(
        population=population(
            population_id="eligible_customers",
            label="Eligible customers",
        ),
        treatment=TreatmentDefinition(
            treatment_id="offer_exposed",
            label="Offer exposed",
            assignment_value="exposed",
            description="Customers exposed to the offer.",
        ),
        control=ControlDefinition(
            control_id="offer_unexposed",
            label="Offer unexposed",
            assignment_value="unexposed",
            description="Customers not exposed to the offer.",
        ),
        outcome=outcome(metric_id="conversion_rate", label="Conversion rate"),
        estimand=EstimandDefinition(
            kind=EstimandKind.AVERAGE_TREATMENT_EFFECT_ON_TREATED,
        ),
        study_design=ObservationalStudyDesign(
            method=ObservationalAnalysisMethod.DOUBLE_MACHINE_LEARNING,
            observation_period=TimePeriod(
                start=OBSERVATIONAL_START,
                end=OBSERVATIONAL_END,
            ),
        ),
        unit_of_analysis=customer,
        clustering=Clustered(unit=customer),
        sample_counts=SampleCounts(total=300, treatment=120, control=180),
        uncertainty=RequestedConfidenceLevel(level=0.95),
        covariates=(covariate(),),
    )


def source() -> ProvenanceRecord:
    return ProvenanceRecord(
        source_type=ProvenanceSourceType.EXPERIMENT_DATA,
        source_id="exp-001-payment-recommendation",
    )


def effect_details(
    *,
    analysis_status: AnalysisStatus = AnalysisStatus.COMPLETED,
) -> EffectEstimateDetails:
    request = randomized_request()
    return EffectEstimateDetails(
        status=analysis_status,
        estimand=request.estimand,
        outcome=request.outcome,
        point_estimate=MeasuredValue(value=0.055, unit=proportion_unit()),
        uncertainty=UncertaintyBundle(
            measures=(
                ConfidenceInterval(
                    lower=0.002,
                    upper=0.108,
                    confidence_level=0.95,
                ),
            )
        ),
        sample_counts=request.sample_counts,
        assumptions=(),
        diagnostics=(),
        warnings=(),
        provenance=(source(),),
    )


def randomized_estimate(
    *,
    analysis_status: AnalysisStatus = AnalysisStatus.COMPLETED,
) -> RandomizedExperimentEstimate:
    return RandomizedExperimentEstimate(
        finding_type="randomized_experiment_estimate",
        conclusion_type=ConclusionType.CAUSAL_EFFECT,
        estimate=effect_details(analysis_status=analysis_status),
    )


def valid_business_inputs(*, input_currency: str = "USD") -> BusinessImpactInputs:
    provenance = (source(),)
    return BusinessImpactInputs(
        eligible_population=SourcedCount(value=100_000, provenance=provenance),
        exposure_frequency=SourcedQuantity(
            value=2.0,
            unit=MetricUnit(
                dimension=UnitDimension.CUSTOM,
                value_scale=ValueScale.CUSTOM,
                symbol="exposures/user/month",
                scale_to_base_unit=1.0,
                custom_dimension_name="exposures per user per month",
            ),
            provenance=provenance,
        ),
        baseline_rate=SourcedProportion(
            value=0.20,
            unit=proportion_unit(),
            provenance=provenance,
        ),
        average_order_value=SourcedMoney(
            value=80.0,
            unit=currency_unit(input_currency),
            provenance=provenance,
        ),
        contribution_margin=SourcedProportion(
            value=0.30,
            unit=proportion_unit(),
            provenance=provenance,
        ),
        rollout_proportion=SourcedProportion(
            value=0.50,
            unit=proportion_unit(),
            provenance=provenance,
        ),
        analysis_horizon=SourcedTimePeriod(
            value=TimePeriod(start=utc(2026, 8, 1), end=utc(2026, 9, 1)),
            provenance=provenance,
        ),
        currency=SourcedCurrency(value=input_currency, provenance=provenance),
    )


def valid_projection(
    *,
    projected_currency: str = "USD",
    input_currency: str = "USD",
) -> BusinessImpactProjection:
    return BusinessImpactProjection(
        status=AnalysisStatus.COMPLETED,
        conclusion_type=ConclusionType.PROJECTION,
        inputs=valid_business_inputs(input_currency=input_currency),
        source_estimate=randomized_estimate(),
        projected_incremental_outcome=ProjectedValue(
            value=MeasuredValue(value=550.0, unit=count_unit()),
            uncertainty=effect_details().uncertainty,
        ),
        projected_financial_impact=ProjectedValue(
            value=MeasuredValue(
                value=13_200.0,
                unit=currency_unit(projected_currency),
            ),
            uncertainty=effect_details().uncertainty,
        ),
        assumptions=(),
        diagnostics=(),
        warnings=(),
        provenance=(source(),),
    )


def abstained_result() -> AbstainedAnalysisResult:
    return AbstainedAnalysisResult(
        outcome_type="abstained",
        status=AnalysisStatus.ABSTAINED,
        reason=AbstentionReason(
            code="covariate_timing_unknown",
            message="Causal adjustment is unsafe.",
            missing_or_invalid_information=("covariate timing",),
        ),
        diagnostics=(),
        warnings=(),
        provenance=(source(),),
    )
