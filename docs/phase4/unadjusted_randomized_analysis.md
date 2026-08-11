# Unadjusted randomized experiment analysis

ExperimentOS v1 provides deterministic, offline, unadjusted fixed-horizon inference for an
eligible two-arm randomized experiment. The public `RandomizedAnalysisService` accepts an explicit
`RandomizedAnalysisExecutionRequest`, `AnalysisTable`, `AnalysisDataBinding`, and provenance. It
first runs `AnalysisEligibilityService`; labels alone never establish randomization.

## Supported design

- One declared treatment arm and one declared control arm.
- A declared randomized `fixed_horizon_ab` design.
- One declared primary continuous or binary outcome.
- Independent observations at a supported analysis/randomization-unit structure.
- No clustering, repeated unresolved observations, crossover, pairing, or sequential monitoring.
- An explicit `two_sided` alternative and frequentist confidence level.
- A metric-specific difference estimand or intention-to-treat estimand.

Effects always use `treatment - control` and retain the metric unit and outcome-direction metadata
from the validated `AnalysisRequest`. The result embeds that request, including its population,
treatment, control, outcome, estimand, and units.

## Continuous outcomes

Continuous outcomes use Welch's independent two-sample t procedure. Arm variance is the unbiased
sample variance with denominator `n - 1`, matching the descriptive-statistics subsystem. For arm
means `mean_t`, `mean_c`, sample variances `s_t^2`, `s_c^2`, and counts `n_t`, `n_c`:

```text
effect = mean_t - mean_c
SE = sqrt(s_t^2 / n_t + s_c^2 / n_c)

df = (s_t^2 / n_t + s_c^2 / n_c)^2
     / ((s_t^2 / n_t)^2 / (n_t - 1) + (s_c^2 / n_c)^2 / (n_c - 1))

t = effect / SE
CI = effect +/- t_(1 - alpha/2, df) * SE
p = 2 * P(T_df >= abs(t))
```

Unequal arm sizes, unequal variances, and one constant arm are supported when Welch uncertainty is
finite. An arm with fewer than two values, or two constant arms with zero standard error, yields a
typed abstention. The implementation never falls back to an equal-variance procedure.

## Binary outcomes

Binary outcomes must already satisfy the Phase 4 explicit boolean or integer `0`/`1` encoding.
Python truthiness is not used. The two-proportion z test has no continuity correction and never
silently switches to Fisher's exact test.

The hypothesis test uses a pooled null standard error:

```text
p_t = successes_t / n_t
p_c = successes_c / n_c
p_pool = (successes_t + successes_c) / (n_t + n_c)

effect = p_t - p_c
SE_null = sqrt(p_pool * (1 - p_pool) * (1/n_t + 1/n_c))
z = effect / SE_null
p = 2 * P(Z >= abs(z))
```

The Wald confidence interval uses a separate, unpooled standard error:

```text
SE_ci = sqrt(p_t * (1 - p_t) / n_t + p_c * (1 - p_c) / n_c)
CI = effect +/- z_(1 - alpha/2) * SE_ci
```

Both `standard_error` (`SE_null`) and `confidence_interval_standard_error` (`SE_ci`) are serialized.
Expected success and failure counts below the configured threshold (default `5`) produce the stable
`sparse_cell` abstention. Degenerate pooled uncertainty produces `zero_standard_error`.

## Confidence intervals and p-values

Intervals are explicitly frequentist confidence intervals at the validated requested level. SciPy
1.16 distribution survival functions and inverse survival functions provide t and normal tails and
quantiles behind ExperimentOS-owned scalar helpers. This avoids fragile hand-written distribution
approximations and exposes no SciPy result objects. Underflowed positive tails are serialized as the
smallest positive representable float rather than literal zero.

Every test states `H0: treatment - control = 0` and `H1: treatment - control != 0`. P-values are
evidence measures under the null, not proof of an effect, proof of no effect, or evidence of product
value. Values retain full floating-point precision and are not rounded before comparisons.

## Relative effects

When the control baseline is non-zero, relative lift is:

```text
(treatment - control) / control
```

Absolute and relative scales remain separate. A non-positive continuous control mean or zero binary
control event rate leaves the finite absolute effect available but sets the relative effect to
`null`. Zero baselines use reason `zero_control_baseline`; negative continuous baselines use
`non_positive_control_baseline`. Both include matching diagnostics and warnings. No infinity, NaN,
sentinel, or substitute denominator is emitted.

## Assumptions and eligibility

Results preserve structured assessments for random assignment, treatment/control consistency,
stable unit treatment value, no interference, compatible analysis/randomization units, independent
supported units, valid outcome measurement, fixed-horizon analysis, and no uncorrected repeated
peeking. Untestable or unverified assumptions are never marked empirically proven.

Eligibility diagnostics are copied into the analyzer result with an `eligibility.` prefix. Blocking
eligibility outcomes become abstentions without arm summaries, effects, tests, intervals, or
conclusions. Estimator invalidity uses stable codes including `minimum_observations_not_met`,
`one_observation_arm`, `zero_standard_error`, `sparse_cell`, `unsupported_outcome_type`,
`incompatible_estimand`, `unsupported_uncertainty`, and `unsupported_alternative_hypothesis`.

## Examples

### 1. Supported continuous experiment

```python
execution = RandomizedAnalysisExecutionRequest(
    request_id="revenue-test",
    analysis_request=continuous_request,
    alternative=AlternativeHypothesis.TWO_SIDED,
)
result = RandomizedAnalysisService().analyze(
    execution, table, binding, provenance=(experiment_source,)
)
assert result.test_result.test_type == "welch_t"
```

The result contains both arm means and sample variances, treatment-minus-control effect, relative
lift when valid, Welch SE and degrees of freedom, two-sided p-value, and t confidence interval.

### 2. Supported binary experiment

```python
execution = RandomizedAnalysisExecutionRequest(
    request_id="conversion-test",
    analysis_request=binary_request,
    alternative=AlternativeHypothesis.TWO_SIDED,
)
result = RandomizedAnalysisService().analyze(
    execution, table, binding, provenance=(experiment_source,)
)
assert result.test_result.test_type == "two_proportion_z"
```

The result records successes, failures, rates, pooled test SE, unpooled interval SE, two-sided
p-value, and the absolute-difference confidence interval.

### 3. Zero-baseline relative effect

```json
{
  "point_effect": {
    "absolute_effect": {"value": 0.5},
    "relative_effect": null,
    "relative_effect_availability": "unavailable",
    "relative_effect_reason": "zero_control_baseline"
  }
}
```

The valid absolute effect remains available; only the undefined relative scale is suppressed.

### 4. Insufficient-evidence abstention

```json
{
  "status": "abstained",
  "point_effect": null,
  "test_result": null,
  "abstention_reason": {"code": "eligibility.sample.arm_insufficient"}
}
```

No inferential value is fabricated when eligibility or estimator evidence requirements fail.

### 5. Unsupported one-sided request

```python
execution = RandomizedAnalysisExecutionRequest(
    request_id="directional-test",
    analysis_request=request,
    alternative=AlternativeHypothesis.GREATER_THAN,
)
result = RandomizedAnalysisService().analyze(
    execution, table, binding, provenance=(experiment_source,)
)
assert result.abstention_reason.code == "unsupported_alternative_hypothesis"
```

`greater_than` and `less_than` are preserved as declared and rejected. They are never reinterpreted
as two-sided tests, and no one-sided p-value or confidence bound is computed.

## Known limitations and exclusions

This unadjusted capability composes with the separate ExperimentOS CUPED service documented in
`docs/phase4/cuped_covariate_adjustment.md`. It does **not** implement sequential analysis,
Bayesian analysis, observational causal inference, clustered inference, paired/crossover analysis,
heterogeneous effects,
business-impact estimation, database persistence, API exposure, LangGraph/workflow integration,
live LLM calls, or network services. Statistical significance is never converted into a rollout,
revenue, ROI, success, or no-effect recommendation.
