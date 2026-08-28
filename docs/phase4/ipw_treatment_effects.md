# Baseline observational treatment effects with IPW

ExperimentOS estimates observational ATE and ATT only after a completed causal-identification
result and a completed, converged propensity result pass overlap, positivity, effective-sample,
and measured-covariate balance gates. The estimator consumes the exact issue-99 propensity
scores; it never fits or refits a score model.

## Estimands and weights

Let `e(X) = P(T=1 | X)`, with `T=1` defined by the carried treatment contrast.

- ATE raw weights are `1/e(X)` for treated units and `1/(1-e(X))` for controls. Its target is
  the declared full population.
- ATT raw weights are `1` for treated units and `e(X)/(1-e(X))` for controls. Controls are
  reweighted toward the treated population; the target is explicitly the treated population.

Arm means use the Hájek weighted mean `sum(wY)/sum(w)`, and the reported effect is the
weighted treated mean minus the weighted control mean. Weights are never silently normalized,
trimmed, clipped, or capped. Scale cancellation inside the weighted-mean calculation is a
numerical-safety technique and is not a stored weight transformation.

Stabilization is disabled by default. When explicitly enabled, ATE multiplies treated raw
weights by the selected-population treatment prevalence `p` and control raw weights by `1-p`.
For ATT, treated weights remain `1` and control odds weights are multiplied by `(1-p)/p`. The
result retains both raw and stabilized diagnostics and records `p` and the selected convention.

Maximum-weight clipping is also disabled by default. An explicit maximum cap applies to the
configured estimation weights after optional stabilization. Raw weights remain available, and
the result reports arm-specific affected counts, affected proportion, maximum before/after,
and ESS before/after. Clipping changes the estimator and its point estimate; it must be
disclosed whenever used. The IPW layer never independently trims observations. If the supplied
propensity result contains an explicitly retained population, that population is used and raw,
model, selected, and dropped counts are reported. Retention metadata is accepted only when its
configuration, ordered unit IDs, treatment orientation, unchanged scores, and arm/count totals
exactly match the inclusive upstream propensity-score bounds.

## Safety and diagnostics

Kish effective sample size is `(sum(w))^2 / sum(w^2)` overall and by arm. Computation is scaled
to avoid overflow. Fatal identification, convergence, overlap/positivity, source or selected ESS,
weight-denominator, outcome, or severe balance failures stop before the effect engine runs. An
abstained result contains no point estimate, interval, or fabricated inference.

When upstream trimming is explicit, overlap and positivity are recomputed and gated on the
exact retained score population; the treatment-effect result reports that selected-population
overlap rather than the pre-trimming diagnostic. Selected arm presence and ESS are checked
before balance so an empty or information-poor arm cannot be misclassified as balance alone.

The outcome table must represent the same raw population count recorded by the propensity
result. Every selected propensity unit must map to exactly one row with matching treatment
coding. A missing, duplicated, or unreported extra row is invalid rather than silently excluded.
Abstained and invalid results retain a fingerprinted score-model reference with the available
configuration, fit status, encoding, diagnostics, and model provenance; unavailable upstream
fields remain explicitly absent instead of being invented.

Pre- and post-weighting standardized mean differences retain the propensity result's complete
feature and encoding provenance. Feature coverage, statuses, maxima, and threshold counts are
validated against one another. When explicit upstream retention or downstream clipping changes
the estimation population or weights, balance is deterministically recomputed for that exact
population from the supplied table without refitting the propensity model. The result preserves
feature diagnostics and an aggregate acceptable/concern/severe status. Improvement alone does
not establish adequate adjustment. Structured sensitivity flags identify extreme weights, weak overlap, low ESS,
residual imbalance, heavy clipping, imbalanced prevalence, fit concerns, and unverified
identification assumptions. These flags diagnose; they do not correct an estimate.
Fatal overlap, effective-sample, or convergence refusals retain corresponding structured
`poor_overlap`, `low_ess`, or `propensity_convergence_concerns` flags in addition to their
primary abstention diagnostic.

## Uncertainty and interpretation

V1 uses an analytic fixed-propensity Hájek sandwich variance. For each arm `a`,

`V(mu_a) = [n_a/(n_a-1)] * sum(w_i^2 * (Y_i-mu_a)^2) / sum(w_i)^2`.

The effect variance is the sum of the two arm variances. Confidence intervals and two-sided
p-values use the standard-normal reference distribution, with arm-level `n/(n-1)` finite-sample
correction and no degrees-of-freedom parameter. The result reports the standard error, test
statistic, p-value, null effect, confidence level, bounds, interval method, and variance method.

This baseline conditions on fitted propensity scores. It does not account fully for uncertainty
from estimating the propensity model and can understate uncertainty. A computed estimate has
the causal status `conditional_on_declared_assumptions`: IPW does not remove unmeasured
confounding, successful weighting does not prove exchangeability, and non-significance does not
prove no effect. Extreme weights can make estimates unstable, and stabilization does not repair
poor overlap.

V1 supports continuous mean differences and binary risk differences. It does not implement
outcome regression, augmented IPW, doubly robust estimation, DML, heterogeneous effects,
formal unmeasured-confounding sensitivity analysis, business-impact calculation, or workflow
integration.
