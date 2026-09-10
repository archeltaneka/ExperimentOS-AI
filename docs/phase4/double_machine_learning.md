# Double Machine Learning

ExperimentOS supports one deliberately bounded Double Machine Learning (DML) design: a
binary treatment, continuous outcome, explicitly declared numeric pre-treatment covariates,
and a full-population ATE-style mean-difference target under a partially linear model.

## Supported model and identification

The structural model is

```text
Y = theta D + g0(X) + epsilon
D = m0(X) + v
```

where `D` is binary, `Y` is continuous, and `X` contains only the validated pre-treatment
adjustment variables. The implemented partialling-out score estimates the constant effect
`theta`. Its outcome nuisance is `ell0(X) = E[Y | X]`; this is not the same object as the
structural function `g0(X)`.

An identified issue #97 contract is mandatory. The supported interpretation additionally
requires consistency, no relevant interference, conditional exchangeability/no unmeasured
confounding, positivity, correct temporal ordering, the partially linear structural form,
and sufficient residual treatment variation. Exchangeability is asserted rather than
empirically proven. DML does not remove unmeasured confounding, and flexible nuisance models
do not make causal identification automatic.

## Cross-fitting and orthogonal score

For every fold, both nuisance models are fitted on the complement of the scoring fold.
Training and scoring identities must be disjoint, and every retained observation receives
exactly one out-of-fold outcome prediction and one out-of-fold treatment probability.
Same-fold fitting and scoring is forbidden.

With `U_i = Y_i - ell_hat_i` and `V_i = D_i - m_hat_i`, ExperimentOS uses only this score:

```text
psi_i(theta) = V_i (U_i - theta V_i)
theta_hat = sum(V_i U_i) / sum(V_i^2)
```

It does not silently mix score formulations. If `sum(V_i^2)` is at or below the configured
tolerance, estimation abstains; no epsilon is added to fabricate an estimate.

## Deterministic folds

`fold_count` and `random_seed` are required and `fold_count >= 2`. Complete-case filtering
happens before fold construction. Stable observation IDs are canonically type-tagged, hashed
with SHA-256 and the explicit seed within treatment strata, ranked, and assigned round-robin.
This makes unit-to-fold membership invariant to simple input row reordering. Each score and
training fold must contain both treatment classes and satisfy centralized size policies.

The fold fingerprint hashes non-sensitive ID digests, fold count, seed, split method/version,
and stratification policy. Results retain fold sizes and treated/control
counts. Telemetry never contains observation IDs or fold membership.

## Nuisance adapters and diagnostics

Public adapters implement ExperimentOS-owned `OutcomeNuisanceModel` and
`TreatmentNuisanceModel` protocols. They must provide deterministic metadata, configuration
fingerprints, seed, preprocessing and feature-order provenance, minimum sample requirements,
owned fit status, and the relevant prediction method. A fresh adapter is created for every
fold. Exceptions, failed fits, invalid lengths, non-finite predictions, and probabilities
outside `[0, 1]` become structured abstentions.

Private baseline adapters use fold-local standardization with deterministic scikit-learn
Ridge regression for the outcome and regularized logistic regression for treatment. Fitted
scikit-learn objects never enter public contracts. User-supplied adapters are Python objects
provided through the owned protocols; ExperimentOS does not dynamically execute code from
serialized user input.

Outcome RMSE, MAE, and R-squared and treatment log loss, Brier score, AUC, and score
distributions are predictive diagnostics only. Good predictive performance does not prove
exchangeability, a correct adjustment set, positivity, or causal validity. High treatment
predictability can instead indicate poor overlap.

## Overlap, residuals, and uncertainty

Overlap is evaluated from cross-fitted treatment probabilities using common support,
outside-support proportions, extreme-score fractions, and configured weak/severe thresholds.
Severe overlap failures abstain before estimation. A shared non-extreme constant propensity,
such as `0.5` in a randomized-style sample, is treated as overlap rather than a width failure.

Both residuals report count, mean, sample standard deviation and variance, min/max, squared
norm, and non-finite count. Degenerate treatment residuals are fatal. Effectively constant
outcome residuals produce a structured abstention because meaningful uncertainty is not
available under the supported inference contract.

Observation influence values are

```text
phi_i = V_i (U_i - theta_hat V_i) / mean(V_i^2)
```

and remain internal. ExperimentOS reports only their aggregate variance and maximum absolute
magnitude. The estimate variance is `sum(phi_i^2) / (N (N - 1))`, an HC1-style finite-sample
scaling. Standard errors, two-sided `theta = 0` normal tests, and normal confidence intervals
use this same orthogonal-score representation. Degenerate or non-finite uncertainty abstains;
non-significance must not be interpreted as proof of a zero effect.

## Sample retention, provenance, and privacy

No imputation or automated confounder selection occurs. Missing treatment, outcome, or
covariate values are removed by the explicit complete-case policy before folding and are
reported. Invalid non-missing values are rejected. Treatment, outcome, post-treatment,
unknown-timing, and identifier-only variables cannot enter the feature set.
Treatment and outcome bindings carry declared variable IDs as well as table columns, and
those IDs must exactly match the variables approved by the identification contract.

Results record the estimand, target population, contrast, assumptions, evidence limitations,
sample counts, fold configuration/fingerprint/summaries, adapter configuration fingerprints,
fold fit metadata, diagnostics, uncertainty, status, and abstention reason. Telemetry is
limited to aggregate method, estimand, fold count, completion, overlap, nuisance families,
status, diagnostic codes, duration, and sample count. It excludes IDs, raw outcomes,
treatments, covariates, predictions, propensities, residual arrays, and influence values.

## Explicit limitations and exclusions

DML is not causal identification by itself. Positivity remains necessary, nuisance
misspecification remains possible, and the constant partially linear effect is restrictive.
V1 has no IV-DML or PLIV, continuous or multiple treatment, ATT-specific DML, automatic
nuisance selection, AutoML, hyperparameter optimization, causal forests, individualized
effects, EconML, DoWhy, business-impact calculation, workflow integration, live LLM
functionality, network execution, or database dependency. The bounded discrete subgroup
extension is documented separately in [Heterogeneous Treatment Effects](heterogeneous_treatment_effects.md).
