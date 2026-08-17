# Phase 4 Statistical Reliability Baseline

- Overall status: pass
- Baseline version: `2.0.0`
- Policy version: `2026-08-17`
- Machine-readable JSON is authoritative.

## Overall Randomized-Inference Status

- Status: pass
- Covered methods: fixed-horizon, CUPED, sequential, and Bayesian A/B.

## Fixed-Horizon Status

- Status: pass
- Cases: 7
- Blocking failures: 0
- Advisory findings: 0
- Skipped cases: 0

## CUPED Status

- Status: advisory
- Cases: 8
- Blocking failures: 0
- Advisory findings: 4
- Skipped cases: 0

## Sequential Status

- Status: advisory
- Cases: 12
- Blocking failures: 0
- Advisory findings: 4
- Skipped cases: 0

## Bayesian Status

- Status: advisory
- Cases: 15
- Blocking failures: 0
- Advisory findings: 1
- Skipped cases: 1

## Evaluated Capabilities

| Capability | Cases | Passed | Failed | Advisory |
| --- | ---: | ---: | ---: | ---: |
| eligibility_validation | 4 | 4 | 0 | 0 |
| descriptive_statistics | 2 | 2 | 0 | 0 |
| randomized_continuous | 5 | 5 | 0 | 0 |
| randomized_binary | 2 | 2 | 0 | 0 |
| cuped | 8 | 4 | 0 | 4 |
| sequential | 12 | 8 | 0 | 4 |
| bayesian_binary | 13 | 11 | 0 | 1 |
| bayesian_continuous | 2 | 2 | 0 | 0 |

## Summary Counts

- Dataset size: 48
- Cases passed: 38
- Cases failed: 0
- Cases advisory: 9
- Cases invalid: 13
- Cases abstained: 8
- Cases skipped: 1

## Blocking Failures

None.

## Advisory Findings

- `bayesian-informative-prior-advisory` / `statistics.performance.prior.treatment_dominance`: Statistical performance finding is advisory and does not invalidate output.
- `bayesian-informative-prior-advisory` / `statistics.performance.prior.control_dominance`: Statistical performance finding is advisory and does not invalidate output.
- `cuped-arm-imbalance-advisory` / `statistics.performance.eligibility.allocation.deviation_warning`: Statistical performance finding is advisory and does not invalidate output.
- `cuped-arm-imbalance-advisory` / `statistics.performance.cuped.covariate_arm_difference_observed`: Statistical performance finding is advisory and does not invalidate output.
- `cuped-arm-imbalance-advisory` / `statistics.performance.eligibility.sample.arm_imbalance`: Statistical performance finding is advisory and does not invalidate output.
- `cuped-missing-covariate-retention` / `statistics.performance.cuped.sample_rows_removed`: Statistical performance finding is advisory and does not invalidate output.
- `cuped-negative-variance-reduction` / `statistics.performance.cuped.covariate_arm_difference_observed`: Statistical performance finding is advisory and does not invalidate output.
- `cuped-negative-variance-reduction` / `statistics.performance.cuped.degraded_precision`: Statistical performance finding is advisory and does not invalidate output.
- `cuped-negative-variance-reduction` / `statistics.performance.cuped.negative_variance_reduction`: Statistical performance finding is advisory and does not invalidate output.
- `cuped-zero-variance-reduction` / `statistics.performance.cuped.weak_outcome_covariate_correlation`: Statistical performance finding is advisory and does not invalidate output.
- `sequential-early-efficacy-crossing` / `statistics.performance.eligibility.sample.total_weak`: Statistical performance finding is advisory and does not invalidate output.
- `sequential-early-efficacy-crossing` / `statistics.performance.eligibility.sample.arm_weak`: Statistical performance finding is advisory and does not invalidate output.
- `sequential-late-efficacy-crossing` / `statistics.performance.eligibility.sample.total_weak`: Statistical performance finding is advisory and does not invalidate output.
- `sequential-no-stop-sequence` / `statistics.performance.eligibility.sample.total_weak`: Statistical performance finding is advisory and does not invalidate output.
- `sequential-no-stop-sequence` / `statistics.performance.eligibility.sample.arm_weak`: Statistical performance finding is advisory and does not invalidate output.
- `sequential-null-sequence` / `statistics.performance.eligibility.sample.total_weak`: Statistical performance finding is advisory and does not invalidate output.

## Skipped Checks

None.

## Numerical Reference Failures

- Checks: 148
- Failures: 0
- Skipped: 0

## Abstention Correctness

- Checks: 98
- Failures: 0
- Skipped: 0

## Determinism

- Checks: 96
- Failures: 0
- Skipped: 0

## Telemetry Privacy

- Checks: 34
- Failures: 0
- Skipped: 0

## Assumption Completeness

- Checks: 20
- Failures: 0
- Skipped: 0

## Sequential Plan Integrity

- Checks: 12
- Failures: 0
- Skipped: 0

## Diagnostic Completeness

- Checks: 192
- Failures: 0
- Skipped: 0

## Uncertainty Completeness

- Checks: 179
- Failures: 0
- Skipped: 0

## Centralized Quality Policy

- Overall status: warning
- Blocking failures: 0
- Advisory findings: 2
- Skipped rules: 0

## Numerical Tolerances

| Case | Field | Absolute tolerance | Provenance |
| --- | --- | ---: | --- |
| `bayesian-binary-conjugate` | `treatment_posterior.prior.alpha` | 0.0 | Beta(1,1) fixture |
| `bayesian-binary-conjugate` | `treatment_posterior.prior.beta` | 0.0 | Beta(1,1) fixture |
| `bayesian-binary-conjugate` | `treatment_posterior.posterior_alpha` | 0.0 | 1 + 2 successes |
| `bayesian-binary-conjugate` | `treatment_posterior.posterior_beta` | 0.0 | 1 + 0 failures |
| `bayesian-binary-conjugate` | `treatment_posterior.posterior_mean` | 1e-12 | 3/(3+1) |
| `bayesian-binary-conjugate` | `treatment_posterior.posterior_variance` | 1e-12 | 3*1/(4^2*5) |
| `bayesian-binary-conjugate` | `control_posterior.posterior_alpha` | 0.0 | 1 + 1 success |
| `bayesian-binary-conjugate` | `control_posterior.posterior_beta` | 0.0 | 1 + 1 failure |
| `bayesian-binary-conjugate` | `effect.posterior_mean` | 1e-12 | 0.75 - 0.5 |
| `bayesian-binary-conjugate` | `effect.posterior_standard_deviation` | 1e-12 | sqrt(0.0375 + 0.05) |
| `bayesian-binary-conjugate` | `effect.credible_interval.lower` | 1e-10 | documented beta polynomial CDF reference |
| `bayesian-binary-conjugate` | `effect.credible_interval.upper` | 1e-10 | documented beta polynomial CDF reference |
| `bayesian-binary-conjugate` | `effect.probability_of_superiority.probability` | 1e-12 | P(Beta(3,1) > Beta(2,2)) |
| `bayesian-continuous-conjugate` | `treatment_posterior.prior.mu_0` | 0.0 | shifted NIG fixture |
| `bayesian-continuous-conjugate` | `treatment_posterior.posterior_mu` | 1e-12 | (1*1 + 3*3)/4 |
| `bayesian-continuous-conjugate` | `treatment_posterior.posterior_kappa` | 0.0 | 1 + 3 |
| `bayesian-continuous-conjugate` | `treatment_posterior.posterior_alpha` | 0.0 | 2 + 3/2 |
| `bayesian-continuous-conjugate` | `treatment_posterior.posterior_beta` | 1e-12 | 2 + 2/2 + (1*3*(3-1)^2)/(2*4) |
| `bayesian-continuous-conjugate` | `treatment_posterior.marginal_mean_variance` | 1e-12 | 4.5/(4*(3.5-1)) |
| `bayesian-continuous-conjugate` | `control_posterior.posterior_mu` | 1e-12 | (1*0 + 3*2)/4 |
| `bayesian-continuous-conjugate` | `effect.posterior_mean` | 1e-12 | 2.5 - 1.5 |
| `bayesian-continuous-conjugate` | `effect.posterior_standard_deviation` | 1e-12 | sqrt(0.45 + 0.45) |
| `bayesian-continuous-conjugate` | `effect.credible_interval.lower` | 1e-10 | documented NIG convolution reference |
| `bayesian-continuous-conjugate` | `effect.credible_interval.upper` | 1e-10 | documented NIG convolution reference |
| `bayesian-continuous-conjugate` | `effect.probability_of_superiority.probability` | 1e-10 | documented NIG convolution reference |
| `cuped-positive-variance-reduction` | `coefficient.theta` | 1e-12 | (19.5/7)/(10/7) |
| `cuped-positive-variance-reduction` | `coefficient.covariance` | 1e-12 | 19.5/7 |
| `cuped-positive-variance-reduction` | `coefficient.covariate_variance` | 1e-12 | 10/7 |
| `cuped-positive-variance-reduction` | `coefficient.correlation` | 1e-12 | (19.5/7)/sqrt((63.875/7)*(10/7)) |
| `cuped-positive-variance-reduction` | `adjusted_result.point_effect.absolute_effect.value` | 1e-12 | 6.125 - 2.875 |
| `cuped-positive-variance-reduction` | `adjusted_result.test_result.standard_error` | 1e-12 | sqrt(1.5433333333333334/4 + 0.03333333333333336/4) |
| `cuped-positive-variance-reduction` | `adjusted_result.test_result.confidence_interval.lower` | 1e-12 | independent t critical value with Welch df |
| `cuped-positive-variance-reduction` | `adjusted_result.test_result.confidence_interval.upper` | 1e-12 | independent t critical value with Welch df |
| `cuped-positive-variance-reduction` | `variance_reduction.fraction` | 1e-12 | 1 - 0.39375000000000016/3.5625 |
| `descriptive-binary-reference` | `population.summary.rate` | 1e-15 | 10 / 20 |
| `descriptive-binary-reference` | `treatment.summary.rate` | 1e-15 | 6 / 10 |
| `descriptive-binary-reference` | `control.summary.rate` | 1e-15 | 4 / 10 |
| `descriptive-binary-reference` | `raw_comparison.absolute_difference` | 1e-15 | 0.6 - 0.4 |
| `descriptive-binary-reference` | `raw_comparison.relative_difference` | 1e-15 | (0.6 - 0.4) / 0.4 |
| `descriptive-continuous-reference` | `population.summary.mean` | 1e-12 | sum([1,2,3,4,2,4,6,8]) / 8 |
| `descriptive-continuous-reference` | `population.summary.variance` | 1e-12 | 37.5 / 7 |
| `descriptive-continuous-reference` | `population.summary.quantiles.0.value` | 1e-12 | sorted position (8 - 1) * 0.25 |
| `descriptive-continuous-reference` | `population.summary.quantiles.1.value` | 1e-12 | average of the fourth and fifth ordered values |
| `descriptive-continuous-reference` | `population.summary.quantiles.2.value` | 1e-12 | sorted position (8 - 1) * 0.75 |
| `descriptive-continuous-reference` | `raw_comparison.absolute_difference` | 1e-12 | 5.0 - 2.5 |
| `descriptive-continuous-reference` | `raw_comparison.relative_difference` | 1e-12 | (5.0 - 2.5) / 2.5 |
| `randomized-binary-reference` | `point_effect.absolute_effect.value` | 1e-12 | 12/20 - 8/20 |
| `randomized-binary-reference` | `point_effect.relative_effect` | 1e-12 | 0.2 / 0.4 |
| `randomized-binary-reference` | `test_result.standard_error` | 1e-12 | sqrt(0.5 * 0.5 * (1/20 + 1/20)) |
| `randomized-binary-reference` | `test_result.statistic` | 1e-12 | 0.2 / sqrt(0.025) |
| `randomized-binary-reference` | `test_result.p_value` | 1e-10 | NIST standard normal CDF reference for z=1.2649110640673518 |
| `randomized-continuous-reference` | `treatment_summary.mean` | 1e-12 | mean([3,5,7,9,11]) |
| `randomized-continuous-reference` | `control_summary.mean` | 1e-12 | mean([2,4,6,8,10]) |
| `randomized-continuous-reference` | `treatment_summary.sample_variance` | 1e-12 | 40 / (5 - 1) |
| `randomized-continuous-reference` | `point_effect.absolute_effect.value` | 1e-12 | 7 - 6 |
| `randomized-continuous-reference` | `test_result.standard_error` | 1e-12 | sqrt(10/5 + 10/5) |
| `randomized-continuous-reference` | `test_result.statistic` | 1e-12 | 1 / 2 |
| `randomized-continuous-reference` | `test_result.degrees_of_freedom` | 1e-12 | (2+2)^2 / (2^2/4 + 2^2/4) |
| `randomized-continuous-reference` | `test_result.p_value` | 1e-10 | NIST Student t reference for t=0.5, df=8 |
| `randomized-continuous-zero-baseline` | `point_effect.absolute_effect.value` | 1e-12 | mean([1,2,3]) - mean([-1,0,1]) |
| `sequential-null-sequence` | `plan.planned_looks.0.information_time` | 0.0 | two-look registered plan |
| `sequential-null-sequence` | `plan.planned_looks.1.information_time` | 0.0 | two-look registered plan |
| `sequential-null-sequence` | `boundaries.0.critical_boundary` | 1e-12 | independent normal quantile at first-look nominal alpha |
| `sequential-null-sequence` | `boundaries.0.cumulative_alpha_spent` | 1e-15 | two-sided O'Brien-Fleming spending formula |
| `sequential-null-sequence` | `boundaries.0.nominal_alpha` | 1e-15 | first cumulative spend minus zero |
| `sequential-null-sequence` | `boundaries.1.critical_boundary` | 1e-12 | independent normal quantile at final nominal alpha |
| `sequential-null-sequence` | `boundaries.1.cumulative_alpha_spent` | 1e-15 | registered total alpha |
| `sequential-null-sequence` | `boundaries.1.nominal_alpha` | 1e-15 | 0.05 - 0.005574596680784402 |
| `sequential-null-sequence` | `current_look.standardized_statistic` | 0.0 | null cumulative outcome sequence |
| `sequential-null-sequence` | `alpha_summary.cumulative_alpha_spent` | 1e-15 | two-look O'Brien-Fleming spending reference |

## Limitations

- Difference-in-Differences, propensity scores, and observational ATE/ATT are not covered.
- Inverse-probability weighting, DML, HTE, EconML, and DoWhy are not covered.
- Business-impact conversion, auto-stop actions, rollout automation, and dashboards are not covered.
- Bayesian v1 uses deterministic quadrature and has no seeded sampling path to evaluate.

## Offline Execution

- Offline deterministic providers only; no network, live LLM, database, external judge, or hosted telemetry is required.
