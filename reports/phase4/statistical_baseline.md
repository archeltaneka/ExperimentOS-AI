# Phase 4 Statistical Reliability Baseline

- Overall status: pass
- Baseline version: `1.0.0`
- Policy version: `2026-08-11`
- Machine-readable JSON is authoritative.

## Evaluated Capabilities

| Capability | Cases | Passed | Failed | Advisory |
| --- | ---: | ---: | ---: | ---: |
| eligibility_validation | 4 | 4 | 0 | 0 |
| descriptive_statistics | 2 | 2 | 0 | 0 |
| randomized_continuous | 5 | 5 | 0 | 0 |
| randomized_binary | 2 | 2 | 0 | 0 |

## Summary Counts

- Dataset size: 13
- Cases passed: 13
- Cases failed: 0
- Cases advisory: 0
- Cases invalid: 4
- Cases abstained: 3
- Cases skipped: 0

## Blocking Failures

None.

## Advisory Findings

None.

## Skipped Checks

None.

## Numerical Reference Failures

- Checks: 44
- Failures: 0
- Skipped: 0

## Abstention Correctness

- Checks: 25
- Failures: 0
- Skipped: 0

## Determinism

- Checks: 26
- Failures: 0
- Skipped: 0

## Diagnostic Completeness

- Checks: 52
- Failures: 0
- Skipped: 0

## Uncertainty Completeness

- Checks: 30
- Failures: 0
- Skipped: 0

## Centralized Quality Policy

- Overall status: pass
- Blocking failures: 0
- Advisory findings: 0
- Skipped rules: 0

## Numerical Tolerances

| Case | Field | Absolute tolerance | Provenance |
| --- | --- | ---: | --- |
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

## Limitations

- CUPED, sequential testing, Bayesian analysis, and Difference-in-Differences are not covered.
- Propensity scores, observational treatment effects, DML, and HTE are not covered.
- EconML, DoWhy, business-impact estimation, and product workflows are not covered.

## Offline Execution

- Offline deterministic providers only; no network, live LLM, database, external judge, or hosted telemetry is required.
