"""Offline owned-result fixtures for business-impact source adapters."""

from __future__ import annotations

from collections.abc import Sequence

from packages.experiments.analysis import (
    AnalysisRequest,
    AnalysisTable,
    AnalysisUnit,
    EstimandDefinition,
    EstimandKind,
    MetricType,
    OutcomeDataBinding,
    RandomizedAnalysisMethod,
    RequestedConfidenceLevel,
    RequestedCredibleLevel,
    SampleCounts,
)
from packages.experiments.analysis.causal.advanced.models import (
    AdvancedAdapterProvenance,
    AdvancedCausalResult,
    AdvancedEstimatorConfig,
    AdvancedInference,
)
from packages.experiments.analysis.causal.did import (
    DifferenceInDifferencesResult,
    DifferenceInDifferencesService,
)
from packages.experiments.analysis.causal.dml import DMLResult, DoubleMachineLearningEstimator
from packages.experiments.analysis.causal.hte import (
    HeterogeneousEffectEstimator,
    HeterogeneousEffectResult,
)
from packages.experiments.analysis.causal.ipw import (
    IPWTreatmentEffectEstimator,
    TreatmentEffectResult,
)
from packages.experiments.analysis.randomized import (
    AlternativeHypothesis,
    RandomizedAnalysisExecutionRequest,
    RandomizedAnalysisResult,
    RandomizedAnalysisService,
)
from packages.experiments.analysis.randomized.bayesian import (
    BayesianAnalysisExecutionRequest,
    BayesianAnalysisResult,
    BayesianAnalysisService,
    BernoulliBinomialLikelihood,
    BetaPrior,
)
from packages.experiments.analysis.randomized.cuped import (
    CupedAnalysisExecutionRequest,
    CupedAnalysisResult,
    CupedAnalysisService,
)
from packages.experiments.analysis.randomized.sequential import (
    SequentialAnalysisHistory,
    SequentialAnalysisService,
    SequentialLookExecution,
)
from packages.experiments.analysis.study_designs import CovariateRole
from packages.experiments.analysis.validation import (
    AnalysisDataBinding,
    MetricColumnBinding,
    ValidationPolicy,
)
from tests.analysis_contract_fixtures import covariate, randomized_request, source
from tests.causal_identification_fixtures import provenance
from tests.did_fixtures import did_execution, did_table, positive_effect_rows
from tests.dml_fixtures import dml_execution, dml_table
from tests.hte_fixtures import effect_rows, hte_execution, hte_table
from tests.ipw_fixtures import ipw_execution, ipw_table
from tests.sequential_fixtures import sequential_plan


def _request(metric_type: MetricType, *, bayesian: bool = False) -> AnalysisRequest:
    uncertainty = (
        RequestedCredibleLevel(level=0.95) if bayesian else RequestedConfidenceLevel(level=0.95)
    )
    request = randomized_request(uncertainty=uncertainty)
    outcome = request.outcome.model_copy(
        update={"metric": request.outcome.metric.model_copy(update={"metric_type": metric_type})}
    )
    estimand = (
        EstimandKind.DIFFERENCE_IN_PROPORTIONS
        if metric_type is MetricType.BINARY
        else EstimandKind.DIFFERENCE_IN_MEANS
    )
    design = request.study_design
    if bayesian:
        design = design.model_copy(update={"method": RandomizedAnalysisMethod.BAYESIAN_AB})
    return request.model_copy(
        update={
            "estimand": EstimandDefinition(kind=estimand),
            "outcome": outcome,
            "study_design": design,
            "unit_of_analysis": AnalysisUnit(unit_id="account", label="Account"),
            "sample_counts": SampleCounts(total=40, treatment=20, control=20),
        }
    )


def _table(treatment: Sequence[object], control: Sequence[object]) -> AnalysisTable:
    rows = tuple(
        (f"treatment-{index}", "treatment", value) for index, value in enumerate(treatment)
    ) + tuple((f"control-{index}", "control", value) for index, value in enumerate(control))
    return AnalysisTable(columns=("unit_id", "arm", "outcome"), rows=rows)


def _binding() -> AnalysisDataBinding:
    return AnalysisDataBinding(
        treatment_column="arm",
        outcome=OutcomeDataBinding(value_column="outcome"),
        observation_unit_column="unit_id",
        randomization_unit_column="unit_id",
    )


def randomized_result(*, binary: bool = False) -> RandomizedAnalysisResult:
    metric_type = MetricType.BINARY if binary else MetricType.CONTINUOUS
    request = _request(metric_type)
    treatment = (1,) * 14 + (0,) * 6 if binary else tuple(range(11, 31))
    control = (1,) * 8 + (0,) * 12 if binary else tuple(range(1, 21))
    return RandomizedAnalysisService().analyze(
        RandomizedAnalysisExecutionRequest(
            request_id="impact-randomized",
            analysis_request=request,
            alternative=AlternativeHypothesis.TWO_SIDED,
        ),
        _table(treatment, control),
        _binding(),
        provenance=(source(),),
    )


def sequential_result() -> SequentialAnalysisHistory:
    from datetime import UTC, datetime

    plan = sequential_plan(information_times=(1.0,))
    assert plan.plan_fingerprint is not None
    look = SequentialLookExecution(
        look_index=1,
        information_time=1.0,
        plan_fingerprint=plan.plan_fingerprint,
        analysis_request=plan.analysis_request,
        table=_table(tuple(range(20, 40)), tuple(range(20))),
        binding=_binding(),
        executed_at=datetime(2026, 7, 2, tzinfo=UTC),
    )
    return SequentialAnalysisService().analyze(plan, (look,), provenance=(source(),))


def bayesian_result() -> BayesianAnalysisResult:
    request = _request(MetricType.BINARY, bayesian=True)
    prior = BetaPrior(alpha=1.0, beta=1.0, provenance=(source(),))
    return BayesianAnalysisService().analyze(
        BayesianAnalysisExecutionRequest(
            request_id="impact-bayesian",
            analysis_request=request,
            treatment_prior=prior,
            control_prior=prior,
            likelihood=BernoulliBinomialLikelihood(),
        ),
        _table((1,) * 14 + (0,) * 6, (1,) * 8 + (0,) * 12),
        _binding(),
        provenance=(source(),),
    )


def cuped_result() -> CupedAnalysisResult:
    request = _request(MetricType.CONTINUOUS)
    cuped_covariate = covariate().model_copy(update={"role": CovariateRole.CUPED})
    request = request.model_copy(
        update={
            "study_design": request.study_design.model_copy(
                update={"method": RandomizedAnalysisMethod.CUPED}
            ),
            "sample_counts": SampleCounts(total=8, treatment=4, control=4),
            "covariates": (cuped_covariate,),
        }
    )
    table = AnalysisTable(
        columns=("unit_id", "arm", "outcome", "prior_orders"),
        rows=tuple(
            (f"control-{index}", "control", outcome, float(index))
            for index, outcome in enumerate((0.0, 3.0, 3.0, 6.0))
        )
        + tuple(
            (f"treatment-{index}", "treatment", outcome, float(index))
            for index, outcome in enumerate((4.0, 4.0, 7.0, 10.0))
        ),
    )
    binding = AnalysisDataBinding(
        treatment_column="arm",
        outcome=OutcomeDataBinding(value_column="outcome"),
        observation_unit_column="unit_id",
        randomization_unit_column="unit_id",
        covariates=(
            MetricColumnBinding(metric_id=cuped_covariate.metric.metric_id, column="prior_orders"),
        ),
    )
    return CupedAnalysisService(
        validation_policy=ValidationPolicy(
            minimum_total=4,
            minimum_per_arm=2,
            weak_total=4,
            weak_per_arm=2,
        )
    ).analyze(
        CupedAnalysisExecutionRequest(
            request_id="impact-cuped",
            analysis_request=request,
            alternative=AlternativeHypothesis.TWO_SIDED,
        ),
        table,
        binding,
        provenance=(source(),),
    )


def ipw_result(*, att: bool = False, binary: bool = False) -> TreatmentEffectResult:
    from packages.experiments.analysis.causal import CausalEstimandKind

    estimand = CausalEstimandKind.ATT if att else CausalEstimandKind.ATE
    return IPWTreatmentEffectEstimator().analyze(
        ipw_execution(estimand=estimand, binary=binary),
        ipw_table(),
        provenance=provenance("impact-ipw"),
    )


def did_result() -> DifferenceInDifferencesResult:
    return DifferenceInDifferencesService().analyze(
        did_execution(),
        did_table(positive_effect_rows()),
        provenance=provenance("impact-did"),
    )


def dml_result() -> DMLResult:
    rows = tuple(
        {
            "account_id": f"unit-{index:03d}",
            "treated": int((index * 17 + 3) % 7 < 3),
            "outcome": 2.0 * int((index * 17 + 3) % 7 < 3)
            + 0.7 * ((index - 39.5) / 10.0)
            + (-0.4, 0.2, 0.5, -0.3, 0.1)[index % 5],
            "prior_orders": (index - 39.5) / 10.0,
        }
        for index in range(80)
    )
    return DoubleMachineLearningEstimator().analyze(
        dml_execution(fold_count=4, seed=812),
        dml_table(rows),
        provenance=provenance("impact-dml"),
    )


def hte_result() -> HeterogeneousEffectResult:
    return HeterogeneousEffectEstimator().analyze(
        hte_execution(fold_count=4),
        hte_table(effect_rows()),
        provenance=provenance("impact-hte"),
    )


def _advanced_provenance(
    *,
    estimand: str,
    adapter_id: str,
    estimator_class: str,
    fold_fingerprint: str,
) -> AdvancedAdapterProvenance:
    configuration = AdvancedEstimatorConfig(constant_effect_assumption=True)
    return AdvancedAdapterProvenance(
        adapter_id=adapter_id,
        econml_version="0.17.0",
        estimator_class=estimator_class,
        estimator_configuration=(),
        estimand=estimand,  # type: ignore[arg-type]
        nuisance_configuration=configuration,
        seed=812,
        random_state=812,
        nuisance_seed=812,
        fold_count=4,
        fold_fingerprint_sha256=fold_fingerprint,
        features=(),
        python_version="3.12",
        platform="offline-test",
        dependencies=(),
    )


def advanced_result() -> AdvancedCausalResult:
    base = dml_result()
    execution = dml_execution(fold_count=4, seed=812)
    assert base.fold_plan is not None
    assert base.test_result is not None
    assert base.point_estimate is not None
    provenance = _advanced_provenance(
        estimand="ate",
        adapter_id="experimentos_econml_dml",
        estimator_class="LinearDML",
        fold_fingerprint=base.fold_plan.fingerprint_sha256,
    )
    return AdvancedCausalResult(
        configuration_fingerprint_sha256=base.configuration_fingerprint_sha256,
        execution_request=execution,
        configuration=provenance.nuisance_configuration,
        status=base.status,
        point_estimate=base.point_estimate,
        inference=AdvancedInference(
            standard_error=base.test_result.standard_error,
            statistic=base.test_result.statistic,
            p_value=base.test_result.p_value,
            confidence_interval=base.test_result.confidence_interval,
        ),
        sample_counts=base.sample_counts,
        overlap=base.overlap,
        nuisance_diagnostics=base.nuisance_diagnostics,
        fold_plan=base.fold_plan,
        fold_fits=base.fold_fits,
        diagnostics=base.diagnostics,
        evidence_limitations=base.evidence_limitations,
        adapter_provenance=provenance,
        provenance=base.provenance,
    )


def econml_hte_result() -> HeterogeneousEffectResult:
    base = hte_result()
    assert base.fold_plan is not None
    provenance = _advanced_provenance(
        estimand="cate",
        adapter_id="experimentos_econml_hte",
        estimator_class="LinearDML",
        fold_fingerprint=base.fold_plan.fingerprint_sha256,
    )
    return HeterogeneousEffectResult.model_validate(
        base.model_copy(update={"adapter_provenance": provenance}).model_dump(mode="python")
    )
