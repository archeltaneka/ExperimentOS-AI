# Observational Causal Reliability

Issue #101 promotes the implemented observational causal surface into the same Phase 4
reliability baseline used by randomized inference. It does not introduce a second evaluator,
policy engine, report schema, command, or CI framework.

## Covered surface

The offline suite covers causal-identification contracts, two-group/two-period
Difference-in-Differences, deterministic logistic propensity diagnostics, IPW ATE, and IPW ATT.
References include identified and invalid contracts, known and null effects, overlap and balance,
model convergence, weight tails, effective sample size, explicit stabilization and clipping,
uncertainty, abstention, and fatal-upstream-gate behavior.

Identification metadata is blocking for successful observational effect estimates. The checks
require a declared estimand and target population, treatment, outcome, population, adjustment
set, causal assumptions, timing, identification state, and evidence limitations. Treatment,
outcome, post-treatment covariate, and invalidly timed effect-modifier leakage are blocking.
Assumptions retain their declared semantics: balance does not verify exchangeability, overlap
does not verify absence of unmeasured confounding, and a non-significant pre-trend diagnostic
does not verify parallel trends.

## Reference data and accuracy

The Phase 4 baseline loads its existing reference inventory plus
`data/eval/phase4_observational_reliability.json`. Both use the same strict case contract,
fixture provenance, evaluator, policy adapter, and artifacts. Every observational case records a
stable ID, design, estimand, target population, method, expected state, diagnostic expectations,
independent reference values and tolerances where applicable, and provenance.

DiD accuracy covers the four cell means, treated and comparison changes, DiD ATT, clustered CR1
uncertainty, confidence interval, p-value, and cluster metadata. Propensity references cover
support, convergence, overlap, raw and weighted SMD behavior, weights, ESS, and retention. IPW
references independently encode the ATE and ATT weight formulas, weighted arm means, estimates,
ESS and uncertainty, including explicit stabilization and clipping provenance.

Expected invalid designs and expected abstentions are correct outcomes. They must include the
expected reason and diagnostics and must not expose a point estimate, interval, p-value, or causal
conclusion. Spy-backed tests verify the IPW calculation engine is not invoked after invalid
identification, propensity non-convergence, fatal overlap, or ESS collapse.

## Versioned simulation

The initial coverage DGP is `did_parallel_trends_gaussian` version `1.0.0`, seed `101004`, 80
units, and 40 repetitions. Forty treated and forty comparison units are fixed before random
draws. The declared confounders are unit and group baselines; the outcome formula is
`8 + 2*treated_group + unit_baseline + 2*post + 3*treated_post + error`; the true estimand is a
DiD ATT of 3.0. Production DiD estimation uses cluster-robust CR1 intervals at 95% confidence.
The empirical coverage range of 0.80–1.00 is aspirational and advisory in v1, preventing a
stochastic-looking threshold from making CI flaky. Changing the DGP requires an explicit name or
version change in the fixture.

## Policy and failure classification

The centralized quality policy blocks reference-accuracy regressions, malformed or incomplete
identification, leakage, fatal-diagnostic bypass, non-converged propensity acceptance, fatal
overlap or ESS bypass, invalid DiD acceptance, non-finite results, missing effect-estimator
uncertainty, incorrect abstention, telemetry privacy violations, and deterministic-output
regressions. Weak overlap, high finite weights, residual imbalance, few clusters, divergent
pre-trends, heavy clipping, efficiency loss, and empirical coverage concerns are advisory when
the estimator remains statistically available.

Reports preserve expected invalid designs, expected abstentions, advisories, quality regressions,
infrastructure failures, and skipped capabilities as distinct states. Policy thresholds remain in
`config/evaluation/quality_policy.yaml`, never in GitHub Actions.

## Observability and privacy

The existing observability provider receives low-cardinality design, method, estimand,
identification, assumption and diagnostic codes, status, duration, aggregate sample counts,
overlap, ESS, balance, convergence, pre-trend, cluster-robust, clipping, stabilization, and overlap
gate metadata. In-memory tests cover successful, invalid, and abstained DiD, propensity, ATE, and
ATT paths. Telemetry and reliability artifacts reject row-level treatment or outcomes, covariate
values, propensity score arrays, unit-level weights, identifiers, and raw panel observations.

## Command, artifacts, and CI

Run the complete offline gate with:

```powershell
uv run python -m packages.evals.cli statistical-baseline
```

The command executes the prior randomized suite and the observational references and simulation,
applies centralized policy, and writes authoritative JSON plus derived Markdown. JSON contains
suite and case versions, case IDs, design, estimand, method, references, tolerances, policy rules,
diagnostics, simulation metadata, and durations. Markdown includes observational method status,
blocking failures, advisories, abstention correctness, determinism, coverage, telemetry privacy,
and limitations. GitHub Actions invokes this same command and uploads the existing Phase 4
artifact directory; blocking regressions fail CI while advisory-only findings succeed.

## Limitations

Reliability coverage does not add or cover DML, heterogeneous-effect estimation, EconML, DoWhy,
causal forests, unmeasured-confounding sensitivity analysis, automatic remediation, business
impact conversion, production causal dashboards, workflow integration, live LLM calls, network
services, or a database.
