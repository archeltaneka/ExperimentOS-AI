# Bayesian A/B testing with explicit priors

ExperimentOS supports deterministic, offline Bayesian analysis for eligible two-arm randomized
experiments. Priors are scientific assumptions supplied by the caller. The analyzer never selects,
fits, weakens, or repairs a prior automatically.

## Supported v1 models

Binary outcomes use a Beta prior and Bernoulli observations summarized by Binomial arm counts:

```text
theta ~ Beta(alpha, beta), alpha > 0, beta > 0
s successes, f failures
theta | data ~ Beta(alpha + s, beta + f)
```

The posterior mean and variance are:

```text
E[theta | data] = alpha_n / (alpha_n + beta_n)
Var(theta | data) = alpha_n beta_n /
                    ((alpha_n + beta_n)^2 (alpha_n + beta_n + 1))
```

Success is the validated binary value `1`. Zero successes, all successes, and sparse events remain
mathematically valid with a proper prior and at least one observation in each arm.

Continuous outcomes use exactly one conjugate model:

```text
sigma^2 ~ InverseGamma(alpha_0, scale=beta_0)
mu | sigma^2 ~ Normal(mu_0, sigma^2 / kappa_0)
x_i | mu, sigma^2 ~ Normal(mu, sigma^2)
```

`beta_0` is an inverse-gamma **scale**, not a rate. All four hyperparameters are explicit;
`mu_0` is finite and `kappa_0`, `alpha_0`, and `beta_0` are finite and strictly positive. For `n`
observations, mean `x_bar`, and `S = sum((x_i-x_bar)^2)`:

```text
kappa_n = kappa_0 + n
mu_n    = (kappa_0 mu_0 + n x_bar) / kappa_n
alpha_n = alpha_0 + n / 2
beta_n  = beta_0 + S / 2
          + kappa_0 n (x_bar - mu_0)^2 / (2 kappa_n)
```

The marginal posterior for the arm mean is Student-t with `2 alpha_n` degrees of freedom,
location `mu_n`, and scale `sqrt(beta_n / (alpha_n kappa_n))`. Each continuous arm needs at least
two valid observations. Zero observed variance is allowed because the proper prior keeps posterior
variance positive.

## Explicit declarations

Use `BayesianAnalysisExecutionRequest` with an `AnalysisRequest` whose method is `bayesian_ab` and
whose uncertainty is `RequestedCredibleLevel`. Treatment and control priors and the likelihood are
required fields. Each prior records its family, family version, numeric hyperparameters, optional
label, and provenance.

The production API consumes numeric priors. A label such as “weak” or “informative” has no
statistical effect. `alpha + beta` is reported as the conventional Beta prior effective sample size,
and `kappa_0` is reported as Normal prior mean information; neither is claimed to be a universal
measure of prior strength.

```python
from packages.experiments.analysis.randomized.bayesian import (
    BayesianAnalysisExecutionRequest,
    BayesianAnalysisService,
    BernoulliBinomialLikelihood,
    BetaPrior,
)

prior = BetaPrior(
    alpha=1.0,
    beta=1.0,
    label="Uniform fixture prior",
    provenance=(prior_source,),
)
execution = BayesianAnalysisExecutionRequest(
    request_id="binary-example",
    analysis_request=bayesian_binary_request,
    treatment_prior=prior,
    control_prior=prior,
    likelihood=BernoulliBinomialLikelihood(),
)
result = BayesianAnalysisService().analyze(
    execution,
    table,
    binding,
    provenance=(experiment_source,),
)
```

An informative binary prior is expressed by its numbers, for example `BetaPrior(alpha=40.0,
beta=10.0, ...)`. An informative continuous prior likewise supplies `mu_0`, `kappa_0`, `alpha_0`,
and `beta_0`; there is no `weak_prior=True` shortcut.

## Treatment-effect posterior

Both models target the raw outcome-scale difference:

```text
delta = treatment parameter - control parameter
```

For binary outcomes the parameters are arm probabilities. For continuous outcomes they are arm
means. Arm posterior parameters and moments are analytic. The difference distribution is evaluated
by deterministic one-dimensional adaptive quadrature: bounded Beta convolution for binary outcomes
and convolution of the exact marginal Student-t means for continuous outcomes. Brent root finding
inverts that CDF for the median and credible bounds.

No posterior sampling is used. Results therefore have no seed, draw count, Monte Carlo standard
error, effective sample size for draws, or MCMC convergence statistic. The computation method,
quadrature tolerances, reproducibility flag, and maximum reported absolute integration-error
estimate are preserved in the result.

## Credible intervals

Version 1 uses equal-tailed intervals at the explicitly requested credible level. Per-arm binary
intervals use Beta quantiles; per-arm continuous-mean intervals use Student-t quantiles; effect
intervals invert the deterministic difference CDF.

A credible interval is not a confidence interval. ExperimentOS serializes it as
`credible_interval`, with `kind="credible_interval"`, `credible_level`, and
`interval_method="equal_tailed"`. Bayesian results contain no p-value or frequentist significance
flag.

## Probability of superiority and metric direction

`probability_of_superiority` always means:

```text
P(delta > 0 | observed data, declared priors, declared likelihood)
```

That raw meaning never reverses. When the metric direction is `increase`,
`probability_treatment_is_better` equals `P(delta > 0)`. When direction is `decrease`, it equals
`P(delta < 0)`. It is omitted for `no_preference`. Event text and metric direction are serialized.

A posterior probability is not a p-value. `P(delta > 0)=0.95` is not interpreted as `p=0.05`, and
neither quantity is automatically converted into a rollout decision or business value.

## Region of practical equivalence

ROPE output exists only when the execution request supplies a finite, ordered, unit-compatible
`PracticalEquivalenceRegion`. Symmetric and asymmetric regions are supported:

```python
rope = PracticalEquivalenceRegion(
    lower=-0.01,
    upper=0.02,
    unit=bayesian_binary_request.outcome.metric.unit,
)
execution = execution.model_copy(update={"rope": rope})
```

The result reports posterior probability below, inside, and above the region. The three values form
a probability partition and preserve the raw treatment-minus-control effect scale. With no ROPE,
`rope_probability` is `null`; ExperimentOS does not invent epsilon from the credible level or any
frequentist alpha. No “equivalent,” “ship,” or “do not ship” classification is applied.

## Worked continuous example

```python
from packages.experiments.analysis.randomized.bayesian import (
    BayesianAnalysisExecutionRequest,
    BayesianAnalysisService,
    NormalInverseGammaPrior,
    NormalUnknownMeanVarianceLikelihood,
)

control_prior = NormalInverseGammaPrior(
    mu_0=0.0,
    kappa_0=1.0,
    alpha_0=2.0,
    beta_0=2.0,
    provenance=(prior_source,),
)
treatment_prior = control_prior.model_copy(update={"mu_0": 1.0})
execution = BayesianAnalysisExecutionRequest(
    request_id="continuous-example",
    analysis_request=bayesian_continuous_request,
    treatment_prior=treatment_prior,
    control_prior=control_prior,
    likelihood=NormalUnknownMeanVarianceLikelihood(),
)
result = BayesianAnalysisService().analyze(
    execution,
    table,
    binding,
    provenance=(experiment_source,),
)
```

For control observations `(1, 2, 3)`, the example prior updates exactly to `mu_n=1.5`,
`kappa_n=4`, `alpha_n=3.5`, and `beta_n=4.5`. Those values lock the inverse-gamma shape/scale
convention.

## Sparse data, diagnostics, and abstention

Sparse binary data do not reuse frequentist sparse-cell abstention. With Beta `(1,1)`, one observed
failure in each arm produces proper Beta `(1,2)` posteriors and a wide but valid effect posterior.
High uncertainty is a result, not an abstention reason.

Diagnostics record declaration validity, analytic arm updates, deterministic quadrature,
integration error, existing randomized eligibility checks, and model-specific prior/data information
context. A warning is emitted when `alpha+beta > n` for a Beta arm or `kappa_0 > n` for a continuous
arm. These are explicitly labeled heuristics; they do not penalize certainty or alter posterior
values.

The analyzer abstains or returns a non-numerical status for:

- zero observations in either arm;
- fewer than two observations in a continuous arm;
- missing, invalid, non-finite, or outcome-incompatible observations;
- an unsupported outcome or likelihood/outcome combination;
- invalid/non-finite prior hyperparameters;
- malformed, reversed, zero-width, non-finite, or unit-incompatible ROPE declarations; and
- a posterior computation that cannot produce finite valid quantities.

`analyze_payload` converts invalid prior and likelihood declarations into structured diagnostics and
typed invalid/unsupported results without echoing rejected values. Nothing is repaired automatically.

## Provenance, serialization, and observability

Valid results retain the analysis request, metric, estimand, arm identities, complete treatment and
control priors, prior provenance, explicit likelihood, exact posterior parameters, interval and
effect methods, configuration provenance, assumptions, diagnostics, warnings, ROPE declaration, and
caller-supplied experiment provenance. Frozen SciPy distributions and third-party result objects
never cross the ExperimentOS boundary. Canonical JSON is key-sorted and rejects NaN and infinity.

Estimator telemetry is best-effort and low-cardinality. It records the Bayesian inference family,
likelihood/outcome families, deterministic computation mode, status, prior-validity state, ROPE and
superiority availability, aggregate arm counts, diagnostic codes, warning count, and duration. It
does not emit raw outcomes, raw priors, posterior samples, row payloads, column names, request or
experiment identifiers, or credentials. Observability failure cannot change the analysis result.

## Limitations and exclusions

Version 1 does not implement hierarchical Bayesian models, non-conjugate priors, MCMC, PyMC, Stan,
NumPyro, automatic prior selection, empirical-Bayes optimization, Bayesian sequential stopping,
adaptive traffic allocation, business-impact conversion, observational causal inference, workflow
or LangGraph integration, persistence, live LLM functionality, hosted services, or external judges.
It supports no alternative continuous Bayesian model and makes no automatic business decision.
