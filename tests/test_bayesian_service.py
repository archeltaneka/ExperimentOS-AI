"""Eligibility, dispatch, abstention, and provenance tests for Bayesian A/B service."""

from __future__ import annotations

from collections.abc import Sequence

from packages.experiments.analysis import (
    AnalysisRequest,
    AnalysisUnit,
    EstimandDefinition,
    EstimandKind,
    MetricType,
    RandomizedAnalysisMethod,
    RequestedCredibleLevel,
    SampleCounts,
)
from packages.experiments.analysis.randomized.bayesian import (
    BayesianAnalysisExecutionRequest,
    BayesianAnalysisService,
    BayesianComputationStatus,
    BernoulliBinomialLikelihood,
    BetaPrior,
    NormalInverseGammaPrior,
    NormalUnknownMeanVarianceLikelihood,
)
from packages.experiments.analysis.validation import (
    AnalysisDataBinding,
    AnalysisTable,
    OutcomeDataBinding,
)
from tests.analysis_contract_fixtures import proportion_unit, randomized_request, source


def _request(metric_type: MetricType, *, treatment: int = 20, control: int = 20) -> AnalysisRequest:
    request = randomized_request(uncertainty=RequestedCredibleLevel(level=0.95))
    unit = AnalysisUnit(unit_id="account", label="Account")
    estimand = (
        EstimandKind.DIFFERENCE_IN_PROPORTIONS
        if metric_type is MetricType.BINARY
        else EstimandKind.DIFFERENCE_IN_MEANS
    )
    outcome = request.outcome.model_copy(
        update={"metric": request.outcome.metric.model_copy(update={"metric_type": metric_type})}
    )
    return request.model_copy(
        update={
            "estimand": EstimandDefinition(kind=estimand),
            "outcome": outcome,
            "study_design": request.study_design.model_copy(
                update={"method": RandomizedAnalysisMethod.BAYESIAN_AB}
            ),
            "sample_counts": SampleCounts(
                total=treatment + control,
                treatment=treatment,
                control=control,
            ),
            "unit_of_analysis": unit,
        }
    )


def _table(treatment: Sequence[object], control: Sequence[object]) -> AnalysisTable:
    rows = tuple(
        (f"treatment-{index}", "treatment", value)
        for index, value in enumerate(treatment)
    ) + tuple((f"control-{index}", "control", value) for index, value in enumerate(control))
    return AnalysisTable(columns=("unit_id", "arm", "outcome"), rows=rows)


def _binding() -> AnalysisDataBinding:
    return AnalysisDataBinding(
        treatment_column="arm",
        outcome=OutcomeDataBinding(value_column="outcome"),
        observation_unit_column="unit_id",
        randomization_unit_column="unit_id",
    )


def _beta_execution(request: AnalysisRequest) -> BayesianAnalysisExecutionRequest:
    prior = BetaPrior(alpha=1.0, beta=1.0, provenance=(source(),))
    return BayesianAnalysisExecutionRequest(
        request_id="bayes-service-binary",
        analysis_request=request,
        treatment_prior=prior,
        control_prior=prior,
        likelihood=BernoulliBinomialLikelihood(),
    )


def _nig_execution(request: AnalysisRequest) -> BayesianAnalysisExecutionRequest:
    prior = NormalInverseGammaPrior(
        mu_0=0.0,
        kappa_0=1.0,
        alpha_0=2.0,
        beta_0=2.0,
        provenance=(source(),),
    )
    return BayesianAnalysisExecutionRequest(
        request_id="bayes-service-continuous",
        analysis_request=request,
        treatment_prior=prior,
        control_prior=prior,
        likelihood=NormalUnknownMeanVarianceLikelihood(),
    )


def test_service_dispatches_binary_and_preserves_complete_provenance() -> None:
    request = _request(MetricType.BINARY)
    result = BayesianAnalysisService().analyze(
        _beta_execution(request),
        _table((1,) * 14 + (0,) * 6, (1,) * 8 + (0,) * 12),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is BayesianComputationStatus.COMPLETED
    assert result.analysis_request == request
    assert result.likelihood == BernoulliBinomialLikelihood()
    assert result.treatment_prior is not None
    assert result.treatment_prior.provenance == (source(),)
    assert result.treatment_posterior is not None
    assert result.treatment_posterior.posterior_family == "beta"
    assert result.effect is not None
    assert result.effect.credible_interval.kind == "credible_interval"
    assert result.configuration_provenance == result.configuration.configuration_provenance()
    assert any(item.source_type == "analysis_request" for item in result.provenance)


def test_service_dispatches_continuous_normal_inverse_gamma() -> None:
    request = _request(MetricType.CONTINUOUS, treatment=4, control=4)
    result = BayesianAnalysisService().analyze(
        _nig_execution(request),
        _table((2.0, 3.0, 4.0, 5.0), (1.0, 2.0, 3.0, 4.0)),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is BayesianComputationStatus.COMPLETED
    assert result.treatment_posterior is not None
    assert result.treatment_posterior.posterior_family == "normal_inverse_gamma"
    assert result.effect is not None
    assert result.effect.posterior_mean > 0.0


def test_sparse_and_all_zero_binary_data_are_not_blocked_by_frequentist_rules() -> None:
    request = _request(MetricType.BINARY, treatment=1, control=1)
    result = BayesianAnalysisService().analyze(
        _beta_execution(request),
        _table((0,), (0,)),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is BayesianComputationStatus.COMPLETED
    assert result.effect is not None
    assert result.effect.probability_of_superiority.probability == 0.5
    assert any(item.code == "eligibility.outcome.zero_variance" for item in result.diagnostics)


def test_one_observation_continuous_arm_abstains_as_inadequate_evidence() -> None:
    request = _request(MetricType.CONTINUOUS, treatment=1, control=2)
    result = BayesianAnalysisService().analyze(
        _nig_execution(request),
        _table((1.0,), (1.0, 2.0)),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is BayesianComputationStatus.ABSTAINED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "continuous_arm_inadequate"
    assert result.effect is None


def test_likelihood_outcome_mismatch_returns_typed_unsupported_result() -> None:
    request = _request(MetricType.CONTINUOUS, treatment=2, control=2)
    result = BayesianAnalysisService().analyze(
        _beta_execution(request),
        _table((1.0, 2.0), (1.0, 2.0)),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is BayesianComputationStatus.UNSUPPORTED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "likelihood_outcome_mismatch"
    assert result.effect is None


def test_invalid_prior_payload_returns_diagnostic_without_repairing_prior() -> None:
    request = _request(MetricType.BINARY, treatment=2, control=2)
    valid = _beta_execution(request).model_dump(mode="python")
    assert isinstance(valid["treatment_prior"], dict)
    valid["treatment_prior"]["alpha"] = 0.0

    result = BayesianAnalysisService().analyze_payload(
        valid,
        _table((1, 0), (0, 1)),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is BayesianComputationStatus.INVALID
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "invalid_prior"
    assert result.treatment_prior is None
    assert result.effect is None
    assert any(item.code == "declaration.invalid_prior" for item in result.diagnostics)
    assert "0.0" not in result.abstention_reason.message


def test_unknown_likelihood_payload_returns_typed_unsupported_result() -> None:
    request = _request(MetricType.BINARY, treatment=2, control=2)
    payload = _beta_execution(request).model_dump(mode="python")
    assert isinstance(payload["likelihood"], dict)
    payload["likelihood"]["likelihood_family"] = "poisson"

    result = BayesianAnalysisService().analyze_payload(
        payload,
        _table((1, 0), (0, 1)),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is BayesianComputationStatus.UNSUPPORTED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "unsupported_likelihood"
    assert result.likelihood is None


def test_invalid_rope_payload_returns_typed_invalid_result() -> None:
    request = _request(MetricType.BINARY, treatment=2, control=2)
    payload = _beta_execution(request).model_dump(mode="python")
    payload["rope"] = {
        "lower": 0.1,
        "upper": -0.1,
        "unit": proportion_unit().model_dump(mode="python"),
    }

    result = BayesianAnalysisService().analyze_payload(
        payload,
        _table((1, 0), (0, 1)),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is BayesianComputationStatus.INVALID
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "invalid_rope"
    assert result.effect is None


def test_count_metric_is_unsupported_for_declared_binary_likelihood() -> None:
    request = _request(MetricType.COUNT, treatment=2, control=2)
    result = BayesianAnalysisService().analyze(
        _beta_execution(request),
        _table((1, 0), (0, 1)),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is BayesianComputationStatus.UNSUPPORTED
    assert result.abstention_reason is not None
    assert result.abstention_reason.code == "likelihood_outcome_mismatch"


def test_prior_information_context_is_explicit_and_does_not_change_status() -> None:
    request = _request(MetricType.BINARY, treatment=2, control=2)
    result = BayesianAnalysisService().analyze(
        _beta_execution(request).model_copy(
            update={
                "treatment_prior": BetaPrior(
                    alpha=20.0,
                    beta=20.0,
                    provenance=(source(),),
                )
            }
        ),
        _table((1, 0), (0, 1)),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is BayesianComputationStatus.COMPLETED
    treatment_context = next(
        item for item in result.diagnostics if item.code == "prior.treatment_information_context"
    )
    values = {item.key: item.value for item in treatment_context.context}
    assert values == {
        "heuristic": "beta_effective_sample_size_gt_observed_n",
        "observed_n": 2,
        "prior_dominated": True,
        "prior_effective_sample_size": 40.0,
    }
    assert any(item.code == "prior.treatment_dominance" for item in result.warnings)
