# Unadjusted randomized experiment analysis

ExperimentOS v1 supports unadjusted, fixed-horizon inference for eligible two-arm randomized experiments with independent analysis units and no clustering.

## Supported analysis

- One declared treatment arm and one declared control arm.
- Continuous outcomes: Welch's independent two-sample t procedure using sample variance (`n - 1`), Welch-Satterthwaite degrees of freedom, a two-sided t p-value, and a t confidence interval.
- Binary outcomes: independent two-proportion z procedure. The null-hypothesis test uses pooled standard error; the absolute-difference confidence interval uses unpooled standard error.
- Effects are always treatment minus control. Relative lift is reported only when the control mean or rate is non-zero.

The hypothesis is explicit in every result: `H0: effect = 0` and `H1: effect != 0`.

## Two-sided fixed-horizon only

V1 accepts only a declared `two_sided` alternative. A `greater_than` or `less_than` request returns a structured unsupported result with diagnostic code `unsupported_alternative_hypothesis`; it does not calculate a one-sided p-value or confidence bound.

This prevents post-hoc directional testing and keeps directional inference for a future, explicitly pre-registered extension.

## Safety and interpretation

Inputs are not filtered, imputed, aggregated, coerced, or assigned a substitute method. Unsupported designs, insufficient arm sizes, invalid binary encodings, degenerate uncertainty, sparse binary cells, and non-finite computations abstain with deterministic diagnostics.

A zero control baseline produces a finite absolute effect but an explicitly unavailable relative effect. A non-significant result is not evidence of no effect. Statistical conclusion, practical significance, and design-based causal evidence remain separate. Unverified assumptions—random assignment, consistency, no interference, compatible units, independence, fixed horizon, valid measurement, and no peeking—are preserved as assumptions rather than marked empirically satisfied.

## Exclusions

This capability does not implement CUPED, sequential testing, Bayesian inference, observational causal inference, heterogeneous effects, business-impact estimation, database persistence, API or workflow integration, or LLM-generated recommendations.
