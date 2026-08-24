# Propensity Score Diagnostics

## Purpose

ExperimentOS uses propensity scores as an observational-study design diagnostic. For each eligible
unit, the score is:

```text
e(X) = P(T = 1 | X)
```

`T = 1` always means the request's explicitly declared treated value. The declared control value
maps to `T = 0`; values are compared by both type and value, never Python truthiness.

Propensity scores do not estimate a treatment effect. They show whether observed treatment groups
have enough measured-covariate overlap for a later weighting estimator to be considered. Good
measured-covariate balance does not prove that unmeasured confounding is absent.

## Supported Requests

V1 accepts only issue-97 observational requests that are already identified and declare:

- binary treatment with distinct treated and control values;
- an ATE/full-population or ATT/treated-population estimand;
- a generic observational or propensity-weighting design;
- a non-empty, validated adjustment set;
- explicit table bindings and numeric/categorical feature kinds for every adjustment variable;
- adjustment variables with an adjustment role and pre-treatment or time-invariant timing.

Treatment, outcome, identifier-only, post-treatment, unknown-role, and unknown-timing variables are
prohibited. ExperimentOS never discovers confounders from correlations, model importance, or the
outcome data.

## Baseline Model

The single V1 estimator is regularized binary logistic regression with a logit link. Configuration
is explicit and serialized:

| Choice | V1 default |
| --- | --- |
| Solver | `lbfgs` |
| Penalty | L2, represented in scikit-learn 1.9 as `l1_ratio=0.0` |
| Inverse regularization strength | `C=1.0` |
| Convergence tolerance | `1e-8` |
| Maximum iterations | `1000` |
| Intercept | fitted |
| Class weights | none |
| Warm start | disabled |
| Random seed provenance | `0` |

The scikit-learn estimator, arrays, coefficients, warnings, and exceptions remain inside a private
adapter. The owned result records fitted class orientation, convergence state, iteration count,
solver, package version, training-classification signal, coefficient-instability magnitude, and
extreme-score fraction. A convergence warning or iteration-limit exhaustion invalidates the score
fit; ExperimentOS does not silently increase the limit.

Practical separation combines near-perfect treatment classification with extreme probabilities or
large standardized coefficients. Severe separation blocks downstream readiness even if the
optimizer returned coefficients.

## Feature Encoding And Missingness

Numeric covariates are standardized using the complete-case model population's mean and population
standard deviation. A constant feature encodes as zero with scale `1` and records its zero-variance
state; the result also carries an advisory `encoding.zero_variance_numeric` diagnostic.

Categorical values use a type-aware canonical order: boolean, integer, float, then string, with
canonical scalar ordering inside each type. The first category is the explicit one-hot reference.
Model feature names and all category/reference metadata are serialized. Unknown categories are an
error rather than an implicit all-zero encoding. Balance diagnostics include every category
indicator, including the model's reference category.

Missing covariates use complete-case retention. ExperimentOS reports raw, excluded, model, treated,
and control counts and retention proportion. It does not impute or hide removed rows. Non-missing
invalid or non-finite values make the input invalid rather than missing.

## Score Distributions And Common Support

Unit-level scores remain in the owned result for later internal estimators and preserve source-row
alignment. They never enter global telemetry. Aggregate overall, treated, and control summaries
include count, mean, sample standard deviation, minimum, maximum, median, total, and configured
linear-interpolation quantiles.

V1 common support is the intersection of observed arm score ranges:

```text
support_lower = max(min(score_treated), min(score_control))
support_upper = min(max(score_treated), max(score_control))
```

The result reports arm-specific inside/outside counts and proportions. An empty intersection is a
severe positivity violation. This range diagnostic is not a proof of positivity.

Overlap is classified as `acceptable`, `weak`, `severe`, or `unavailable` using centralized
configuration for support width, estimand-relevant outside-support fraction, extreme scores,
separation, extreme weights, and effective sample size. ATE evaluates both arms as the target. ATT
uses treated-unit support loss as the primary target-population fraction while still requiring a
usable control comparison population. By default, extreme-score fractions of `0.05` and `0.20`
produce weak and severe status, respectively; extreme-weight fractions of `0.01` and `0.20` use
the same escalation. ATT additionally requires at least one control unit and `0.10` of control
units inside common support. All thresholds are serialized configuration, and severe status blocks
downstream readiness.

## ATE And ATT Weights

Raw diagnostic weights are unnormalized and never silently clipped, capped, or trimmed:

```text
ATE treated: 1 / e(X)
ATE control: 1 / (1 - e(X))

ATT treated: 1
ATT control: e(X) / (1 - e(X))
```

Zero denominators and non-finite weights block the result. An ATT control weight may be zero when
`e(X)=0`. Weight summaries include count, mean, sample standard deviation, minimum, maximum,
median, configured high quantiles, total weight, extreme-weight count, and extreme proportion,
overall and by arm. Large weights are treated as evidence of weak overlap, not cosmetic output.

## Effective Sample Size

Kish weighted effective sample size is computed overall and by arm:

```text
ESS = (sum(w))^2 / sum(w^2)
```

Each result includes raw count and `ESS / raw count`. Empty or zero-total populations are
unavailable. The default blocking policy requires an ESS of at least `10` and a ratio of at least
`0.25` overall and within both arms. Severe ESS collapse makes the design abstain.

## Standardized Mean Differences

Each numeric feature and categorical indicator receives a raw and weighted SMD. Arm means and
population variances use either unit weights or the raw ATE/ATT weights:

```text
mean_g = sum(w_i * x_i) / sum(w_i)
variance_g = sum(w_i * (x_i - mean_g)^2) / sum(w_i)
SMD = (mean_treated - mean_control) / sqrt((variance_treated + variance_control) / 2)
```

For a binary indicator, this variance equals `p * (1 - p)`. Equal means with zero pooled variance
produce SMD zero. Unequal means with zero pooled variance produce an unavailable diagnostic rather
than infinity. The default advisory balance threshold is absolute SMD `0.10`. Balance warnings do
not by themselves invalidate an otherwise healthy score model.

The aggregate balance result reports maximum raw and weighted absolute SMD, counts above the
threshold, and counts improved or worsened after weighting. These diagnostics cover measured
covariates only.

## Trimming And Capping

Trimming and weight capping are disabled by default.

An explicit trimming request supplies inclusive lower and upper score bounds. ExperimentOS retains
the complete raw score and weight diagnostics, reports total and arm-specific losses, labels the
retained proportion, and recomputes score summaries and common support for the retained population.
It never silently removes units outside common support.

An explicit weight-cap request supplies a positive maximum. ExperimentOS preserves raw weights and
raw ESS, creates separately labelled capped weights, reports the affected count/proportion, and
computes post-cap ESS. Capped values do not replace raw weights or raw weighted balance.

## Status, Provenance, And Observability

The result abstains for rejected identification, unsupported design/estimand, invalid treatment or
covariate contracts, missing model arms, convergence failure, severe separation, invalid scores,
empty/severe overlap, impossible weights, or configured ESS collapse. A fit is not considered
successful merely because logistic regression returned coefficients.

Reproducibility provenance contains model family, link, solver, L2 representation, `C`, tolerance,
iteration limit, intercept policy, numeric scaling parameters, category order/reference policy,
encoded feature order, random seed, treatment/control coding, score orientation, estimand,
trim/cap state, scikit-learn version, request evidence, and configuration contract version.

One provider-failure-isolated observability span records only row count and low-cardinality method,
estimand, model, status, convergence, overlap, ESS, policy flags, diagnostic codes, and duration.
Telemetry excludes rows, unit identifiers, column names, raw covariates, categories, scores,
weights, feature matrices, and coefficients.

## Limitations

- No treatment effect, IPW estimate, matching estimate, or business impact is produced.
- No automated confounder selection, sensitivity analysis, or unmeasured-confounding test is
  performed.
- Range-based common support is necessary diagnostic evidence, not a complete positivity proof.
- Balance after weighting does not establish exchangeability.
- Continuous/multinomial treatment, ML propensity models, AutoML, EconML, DoWhy, DML, HTE, causal
  forests, and neural propensity models are unsupported.
- The subsystem is offline and deterministic and has no workflow or live-LLM integration.
