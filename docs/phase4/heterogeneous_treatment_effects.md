# Heterogeneous Treatment Effects

ExperimentOS supports one bounded heterogeneous-effect method: pre-specified discrete
subgroup ATE estimation using the existing deterministic DML cross-fitting machinery and a
direct treatment-by-subgroup comparison. It describes population groups only. It does not
produce individual uplift scores, treatment assignments, rollout recommendations, or
business-impact calculations.

## Estimand and method

For each declared subgroup `g`, the estimand is

```text
E[Y(1) - Y(0) | G = g]
```

under the base population, treatment contrast, adjustment set, and identification
assumptions carried by the approved causal-identification result. This is a discrete subgroup
ATE. A request may be CATE-style in the sense that it asks for effects conditional on a
declared group, but the result is not a smooth or individualized CATE surface.

One global deterministic cross-fit estimates the outcome and treatment nuisances. The
feature matrix contains the approved numeric pre-treatment adjustment covariates plus
deterministic subgroup indicators. Subgroup effects and their direct reference-group
contrasts are computed from the out-of-fold orthogonal residuals. No same-fold nuisance
prediction, hidden subgroup-specific refitting, automatic covariate selection, or threshold
search occurs.

## Eligible effect modifiers

An `EffectModifierDefinition` declares the variable ID and column, role
`EFFECT_MODIFIER`, measurement timing, modifier type, derivation, subgroup rules,
pre-specification and registration states, and their provenance. Confirmatory estimation
requires a registered, pre-specified modifier measured `PRE_TREATMENT`.

V1 supports:

- binary categorical modifiers with exactly two explicit values;
- finite categorical modifiers with explicit levels;
- continuous modifiers with ordered, contiguous, exhaustive, explicitly declared half-open
  bins.

Post-treatment, outcome-derived, treatment-derived, data-mined, unknown-timing,
unregistered, and exploratory definitions cannot produce confirmatory estimates. They are
rejected or abstained before nuisance fitting. Quantiles or cut points are never learned from
the observed treatment effects. Unrestricted subgroup discovery and sample-split discovery
are not implemented.

## Assignment, missing data, and samples

Assignment is deterministic and invariant to row order. The result records an aggregate
SHA-256 assignment fingerprint plus each subgroup's ID, label, rule, raw count, retained
count, treated count, control count, and dropped count. Complete-case filtering follows the
existing DML policy and attributes exclusions to a subgroup when the modifier was assignable.
Unit IDs and row-level membership never enter the public result or telemetry.

The default centralized minima are 20 retained observations, 5 treated observations, and 5
controls per subgroup. A subgroup below any minimum abstains without a point estimate,
standard error, interval, or p-value. Weighted ESS is not applicable to this DML baseline and
is represented explicitly as unavailable rather than fabricated.

## Overlap and uncertainty

Cross-fitted propensity diagnostics are evaluated globally and separately within every
subgroup. A globally acceptable result does not override a severe subgroup overlap failure;
the affected subgroup abstains. Weak overlap remains visible for review. Global severe
overlap prevents all subgroup inference.

Every completed subgroup effect contains a point estimate, HC1-style orthogonal-score
influence standard error, two-sided normal p-value, confidence interval, confidence level,
and uncertainty method. Missing or degenerate uncertainty is an abstention condition.

## Direct heterogeneity evidence

Heterogeneity is tested directly. Binary modifiers return the treatment-effect difference
against the deterministic reference subgroup. Multi-level modifiers return reference-group
interaction contrasts and one joint Wald chi-square test of the null that all supported
subgroup effects are equal. V1 intentionally does not enumerate every pairwise comparison.

**A significant effect in subgroup A and a non-significant effect in subgroup B does not
establish treatment-effect heterogeneity.** Only the direct interaction/difference or joint
test addresses that claim.

Holm correction is applied separately and explicitly to the subgroup-effect family and the
reference-interaction family. The omnibus global p-value is a single unadjusted global test.
The result records effect, interaction, pairwise, and global test counts and whether each
family was corrected.

## Identification, provenance, and policy

The original consistency, exchangeability, positivity, temporal-ordering, no-interference,
estimand, population, and treatment-contrast declarations remain attached to the result.
Convergence is not proof of causal identification, and effect-modifier timing is an
additional required assumption.

Provenance records the full modifier definition, assignment rule and fingerprint, estimator
and analysis version, cross-fit plan and fold fits, nuisance adapter metadata, overlap policy,
uncertainty method, multiplicity method, sample thresholds, and supplied sources. The HTE
quality evaluator blocks conclusive post-treatment or exploratory modifiers, sparse groups,
ignored severe overlap, missing uncertainty, and claims lacking direct heterogeneity
evidence. Wide intervals, weak subgroup overlap, substantial attrition, and larger
multiplicity burdens are advisory.

Telemetry contains low-cardinality method, estimand, modifier type, subgroup/test counts,
analysis semantics, overlap/abstention counts, global evidence status, diagnostics, overall
status, and duration. It excludes unit IDs, membership, raw rows, outcomes, treatment values,
propensities, nuisance predictions, and residuals.

## Explicit exclusions

There is no unrestricted subgroup discovery, recursive segmentation, causal tree, causal
forest, automatic cut-point search, smooth individualized CATE model, uplift targeting,
policy learning, personalized treatment assignment, rollout or budget recommendation,
EconML adapter, DoWhy adapter, business-impact aggregation, workflow integration, live LLM,
network access, database access, or hosted telemetry in this capability.
