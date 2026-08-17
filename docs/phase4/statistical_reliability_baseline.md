# Phase 4 Statistical Reliability Baseline

## Purpose

The Phase 4 statistical reliability baseline is the repository-owned, deterministic check for the
statistical surface implemented so far. It evaluates typed contracts and service outputs, classifies
the results through the centralized ExperimentOS quality policy, emits privacy-safe internal
telemetry, and produces CI-ready JSON and Markdown without a database or live service.

This baseline currently covers:

- statistical contracts;
- eligibility validation;
- descriptive statistics;
- fixed-horizon randomized experiment analysis;
- CUPED covariate adjustment;
- sequential testing with pre-registered looks;
- Bayesian A/B testing with explicit conjugate priors.

It does not replace the Phase 3 evaluation or quality gates.

## Run It Offline

```powershell
uv run python -m packages.evals.cli statistical-baseline
```

The direct module command is equivalent:

```powershell
uv run python -m packages.evals.run_statistical_baseline
```

Default artifacts:

- `reports/phase4/statistical_baseline.json` — authoritative structured result;
- `reports/phase4/statistical_baseline.md` — derived developer and CI investigation report.

Exit codes are:

- `0`: blocking policy passed; advisory findings may still be present;
- `1`: a blocking statistical reliability rule failed;
- `2`: dataset, policy, parsing, writing, or evaluation infrastructure failed.

No environment variable, credential, network service, database, live LLM, external judge, or
hosted observability provider is required.

## Reference Dataset

`data/eval/phase4_statistical_baseline.json` is a versioned repository-local inventory. Each case
declares a stable case ID, capability, category, method, analysis design, metric type, fixture ID,
expected status and estimator method, structured diagnostic codes, advisory codes, required
assumptions, required uncertainty fields, abstention state and reason, independently specified
expected values, deterministic configuration, reference provenance, notes, and fixture provenance.

The loader rejects malformed cases, duplicate IDs, unstable ordering, mismatched provenance, and
floating-point expectations without documented tolerances. The inventory includes successful,
invalid, unsupported, and expected-abstention outcomes. Expected invalid or abstained outcomes pass
when their structured state is correct; they are not converted into generic failures.

## Numerical Tolerance Philosophy

Categorical values and integer counts use exact equality. Every floating-point expectation declares
its own absolute tolerance, rationale, and provenance. Direct arithmetic summaries use tight
tolerances appropriate to small finite fixtures. Distribution-derived p-values use separately
documented tolerances based on independent standard-distribution references. Tolerances are stored
with each expected field and appear in both the structured checks and the Markdown tolerance table.

Expected values are hand-calculated or independently specified. The implementation under test is
never used to generate its own expectations, and tolerances are not widened to hide regressions.

## Reliability Dimensions

Reference accuracy checks counts, summaries, quantiles, arm statistics, effects, standard errors,
statistics, degrees of freedom, confidence intervals, p-values, methods, estimands, and statuses as
applicable.

Abstention correctness verifies the exact reason and diagnostic code and requires the absence of a
point estimate, interval, and p-value. Unsupported and invalid outcomes remain distinct from
abstention.

Diagnostic completeness uses structured codes and warning records. It checks required codes,
advisory codes, repeated ordering, and contradictory states without parsing prose.

Uncertainty completeness applies only to successful randomized inference. Fixed-horizon and CUPED
results require frequentist standard errors and confidence intervals. Sequential looks additionally
require the registered boundary, cumulative alpha, and look metadata. Bayesian results require
posterior effect summaries, credible intervals and levels, explicit prior/posterior parameters, and
posterior computation metadata. Bayesian checks never require p-values or confidence intervals.

Assumption completeness is method-specific and blocking for successful inference. CUPED discloses
randomization, pre-treatment and treatment-unaffected covariate semantics, supported analysis units,
and estimand preservation. Sequential results disclose preregistration, immutability, fixed arm and
outcome definitions, cumulative data, valid looks, and controlled alpha spending. Bayesian results
disclose prior family and parameters, likelihood, outcome model, computation method, and credible
interval method.

Sequential plan-integrity checks block fingerprint, arm, outcome, alpha, boundary, look-schedule,
duplicate-consumption, and cumulative-sample violations. An invalid plan cannot produce a valid
efficacy conclusion.

Determinism checks independent repeated execution, canonical structured serialization, diagnostic
ordering, row-order invariance, sequential fingerprints and histories, and analytic Bayesian
quadrature. Bayesian v1 has no sampling path, so seeded-sampling reproducibility is explicitly
reported as skipped rather than fabricated.

## Quality Policy

`config/evaluation/quality_policy.yaml` remains the only threshold and severity configuration. The
existing policy engine reads the authoritative baseline JSON through the additive
`statistical_baseline_json` adapter.

Blocking rules cover reference accuracy, abstention integrity, diagnostic and assumption
completeness, method-appropriate uncertainty, sequential plan integrity, Bayesian semantics,
telemetry privacy, determinism, status correctness, and non-finite output. Advisory rules cover
negative or negligible CUPED variance reduction, weak correlation, sample loss, imbalance, stable
Bayesian prior-dominance diagnostics, wide uncertainty, approximation proximity, latency, and
minimum reference coverage. Favorable statistical outcomes are never confused with software
correctness. Missing Phase 4 artifacts remain skipped for Phase 3-only policy runs.

The output keeps pass, fail, advisory, skipped, invalid, abstained, and unsupported meanings
separate. Advisory findings do not fail the CLI. Missing required data or malformed reports are
infrastructure errors rather than quality failures.

## Telemetry Privacy

Validation, descriptive statistics, and randomized analysis use the shared
`packages.observability` abstraction. Internal ExperimentOS buffered traces remain authoritative,
and provider failures cannot change statistical results.

Randomized spans contain only controlled inference family, method, estimand, status, aggregate
counts, structured diagnostic codes, abstention state, and duration. CUPED adds adjustment,
retention, variance-reduction, and covariate-eligibility states. Sequential adds look index,
boundary family, plan integrity, boundary crossing, and stopping state. Bayesian adds likelihood
and prior families, analytic computation mode, ROPE request state, and posterior-summary
availability. Tests recursively inspect successful and abstained/invalid in-memory traces.

Telemetry does not contain raw treatment or control outcomes, treatment assignments, adjusted
outcomes, covariate arrays, raw covariate values, posterior draws, sequential rows, full priors,
full experiment records, credentials, arbitrary analysis IDs, prompts, or private payloads.
Structured low-cardinality codes are used instead of arbitrary diagnostic messages.

## CI Behavior

The existing `offline-eval-smoke` GitHub Actions job runs the baseline with repository-local
fixtures, publishes the Markdown to the job summary, and uploads both artifacts under
`artifacts/ci/offline/phase4/`. No Phase 4 thresholds are duplicated in workflow YAML. The generic
CI report aggregator surfaces the Phase 4 suite, status, evaluated count, pass/fail counts,
abstentions, invalid cases, and advisories whenever the structured artifact is present.

## Limitations

This suite covers fixed-horizon randomized analysis, CUPED, sequential testing, and Bayesian A/B
testing. It does not yet cover:

- Difference-in-Differences;
- propensity scores or inverse-probability weighting;
- observational ATE or ATT;
- DML;
- heterogeneous treatment effects;
- EconML;
- DoWhy;
- business-impact estimation;
- product-intelligence workflow integration;
- production telemetry deployment;
- database-backed Phase 4 evaluation;
- live LLM evaluation.
