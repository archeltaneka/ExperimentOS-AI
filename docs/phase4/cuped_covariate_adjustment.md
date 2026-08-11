# CUPED covariate adjustment

ExperimentOS provides deterministic, offline CUPED adjustment for eligible two-arm randomized
experiments. CUPED uses one declared pre-treatment covariate to reduce outcome noise while
estimating the same treatment-effect estimand as the unadjusted randomized analysis.

CUPED is a precision technique. It does not fix confounding, make an observational study causal,
or turn statistical significance into business value.

## Supported v1 scope

The public `CupedAnalysisService` supports:

- a randomized `cuped` design;
- exactly one treatment arm and one control arm;
- one continuous primary outcome;
- exactly one covariate declared with role `cuped`;
- explicit `pre_treatment` timing and a measurement period ending before treatment starts;
- treatment relationship `none_known`;
- fixed-horizon, two-sided frequentist inference; and
- the same supported difference-in-means or intention-to-treat estimand as baseline.

The service accepts a `CupedAnalysisExecutionRequest`, immutable `AnalysisTable`, explicit
`AnalysisDataBinding`, and provenance. It returns only frozen ExperimentOS contracts.

## Coefficient convention

Theta is estimated once across pooled treatment and control complete cases. It is not fitted by arm
and does not include treatment assignment in its fit.

For retained covariates `X`, outcomes `Y`, and retained count `n`:

```text
mean_X = sum(X_i) / n
mean_Y = sum(Y_i) / n

Cov(Y, X) = sum((Y_i - mean_Y) * (X_i - mean_X)) / (n - 1)
Var(X) = sum((X_i - mean_X)^2) / (n - 1)

theta = Cov(Y, X) / Var(X)
```

Covariance and variance both use the sample `n - 1` convention. Their common denominator cancels
in theta but both reported values retain that convention. The reference centering mean is the
pooled complete-case covariate mean.

The adjusted outcome is:

```text
Y_adjusted_i = Y_i - theta * (X_i - mean_X)
```

The coefficient contract reports theta, covariance, covariate variance, covariate mean, outcome
variance, pooled outcome-covariate correlation when defined, retained coefficient sample size,
degrees-of-freedom convention, centering convention, and pooled-fit provenance.

Correlation is unavailable rather than zero when outcome variance is zero. An exact constant
covariate abstains. `ValidationPolicy.minimum_covariate_variance` defaults to `0.0`; callers may set
a positive, domain-scaled threshold for deterministic near-zero blocking.

## Temporal eligibility

The covariate must be explicitly declared as pre-treatment. ExperimentOS does not infer timing from
column names, suffixes, correlation, or observed values.

CUPED is blocked when the covariate is:

- post-treatment, at-treatment, time-varying, or unknown timing;
- declared pre-treatment but measured after treatment starts;
- treatment-derived or a treatment proxy;
- the primary outcome metric;
- bound to treatment, outcome, identifier, unit, clustering, or timestamp columns; or
- missing its declared physical binding or column.

Temporal leakage is a blocking assumption failure. Treatment-control covariate imbalance is a
separate advisory observation and does not by itself establish failed randomization.

## Complete-case policy

CUPED does not impute missing covariates. Rows with `None` in the CUPED covariate are removed from
both adjusted inference and the comparable unadjusted reference. Present boolean, non-numeric, NaN,
or infinite values are invalid and block CUPED rather than being treated as missing.

The result reports original, retained, and removed counts overall and by arm; retained proportions;
and covariate missing counts and rates by arm. The input table and original outcome column are never
mutated.

`ValidationPolicy.maximum_covariate_missing_rate` is the centralized excessive-missingness policy.
Its default is `None`. When configured and exceeded, CUPED abstains. Without a configured threshold,
the retained rows must still satisfy existing total, per-arm, and Welch estimator sample minima.

## Adjusted inference and estimand

ExperimentOS passes adjusted treatment and control outcomes to the same existing two-sided Welch
analyzer used for continuous unadjusted randomized analysis. It therefore preserves:

- treatment-minus-control direction;
- outcome, metric unit, treatment, and control definitions;
- the declared estimand, including intention-to-treat semantics;
- alpha and confidence level;
- sample-variance and Welch-Satterthwaite degrees-of-freedom conventions; and
- two-sided t p-value and confidence-interval behavior.

The adjusted row values remain inside the calculation boundary. They are not returned, persisted,
or emitted through telemetry.

## Unadjusted references

Every CUPED result contains a separately labeled full-sample unadjusted randomized result. It is
computed independently of CUPED validity and may remain valid when CUPED abstains.

A valid CUPED calculation also contains a comparable unadjusted result computed on exactly the same
retained complete cases as adjusted inference. Only this retained-sample result is used for variance
reduction. A full-sample estimate is never compared with a complete-case adjusted estimate and
described as adjustment gain.

## Variance reduction

Estimator variance is represented by squared Welch standard error on identical retained rows:

```text
unadjusted_estimator_variance = comparable_unadjusted_SE^2
adjusted_estimator_variance = adjusted_SE^2

variance_reduction =
    1 - adjusted_estimator_variance / unadjusted_estimator_variance
```

The result preserves the fraction and presentation percentage without clamping:

- `positive_reduction`: the adjusted variance is lower;
- `no_reduction`: the variances are exactly equal;
- `negative_reduction`: adjusted precision is worse for this sample; and
- `unavailable`: a finite positive same-sample comparison cannot be formed.

A negative result is a valid statistical outcome, not automatically a software-quality failure.
ExperimentOS does not rank covariates or automatically disable adjustment based on this result.

Top-level CUPED status is `completed` for positive reduction, `no_improvement` for exact zero,
`degraded_precision` for negative reduction, `inconclusive` for valid adjusted inference with an
unavailable comparison, and `abstained`, `unsupported`, or `invalid` for non-numerical outcomes.
Baseline randomized status remains separate.

## Covariate balance

The retained-sample balance summary reports treatment and control counts, means, sample variances,
pooled within-arm standard deviation, and standardized mean difference when defined:

```text
pooled_variance =
    ((n_t - 1) * variance_t + (n_c - 1) * variance_c) / (n_t + n_c - 2)

standardized_mean_difference =
    (mean_t - mean_c) / sqrt(pooled_variance)
```

Balance status is `exactly_balanced`, `observed_difference`, or `unavailable`. Any nonzero finite
mean difference receives an advisory diagnostic. V1 adds no broad imbalance threshold and does not
infer failed randomization from this summary alone.

## Assumptions and diagnostics

Structured assumptions cover randomized assignment, pre-treatment measurement, the covariate being
unaffected by treatment, stable outcome measurement, compatible units, fixed-horizon analysis,
unchanged estimand, complete-case behavior, and no hidden outcome-dependent covariate selection.

Contract-supported declarations may be marked `supported`. Untestable claims, such as no hidden
selection or no treatment effect on the already measured covariate, remain `untestable`. Failures
connect to stable diagnostics and deterministic abstention reasons.

## Examples

The examples assume an eligible request, table, binding, and provenance have been constructed with
the contracts described above.

### 1. Positive variance reduction

```python
result = CupedAnalysisService().analyze(
    execution,
    table,
    binding,
    provenance=(experiment_source,),
)

assert result.status == "completed"
assert result.adjusted_result.estimand == result.analysis_request.estimand
assert result.comparable_unadjusted_result is not None
assert result.variance_reduction.status == "positive_reduction"
assert result.variance_reduction.fraction > 0.0
```

### 2. Valid computation without precision improvement

```python
result = CupedAnalysisService().analyze(
    execution,
    zero_correlation_table,
    binding,
    provenance=(experiment_source,),
)

assert result.status == "no_improvement"
assert result.coefficient.theta == 0.0
assert result.variance_reduction.fraction == 0.0
```

The estimator remains available, but ExperimentOS makes no improvement claim.

### 3. Constant covariate abstention

```python
result = CupedAnalysisService().analyze(
    execution,
    constant_covariate_table,
    binding,
    provenance=(experiment_source,),
)

assert result.status == "abstained"
assert result.abstention_reason.code == "constant_or_near_zero_covariate"
assert result.full_sample_unadjusted_result.status == "completed"
```

The valid randomized baseline remains inspectable; it is not mislabeled as successful CUPED.

### 4. Post-treatment rejection

```python
assert execution.analysis_request.covariates[0].timing == "post_treatment"

result = CupedAnalysisService().analyze(
    execution,
    table,
    binding,
    provenance=(experiment_source,),
)

assert result.status == "abstained"
assert "eligibility.covariate.post_treatment_leakage" in {
    diagnostic.code for diagnostic in result.diagnostics
}
```

### 5. Missing-covariate retention

```python
result = CupedAnalysisService().analyze(
    execution,
    table_with_missing_covariates,
    binding,
    provenance=(experiment_source,),
)

assert result.retention.original_total == 100
assert result.retention.retained_total == 92
assert result.retention.removed_total == 8
assert result.comparable_unadjusted_result.treatment_summary.n == (
    result.retention.treatment.retained_count
)
assert result.adjusted_result.treatment_summary.n == (
    result.retention.treatment.retained_count
)
```

No missing value is imputed, and the full-sample result remains separately labeled.

## Observability and privacy

CUPED uses the shared ExperimentOS observability abstraction. Telemetry contains controlled method,
metric type, status, timing, retained counts and proportion, variance-reduction status, diagnostic
codes, warning count, and duration. Provider failures do not change statistical results.

Telemetry never contains raw outcomes, raw covariates, adjusted outcomes, rows, theta labels,
arbitrary experiment/request identifiers, credentials, or private payloads.

## Limitations

This implementation does not support multiple covariates, generic regression adjustment,
observational confounding adjustment, propensity scores, automatic covariate selection, sequential
CUPED, Bayesian CUPED, clustering, CUPAC, nonlinear adjustment, causal ML, business-impact
estimation, API or workflow integration, persistence, live LLMs, or network services.

Higher statistical significance after CUPED is not automatically evidence of product or business
value. Covariates must be declared deliberately before analysis; ExperimentOS does not select them
automatically.
