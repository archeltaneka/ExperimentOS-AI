# Difference-in-Differences

ExperimentOS supports a deliberately bounded, observational two-group/two-period
Difference-in-Differences (DiD) estimator. DiD is not just a before/after comparison: the
treated group's change is compared with the contemporaneous change in an untreated comparison
group.

## Estimand

The supported estimand is the ATT-oriented DiD contrast for the declared treated population:

```text
ATT_DiD =
  (E[Y_post | treated] - E[Y_pre | treated])
  - (E[Y_post | control] - E[Y_pre | control])
```

The result is never labeled as a generic ATE. The treated and comparison definitions, canonical
pre/post periods, target population, outcome, analysis unit, and treatment timing are echoed in
the typed result.

The equivalent canonical regression is:

```text
Y_it = beta_0 + beta_1 Treated_i + beta_2 Post_t
       + beta_3 (Treated_i * Post_t) + error_it
```

`control` and `pre` are the reference categories, and `beta_3` equals `ATT_DiD`. ExperimentOS
computes the four-cell contrast directly and verifies it against the interaction coefficient.

## Supported Design

V1 requires exactly one treated group and one comparison group, one canonical pre period, one
canonical post period, explicit unit/time/group/exposure/start/outcome columns, and a complete two-period panel.
Treatment must start after the pre observation window begins and no later than
the post period begins under the declared half-open period semantics. Treated units must adopt at
one common time and remain treated; comparison units must remain untreated.

The panel policy is strict rather than implicit. A unit missing either canonical period, duplicate
unit-period rows, group switching, entry, exit, or differential attrition produces structured
diagnostics and abstention. Missing outcomes are reported and never imputed or converted to zero.

## Identification Assumptions

The issue #97 identification contract must return `identified` before estimation. The result
preserves all declared assumptions, including parallel trends, no anticipation, stable treatment
definition, temporal ordering, and stable unit population. The key point is that parallel trends is an assumption; a
diagnostic can provide evidence about it but cannot establish it.

Extra pre-treatment periods are diagnostic-only. With sufficient complete coverage, ExperimentOS
estimates the treated-by-time pre-trend interaction with the same unit-clustered convention. A
significant divergence surfaces an evidence concern. A non-significant pre-trend result does not prove parallel trends
and never changes the canonical two-period estimand.

## Uncertainty

Frequentist uncertainty uses a cluster-robust CR1 sandwich covariance clustered by the declared
analysis unit. The finite-sample correction is `G/(G-1) * (N-1)/(N-K)`, the test uses a two-sided
Student t reference distribution with `G-1` degrees of freedom, and the confidence interval uses
the same variance and degrees-of-freedom convention. The default confidence level is 95%.

The centralized policy requires at least eight total clusters and four clusters in each group.
Below those limits the service abstains; below 30 clusters it completes with a deterministic
few-cluster warning. It never silently falls back to naive iid uncertainty.

## Limitations

- In v1, staggered adoption is unsupported.
- Treatment reversals, switching, and late comparison-group adoption are unsupported.
- No event-study implementation exists.
- No workflow integration exists.
- No timing discovery, synthetic control, propensity model, DML, heterogeneous-treatment-effect
  estimator, business-impact calculation, or missing-data imputation is included.
- Pre-trend diagnostics are evidence rather than proof, and causal interpretation still depends on
  the declared observational assumptions and evidence limitations.
