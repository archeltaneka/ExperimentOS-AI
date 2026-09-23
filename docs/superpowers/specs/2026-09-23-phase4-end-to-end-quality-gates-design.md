# Complete Phase 4 end-to-end causal quality gates

Issue: https://github.com/archeltaneka/ExperimentOS-AI/issues/109
Branch: `109-complete-phase4-causal-quality-gates`, linked to issue #109.
Status: architecture approved; detailed specification awaiting review.

## Purpose and scope

Complete the existing Phase 4 reliability system from an actual workflow/API
request through method routing, native analysis, optional business impact,
serialization, observability, centralized policy, artifacts, and CI exit status.
The audience is maintainers diagnosing regressions and reviewers evaluating
whether changes preserve statistical and causal contracts.

Issue #109 and `docs/phase4/complete_end_to_end_causal_quality_gates.md` are
authoritative. The latter contains duplicated sections and a pasted continuation;
the repeated requirements are cumulative, not separate implementations. Preserve
that user-owned file without committing it.

Execution must be deterministic and offline: repository fixtures, fixed seeds,
fake embeddings, mock LLMs, in-memory telemetry, and no mandatory database or
optional causal libraries. No new statistical methods, frontend, hosted telemetry,
deployment, production alerts, merge, branch-protection change, or final human
reliability review is included.

## Existing architecture and chosen extension points

The approved approach is composition within the current evaluation system.

| Existing component | Extension |
| --- | --- |
| `packages/evals/run_statistical_baseline.py` | Canonical complete Phase 4 command orchestration, centralized policy, safe failure artifacts, exit decision. |
| `packages/evals/statistical/` | Preserve randomized, observational, and advanced reference evaluation; extend report contracts and rendering with workflow results. |
| `packages/evals/agent_analysis_cases.py` | Versioned complete workflow cases, independent expectations, applicability, preservation checks; split focused helpers as needed. |
| `packages/evals/agent_e2e.py` | Reuse real `/ask` execution for analysis cases and existing legacy API scenarios. |
| `packages/evals/policy/` and `config/evaluation/quality_policy.yaml` | Add strict workflow report ingestion and missing invariants to the existing policy registry. |
| `packages/experiments/analysis/orchestration/` | Fix only integration defects demonstrated by new tests; retain native estimator ownership. |
| `packages/observability/` | Reuse logical spans, safe providers, redaction, and optional OpenTelemetry. |
| `packages/evals/ci_reporting/` | Extend existing Phase 4 suite summary and informational PR report. |
| `.github/workflows/ci.yml` | Orchestrate the canonical command, preserve existing jobs, and upload failure artifacts. |

The existing workflow helper compares native results for fixed-horizon, DiD, and
an injected unavailable EconML request. It lacks complete method coverage and
independent numerical references at the workflow boundary. The baseline already
loads randomized, observational, and advanced datasets and evaluates centralized
statistics rules. The report already carries per-check rule IDs and evidence.
These are the integration seams; no new policy engine is needed.

A separate top-level orchestrator would introduce a competing final command.
A new policy framework would duplicate existing rules. Neither is selected.

## Canonical execution path

Retain this command and its established JSON/Markdown output options:

```bash
uv run python -m packages.evals.cli statistical-baseline
```

Default execution performs, in order:

1. Validate policy, reference fixtures, workflow case schema, and required inventory.
2. Execute existing native reference/conformance evaluations.
3. Execute complete workflow cases through `/ask`, the real agent workflow,
   AnalysisService, native services, and response serialization. Override only
   external dependencies such as experiment existence, retrieval, and model calls.
4. Exercise deterministic failure injection and prohibited downstream-call checks.
5. Check reference values, preservation, immutability, repeatability, trace linkage,
   and privacy. Include explicit existing-surface compatibility checks.
6. Serialize safe structured results and apply the existing centralized policy.
7. Write final JSON, detailed Markdown, policy JSON, and a concise job summary.
8. Return the established exit code: 0 for quality pass, 1 for blocking regression,
   2 for fixture/configuration/evaluation/reporting infrastructure failure.

Do not use Markdown as policy input. A failed case must not prevent collection of
other independent case results. Unusable fixture inventories or malformed policy
inputs stop dependent execution and produce an infrastructure result. If rendering
fails, retain safe structured evidence and return 2; if the output destination is
unwritable, emit only a sanitized stderr diagnostic and return 2.

Retain native evaluator APIs for focused use. A documented optional-adapter scope
on this same command can restrict the existing extras job to installed-adapter
conformance and adapter workflow cases. The default scope always includes all core
families. Scoped artifacts declare their scope and cannot satisfy complete-suite
inventory requirements.

## Golden cases and execution ownership

Extend `data/eval/workflow_analysis/` and its loader. Cases are frozen, versioned,
extra-forbidding models with stable IDs, sorted execution, duplicate rejection,
and a required capability inventory independent of the supplied case list.

Each case declares family, method, design, estimand, fixture reference, request,
expected routing, native/public status, diagnostic and assumption requirements,
uncertainty requirements, reproducibility provenance, optional business status,
workflow status, expected policy findings, and justified numerical tolerances.
Expected invalid requests are permitted only when explicitly declared; malformed
case metadata remains an infrastructure error. Injection identifiers come from a
closed repository-owned registry, never executable fixture content.

Use small existing native fixtures and independent published/analytical reference
values. Reuse `StatisticalExpectedValue` and `StatisticalTolerance` semantics.
Comparing a native result to the workflow result tests preservation; it is not a
numerical oracle. Expected numerical values must not be recalculated by production
code. Each floating-point reference records absolute/relative tolerance, rationale,
and provenance. Categorical fields compare exactly.

| Family | Representative successful checks | Refusal and injected-regression coverage |
| --- | --- | --- |
| Fixed horizon | Effect, interval/level/method, randomization assumptions, provenance | Insufficient sample; fabricated p-value, missing uncertainty, false success. |
| CUPED | Adjustment, theta, retained population, variance metadata, uncertainty | Post-treatment covariate; population mismatch, fabricated variance reduction. |
| Sequential | Registered plan fingerprint, look, boundary, spending, native status | Invalid/mutated plan; duplicate spending, invalid efficacy declaration. |
| Bayesian | Prior/likelihood, posterior, credible interval and level | Invalid prior; missing prior, CI/credible confusion, undeclared ROPE. |
| DiD | Timing, ATT target, parallel trends/no anticipation, uncertainty | Unsupported adoption/timing; missing uncertainty. |
| Propensity | Fit provenance, overlap, SMD, ESS; no treatment effect | Nonconvergence/no overlap; false eligibility, silent trimming/clipping. |
| IPW ATE | ATE population/weights, overlap gate, uncertainty | Invalid identification/overlap; bypass, clipping, wrong weighting. |
| IPW ATT | Distinct treated target and weighting, uncertainty | Invalid identification/overlap; ATE substitution, missing uncertainty. |
| DML | Seed, cross-fitting/fold fingerprint, nuisance provenance, inference | Degenerate residuals; same-fold leakage, nondeterministic folds. |
| HTE | Declared pre-treatment modifier, subgroup uncertainty, direct heterogeneity, multiplicity | Sparse/post-treatment modifier; unsupported subgroup certainty or heterogeneity. |
| EconML DML/HTE | Supported installed adapter, identity, normalized owned inference | Absence; installed malformed result, unsupported inference, raw object/exception. |
| DoWhy | Supported identification/estimation/refutation contracts and graph fingerprint | Absence; unidentified success, contradictory graph, refuter presented as proof. |
| Business impact | Explicit sourced assumptions, effect uncertainty, scenario interval | Missing inputs/provenance, incompatible units, invalid source, invented values. |
| Workflow | Requested method, real state and API boundaries, conservative decision | Unsupported/ambiguous routing, substitution, abstention promoted to success, prose mutation. |

Include valid negative business impact and an interval crossing zero. Both retain
uncertainty and pass correctness gates; neither generates a rollout recommendation.
Business eligibility follows existing source contracts: propensity/identification
are not effects, sequential look-level intervals are not ordinary impact inputs,
and current DoWhy estimation lacks required impact uncertainty. Do not manufacture
successful impact cases for these unsupported conversions.

Optional absence cases use deterministic owned dependency doubles. Additional
installed-capability cases run when supported dependencies exist. Installed but
broken adapters remain failures, not unavailable. Repository DML/HTE always run.

## Assertions and failure injection

Check required evidence at native result, service envelope, workflow state, API
response, and report boundaries. Preserve assumptions and their asserted/unverified
status, blocking and advisory diagnostics, method-appropriate uncertainty, estimand,
and applicable provenance. Explicit applicability prevents irrelevant fields from
being required and prevents missing required checks from becoming silent skips.

Use spies to prove invalid identification prevents estimation, fatal overlap
prevents conclusive effects, invalid analysis prevents business calculation, missing
business provenance prevents calculation, and abstention prevents conclusive
decision evidence. Output inspection alone is insufficient.

Inject deterministic service exceptions, malformed owned/adapter results, missing
uncertainty/provenance, result mutation, provider failure, rendering failure,
malformed fixtures, and malformed policy inputs. For every family, test that the
relevant policy detects deliberately corrupted evidence. Distinguish expected
injection detection from an actual gate failure: an injection case passes only when
the declared defensive behavior or blocking finding is observed. It must fail when
the corruption escapes detection.

Fake generated summaries contradict effect, p-value, interval, posterior quantity,
and business impact. Typed evidence remains authoritative and unchanged; conflicting
prose is rejected/sanitized/flagged by existing integrity/factuality behavior. Do not
copy rejected prose into artifacts or traces.

Determinism compares semantic results after removing only declared volatile fields
such as duration, timestamps, and request-generated IDs. Never remove seeds, plan,
fold/configuration fingerprints, estimates, diagnostics, or policy outcomes.

## Policy and statuses

Execution status and quality verdict remain separate dimensions. Preserve existing
native statuses and public envelope statuses (`completed`, `inconclusive`, `invalid`,
`abstained`, `unavailable`, `failed`). Reports label successful/advisory/skipped
quality outcomes using existing check/policy enums rather than replacing them.

An expected abstention, invalid request, or normalized injected failure can pass its
quality checks. An unavailable optional capability records a reason and does not
block core CI. A skipped test is never reported as executed or passed.

Quality aggregation: any blocking violation means fail; otherwise any advisory
means warning; an entirely unexecuted optional scope is skipped; otherwise pass.
Infrastructure failure is a separate run classification, with exit 2 taking
precedence if both infrastructure and quality failures occur. Retain all findings.

Reuse existing `statistics.*` and `analysis.*` rule dimensions where semantics
match. Add only missing invariants for fabrication, downstream bypass, mutation,
routing, required provenance/assumptions/uncertainty, finite outputs, reproducibility,
trace linkage, privacy, and compatibility. Retain distinct method-specific rules for
sequential plans, DML folds, HTE modifiers, and adapter inference. Consolidate true
duplicates without weakening Phase 3 thresholds or historical artifact readers.

Every failure includes method, case/dataset identity, rule ID, severity, and safe
diagnostic evidence. Do not attach one ambiguous aggregate method to all findings.
Validate artifact inventory and check applicability before trusting aggregate counts;
missing/duplicate cases or forged all-pass summaries cannot satisfy the gate.

Valid weak overlap, high permitted weights, few clusters, pretrend concerns,
negative CUPED reduction, wide/cross-zero uncertainty, prior/refuter sensitivity,
tolerated cross-library differences, and negative impact remain advisory where
existing contracts permit them. No effect-sign or significance threshold becomes
a software-quality requirement.

## Observability and privacy

Follow existing logical trace ownership: request/workflow, analysis, validation or
identification, estimator/adapter, business, serialization, and evaluation/policy.
Policy may be a suite-level operation; associate case evidence through safe IDs
rather than pretending evaluation occurs inside an already-finished request span.
Test trace/correlation continuity and actual parent-child relationships. Add only
missing spans or linkage metadata required to observe these boundaries.

Capture owned provider records and, when available, OpenTelemetry in-memory export.
The core suite does not require hosted export or optional telemetry dependencies;
SDK-specific integration tests run in the existing observability environment.
Provider failures must leave estimator/workflow/API results intact and produce a
safe failure diagnostic without exception messages containing source data.

Recursively inspect span attributes, events, metrics labels, exception metadata,
nested values, JSON, Markdown, and job summaries. Reject raw outcomes, assignments,
covariates, unit IDs, scores, weights, residuals, nuisance predictions, CATE arrays,
posterior draws, graphs, business records, prompts with rows, and credentials.
Use allowlisted categorical metadata and sentinel-based value tests, not only
top-level forbidden keys. Aggregate estimates and justified reference values may
appear in reports. Unknown injected values must be replaced by safe evidence codes.

## Artifact and CI design

Version the extended `StatisticalBaselineReport` schema while preserving existing
native case fields and public invocation. Add a typed workflow section with case
version, family, routing, status, checks, safe evidence summaries, business checks,
trace/privacy findings, duration, and compatibility results. Existing agent/E2E
reports continue to use the same case inventory and checks. Avoid serializing raw
requests or datasets in any report.

Default artifacts remain under `reports/phase4/`:

- `statistical_baseline.json`: authoritative native and workflow results.
- `statistical_baseline.md`: detailed derived report.
- `quality_policy.json`: centralized evaluated policy findings.
- `github_summary.md`: concise status, capability counts, blocking/advisory findings,
  unavailable/skipped groups, compatibility/privacy, and artifact locations.

Additional paths follow the existing output-option convention. Re-rendering one
structured report is deterministic. Report schema failures and renderer failures
are distinguishable from statistical regressions. Do not reuse stale artifacts
after a failed invocation; write a current safe run-failure record when possible.

The offline Actions job runs the expanded canonical command and always publishes
available artifacts and summary. Python remains the authority for policy. Keep
the PostgreSQL integration job, Phase 3 quality gates, final job dependencies,
least-privilege permissions, pinned actions, and fork-safe comment behavior.
Reuse the existing Python 3.13 optional-adapter job with the same policy and a
restricted adapter scope to avoid duplicating the complete suite.

Extend the existing CI report's Phase 4 suite with business/workflow status and
findings; use the existing PR comment mechanism only. No new bot or automatic
message publication is part of implementation.

## Compatibility and verification

Maintain a named compatibility matrix for old `/ask` response shape, ordinary
agent routing/retrieval/approval/summary, selectable `legacy_rag`, prompts, RAG and
agent/E2E/factuality evaluation, internal traces, optional LangSmith/Phoenix/OTel,
and existing Phase 3 policy. Reuse current deterministic tests and real workflow
tests; stubbed API envelope tests alone do not prove workflow compatibility.

Use TDD for new reliability behavior. Focused tests cover strict dataset loading,
every method family, numerical tolerances, expected injections, policy precedence,
artifact schemas/rendering/redaction, command exit codes, trace linkage, provider
isolation, and old surface compatibility. Then execute:

- Complete default offline Phase 4 command.
- Existing Phase 3 verification suite via `uv run python scripts/verify_phase3.py`;
  use `--offline-only` when the database is absent and explicitly report that this
  is a non-closeout diagnostic, not a successful strict Phase 3 closeout. Preserve
  its native exit semantics and report database-related incompleteness separately
  from actual executed-check failures.
- Targeted API/workflow and compatibility tests, plus required existing CI tests.
- `uv run ruff check .` and `uv run mypy` (configured analysis scope).
- Prompt registry validation, prompt experiment validation for
  `rag-answer-abstention-v1-v2`, and observability configuration validation.
- Database-backed tests when `DATABASE_URL` is available, following existing test
  conventions; otherwise record exact skipped groups and the unset-variable reason.

The offline command does not silently initiate database tests. Its artifact records
that database validation is external to the core suite; when the variable is unset,
record an explicit skip. A configured database is not evidence that tests passed:
only attach a passed status from actual execution. Preserve database CI coverage.

Final review checks policy duplication, YAML thresholds, optional absence versus
broken installation, unfavorable outcomes versus failures, fabricated inputs,
downstream bypass, mutation, privacy, and Phase 3/API compatibility. Completion
requires exact verification results, documented skips/limitations, and a final
report of changed files, cases, rules, commands, artifacts, CI, and compatibility.

## Next workflow stage

Review this written specification. After approval, write a concrete implementation
plan with test-first tasks and choose its execution method according to the required
Superpowers workflow. Product implementation has not started at this stage.
