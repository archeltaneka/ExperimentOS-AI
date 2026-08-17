"""Contract tests for explicit Bayesian randomized-analysis declarations."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from packages.experiments.analysis import RandomizedAnalysisMethod
from packages.experiments.analysis.randomized.bayesian import (
    BayesianAnalysisExecutionRequest,
    BayesianAnalysisResult,
    BayesianComputationConfig,
    BayesianComputationStatus,
    BayesianDiagnostic,
    BayesianDiagnosticCategory,
    BayesianDiagnosticStatus,
    BernoulliBinomialLikelihood,
    BetaPosteriorSummary,
    BetaPrior,
    NormalInverseGammaPrior,
    NormalUnknownMeanVarianceLikelihood,
    PosteriorEffectSummary,
    PracticalEquivalenceRegion,
    QuadratureDiagnostics,
)
from packages.experiments.analysis.serialization import (
    bayesian_analysis_result_from_json,
    to_canonical_json,
)
from packages.experiments.analysis.uncertainty import (
    CredibleInterval,
    PosteriorProbability,
    RequestedCredibleLevel,
)
from tests.analysis_contract_fixtures import proportion_unit, randomized_request, source


def _bayesian_request():
    request = randomized_request(uncertainty=RequestedCredibleLevel(level=0.95))
    return request.model_copy(
        update={
            "study_design": request.study_design.model_copy(
                update={"method": RandomizedAnalysisMethod.BAYESIAN_AB}
            )
        }
    )


def test_beta_prior_requires_explicit_positive_finite_hyperparameters() -> None:
    valid = BetaPrior(alpha=1.0, beta=2.0, provenance=(source(),), label="Fixture prior")

    assert valid.prior_family == "beta"
    assert valid.prior_family_version == "1"
    assert valid.alpha == 1.0
    assert valid.beta == 2.0
    assert valid.effective_sample_size == 3.0

    for field, value in (
        ("alpha", 0.0),
        ("alpha", -1.0),
        ("alpha", math.inf),
        ("beta", 0.0),
        ("beta", math.nan),
    ):
        payload = {"alpha": 1.0, "beta": 1.0, "provenance": (source(),)}
        payload[field] = value
        with pytest.raises(ValidationError):
            BetaPrior.model_validate(payload)

    with pytest.raises(ValidationError):
        BetaPrior.model_validate({"alpha": 1.0, "beta": 1.0})


def test_normal_inverse_gamma_prior_locks_shape_scale_parameterization() -> None:
    prior = NormalInverseGammaPrior(
        mu_0=0.0,
        kappa_0=1.0,
        alpha_0=2.0,
        beta_0=3.0,
        provenance=(source(),),
        label="Reference NIG prior",
    )

    assert prior.prior_family == "normal_inverse_gamma"
    assert prior.prior_family_version == "1"
    assert prior.parameterization == "inverse_gamma_shape_scale"

    for field, value in (
        ("mu_0", math.inf),
        ("kappa_0", 0.0),
        ("alpha_0", -1.0),
        ("beta_0", math.nan),
    ):
        payload = {
            "mu_0": 0.0,
            "kappa_0": 1.0,
            "alpha_0": 2.0,
            "beta_0": 3.0,
            "provenance": (source(),),
        }
        payload[field] = value
        with pytest.raises(ValidationError):
            NormalInverseGammaPrior.model_validate(payload)


def test_rope_requires_ordered_finite_bounds_and_explicit_unit() -> None:
    rope = PracticalEquivalenceRegion(
        lower=-0.01,
        upper=0.02,
        unit=proportion_unit(),
    )

    assert rope.lower == -0.01
    assert rope.upper == 0.02
    assert rope.effect_scale == "raw_treatment_minus_control"

    for lower, upper in ((0.0, 0.0), (0.1, -0.1), (math.nan, 0.1)):
        with pytest.raises(ValidationError):
            PracticalEquivalenceRegion(lower=lower, upper=upper, unit=proportion_unit())


def test_execution_request_requires_explicit_compatible_priors_and_likelihood() -> None:
    prior = BetaPrior(alpha=1.0, beta=1.0, provenance=(source(),))
    execution = BayesianAnalysisExecutionRequest(
        request_id="bayes-contract",
        analysis_request=_bayesian_request(),
        treatment_prior=prior,
        control_prior=prior,
        likelihood=BernoulliBinomialLikelihood(),
    )

    assert execution.treatment_prior == prior
    assert execution.control_prior == prior
    assert execution.likelihood.likelihood_family == "bernoulli_binomial"
    assert execution.rope is None

    with pytest.raises(ValidationError):
        BayesianAnalysisExecutionRequest.model_validate(
            {
                "request_id": "missing-priors",
                "analysis_request": _bayesian_request(),
                "likelihood": BernoulliBinomialLikelihood(),
            }
        )

    with pytest.raises(ValidationError, match="Beta priors"):
        BayesianAnalysisExecutionRequest(
            request_id="wrong-prior-family",
            analysis_request=_bayesian_request(),
            treatment_prior=NormalInverseGammaPrior(
                mu_0=0.0,
                kappa_0=1.0,
                alpha_0=2.0,
                beta_0=2.0,
                provenance=(source(),),
            ),
            control_prior=prior,
            likelihood=BernoulliBinomialLikelihood(),
        )

    with pytest.raises(ValidationError, match="BAYESIAN_AB"):
        BayesianAnalysisExecutionRequest(
            request_id="wrong-method",
            analysis_request=randomized_request(),
            treatment_prior=prior,
            control_prior=prior,
            likelihood=BernoulliBinomialLikelihood(),
        )


def test_likelihood_contracts_are_explicit_and_versioned() -> None:
    binary = BernoulliBinomialLikelihood()
    continuous = NormalUnknownMeanVarianceLikelihood()

    assert binary.model_dump(mode="json") == {
        "likelihood_family": "bernoulli_binomial",
        "likelihood_family_version": "1",
        "success_value": 1,
    }
    assert continuous.model_dump(mode="json") == {
        "likelihood_family": "normal_unknown_mean_variance",
        "likelihood_family_version": "1",
        "variance_convention": "arm_specific_unknown_variance",
    }


def _completed_binary_result() -> BayesianAnalysisResult:
    request = _bayesian_request()
    prior = BetaPrior(alpha=1.0, beta=1.0, provenance=(source(),))
    interval = CredibleInterval(lower=-0.2, upper=0.4, credible_level=0.95)
    control = BetaPosteriorSummary(
        arm_id=request.control.control_id,
        n=10,
        successes=4,
        failures=6,
        prior=prior,
        posterior_alpha=5.0,
        posterior_beta=7.0,
        posterior_mean=5.0 / 12.0,
        posterior_variance=35.0 / 1872.0,
        credible_interval=CredibleInterval(lower=0.15, upper=0.70, credible_level=0.95),
    )
    treatment = BetaPosteriorSummary(
        arm_id=request.treatment.treatment_id,
        n=10,
        successes=6,
        failures=4,
        prior=prior,
        posterior_alpha=7.0,
        posterior_beta=5.0,
        posterior_mean=7.0 / 12.0,
        posterior_variance=35.0 / 1872.0,
        credible_interval=CredibleInterval(lower=0.30, upper=0.85, credible_level=0.95),
    )
    effect = PosteriorEffectSummary(
        posterior_mean=1.0 / 6.0,
        posterior_median=1.0 / 6.0,
        posterior_standard_deviation=(70.0 / 1872.0) ** 0.5,
        credible_interval=interval,
        probability_of_superiority=PosteriorProbability(
            probability=0.8,
            event="treatment outcome parameter > control outcome parameter",
        ),
        probability_treatment_is_better=PosteriorProbability(
            probability=0.8,
            event="treatment outcome parameter > control outcome parameter; direction=increase",
        ),
        metric_direction=request.outcome.direction,
        quadrature=QuadratureDiagnostics(
            maximum_absolute_error=1e-12,
            absolute_tolerance=1e-10,
            relative_tolerance=1e-10,
        ),
    )
    return BayesianAnalysisResult(
        request_id="bayes-result",
        analysis_request=request,
        metric=request.outcome.metric,
        estimand=request.estimand,
        treatment_arm_id=request.treatment.treatment_id,
        control_arm_id=request.control.control_id,
        status=BayesianComputationStatus.COMPLETED,
        likelihood=BernoulliBinomialLikelihood(),
        treatment_prior=prior,
        control_prior=prior,
        treatment_posterior=treatment,
        control_posterior=control,
        effect=effect,
        assumptions=(),
        diagnostics=(
            BayesianDiagnostic(
                code="posterior.valid",
                category=BayesianDiagnosticCategory.RESULT,
                status=BayesianDiagnosticStatus.PASSED,
                message="Posterior values are finite.",
            ),
        ),
        warnings=(),
        provenance=(source(),),
        configuration=BayesianComputationConfig(),
    )


def test_completed_result_round_trips_without_frequentist_semantics() -> None:
    result = _completed_binary_result()
    payload = to_canonical_json(result)

    assert bayesian_analysis_result_from_json(payload) == result
    assert '"credible_interval"' in payload
    assert '"confidence_interval"' not in payload
    assert '"p_value"' not in payload
    assert '"significance"' not in payload
    assert result.configuration.interval_method == "equal_tailed"
    assert result.configuration.effect_method == "deterministic_quadrature"


def test_completed_result_requires_posteriors_and_effect() -> None:
    result = _completed_binary_result()

    with pytest.raises(ValidationError, match="numerical Bayesian results"):
        BayesianAnalysisResult.model_validate(
            result.model_copy(update={"effect": None}).model_dump(mode="python")
        )


def test_diagnostics_have_canonical_order_and_finite_context() -> None:
    result = _completed_binary_result()
    later = BayesianDiagnostic(
        code="z-later",
        category=BayesianDiagnosticCategory.RESULT,
        status=BayesianDiagnosticStatus.PASSED,
        message="Later diagnostic.",
        context={"sample_count": 20, "likelihood": "binary"},
    )
    earlier = BayesianDiagnostic(
        code="a-earlier",
        category=BayesianDiagnosticCategory.RESULT,
        status=BayesianDiagnosticStatus.PASSED,
        message="Earlier diagnostic.",
    )
    ordered = BayesianAnalysisResult.model_validate(
        result.model_copy(update={"diagnostics": (later, earlier)}).model_dump(mode="python")
    )

    assert tuple(item.code for item in ordered.diagnostics) == ("a-earlier", "z-later")
    assert tuple(item.key for item in ordered.diagnostics[1].context) == (
        "likelihood",
        "sample_count",
    )

    with pytest.raises(ValidationError):
        BayesianDiagnostic(
            code="bad-context",
            category=BayesianDiagnosticCategory.RESULT,
            status=BayesianDiagnosticStatus.FAILED,
            message="Bad context.",
            context={"value": math.inf},
        )
