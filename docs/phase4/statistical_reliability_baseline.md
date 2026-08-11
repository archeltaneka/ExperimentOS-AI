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
- unadjusted randomized experiment analysis.

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
declares a stable case ID, capability, category, analysis design, metric type, fixture ID, expected
status and method, structured diagnostic codes, advisory codes, abstention state and reason,
independently specified expected values, notes, and fixture provenance.

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

Uncertainty completeness applies only to successful randomized inference. It requires a point
effect, standard error, finite ordered confidence interval, matching confidence level, p-value,
method, estimand, and both arm counts. Descriptive and abstained cases do not receive inappropriate
inferential requirements.

Determinism checks repeated execution, canonical structured serialization, diagnostic ordering, and
row-order invariance for fixtures where row order is mathematically irrelevant. Fixtures contain no
randomness.

## Quality Policy

`config/evaluation/quality_policy.yaml` remains the only threshold and severity configuration. The
existing policy engine reads the authoritative baseline JSON through the additive
`statistical_baseline_json` adapter.

Blocking rules cover overall case failures, reference accuracy, abstention integrity, diagnostic
completeness, uncertainty completeness, determinism, status correctness, and non-finite output.
Advisory rules cover advisory case findings and minimum reference coverage per implemented
capability. Missing Phase 4 artifacts remain skipped for Phase 3-only policy runs, preserving Phase
3 behavior. When the statistical artifact is present, all statistical rules are evaluated and their
exact IDs, severities, statuses, observed values, and thresholds are embedded in the baseline JSON.

The output keeps pass, fail, advisory, skipped, invalid, abstained, and unsupported meanings
separate. Advisory findings do not fail the CLI. Missing required data or malformed reports are
infrastructure errors rather than quality failures.

## Telemetry Privacy

Validation, descriptive statistics, and randomized analysis use the shared
`packages.observability` abstraction. Internal ExperimentOS buffered traces remain authoritative,
and provider failures cannot change statistical results.

Randomized spans contain only controlled method, estimand, metric type, status, aggregate arm and
eligible counts, structured diagnostic codes, warning counts, abstention state, duration, and
evaluation status. Tests recursively inspect every emitted key and value for successful and
abstained runs.

Telemetry does not contain raw treatment or control outcomes, outcome arrays, covariate arrays,
raw covariate values, full rows, credentials, arbitrary analysis IDs, prompts, or private payloads.
Structured low-cardinality codes are used instead of arbitrary diagnostic messages.

## CI Behavior

The existing `offline-eval-smoke` GitHub Actions job runs the baseline with repository-local
fixtures, publishes the Markdown to the job summary, and uploads both artifacts under
`artifacts/ci/offline/phase4/`. No Phase 4 thresholds are duplicated in workflow YAML. The generic
CI report aggregator surfaces the Phase 4 suite, status, evaluated count, pass/fail counts,
abstentions, invalid cases, and advisories whenever the structured artifact is present.

## Limitations

This baseline does not yet provide the broad reliability gates planned for:

- CUPED adjustment performance and production policy hardening;
- sequential testing;
- Bayesian analysis;
- Difference-in-Differences;
- propensity scores;
- observational causal inference or treatment-effect estimation;
- DML;
- heterogeneous treatment effects;
- EconML;
- DoWhy;
- business-impact estimation;
- product-intelligence workflow integration;
- production telemetry deployment;
- database-backed Phase 4 evaluation;
- live LLM evaluation.
