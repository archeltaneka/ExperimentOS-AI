# Phase 3 End-to-End Reliability Closeout Design

## Purpose

Issue #68 closes Phase 3 by verifying that ExperimentOS AI's evaluation, prompt lifecycle,
observability, CI reporting, database-backed retrieval, and public API behavior operate as one
coherent production-oriented portfolio system. The work fixes only demonstrated integration,
configuration, security, reporting, test, command, dependency, and documentation defects. It does
not add a new platform or claim production deployment at scale.

## Non-Negotiable Boundaries

- `agent_workflow` remains the default `POST /ask` implementation.
- `legacy_rag` remains supported and covered by deterministic verification.
- The public `POST /ask` request and response contract remains unchanged.
- Deterministic agents remain prompt-free.
- ExperimentOS-owned models, traces, metrics, policies, and reports remain authoritative.
- RAGAS and DeepEval remain optional evaluation adapters.
- LangSmith and Phoenix remain optional external sinks.
- OpenTelemetry remains an optional vendor-neutral export layer.
- GitHub Actions orchestrates repository commands and does not own quality thresholds.
- Default verification makes no live model, judge, LangSmith, Phoenix, or OTLP calls.
- The work does not weaken thresholds, suppress failures, auto-promote prompts, or expand Phase 4
  scope.

## Selected Approach

Add a thin repository-owned closeout orchestrator backed by focused typed validation and report
models. The orchestrator invokes existing CLIs and quality-policy code, validates their artifacts,
records durations and exit codes, and renders the final closeout reports. It does not copy metric
implementations or quality thresholds.

This is preferred over extending `scripts/run_ai_quality_gate.py`, whose contract is CI-specific,
and over a monolithic verifier that would create a second reliability authority.

## Verification Entry Point

The local entry point is:

```powershell
uv run python scripts/verify_phase3.py
```

Strict full verification is the default. It requires `DATABASE_URL` to reference an available local
PostgreSQL 16 database with pgvector support. It validates the configured environment, applies all
Alembic migrations from the current database state, deterministically ingests the repository CI
fixture, verifies repeat ingestion, runs focused database/API/workflow checks, and executes all
required Phase 3 evaluation commands.

The diagnostic-only mode is:

```powershell
uv run python scripts/verify_phase3.py --offline-only
```

`--offline-only` skips database-dependent checks. Its output is explicitly marked as a non-closeout
diagnostic and its milestone recommendation can never be `ready_to_close`, even when every executed
check passes.

The verifier does not start or stop Docker automatically. Documentation provides the exact Compose
and `DATABASE_URL` preparation commands so the database lifecycle remains explicit and does not
destroy or replace developer data.

## Component Boundaries

### Orchestration

`scripts/verify_phase3.py` parses arguments, installs the offline-safe environment, invokes a typed
verification service, prints a concise summary, and returns the service's exit code.

The verification service owns:

- ordered command definitions;
- per-command timeouts and duration capture;
- required versus optional check classification;
- child-process environment hardening;
- exit-code preservation;
- report-presence and schema validation;
- recommendation derivation;
- final Markdown and JSON rendering.

It does not own evaluation algorithms, quality thresholds, prompt definitions, observability
provider behavior, database migrations, or API schemas.

### Existing Authorities

The verifier reuses these existing authorities:

- dataset loaders in `packages.evals.dataset` and `packages.evals.agent_dataset`;
- prompt registry and experiment validators;
- observability settings and provider diagnostics;
- the custom RAG, agent, and `/ask` evaluation CLIs;
- RAGAS and DeepEval adapters;
- prompt regression and prompt experiment runners;
- factuality detectors and policy;
- centralized quality-policy evaluation;
- Alembic and ingestion commands;
- focused pytest suites;
- `scripts/run_ai_quality_gate.py` behavior and artifacts where CI parity is being checked.

### Reports

Routine execution evidence is written below a configurable `artifacts/phase3/verification`
directory. The curated closeout artifacts are:

- `reports/phase3/final_reliability_review.md`
- `reports/phase3/final_reliability_review.json`

Curated reports use repository-relative paths and contain no developer-absolute paths or secrets.

## Execution Stages

Strict verification runs these stages in order:

1. Validate the lockfile, environment safety, policy invariants, prompts, prompt experiments, and
   golden datasets.
2. Run formatting, linting, and focused verification/reliability tests.
3. Apply Alembic migrations and ingest the deterministic CI fixture using fake embeddings.
4. Re-ingest the fixture to prove idempotency and run database-backed retrieval, API, workflow, and
   evaluation smoke tests.
5. Run custom RAG evaluation with fake embeddings and a mock LLM.
6. Run deterministic custom agent and `/ask` end-to-end evaluations.
7. Run offline-safe RAGAS and offline DeepEval with judge providers disabled.
8. Run prompt registry validation, prompt regression, prompt experiment validation, and the sample
   offline prompt experiment.
9. Run deterministic factuality evaluation with failure-on-violation behavior.
10. Run NoOp, LangSmith dry-run, Phoenix dry-run, OpenTelemetry in-memory trace/metric, composite,
    redaction, sampling, correlation, and failure-isolation checks.
11. Run the centralized quality policy in strict mode and validate every required input report.
12. Generate and validate final Markdown and JSON closeout reports.

Safe report generation continues after a failed command when enough evidence exists to describe the
failure. The verifier preserves the first required non-zero result instead of replacing it with a
later rendering success. Missing reports, malformed reports, timeouts, policy failures, factuality
invariant failures, database failures, and unsafe provider configuration all produce non-zero exits.

## Environment and Network Safety

The verifier creates a child-process environment with these mandatory values:

- `APP_ENV=verification`
- `ASK_MODE=agent_workflow`
- `EMBEDDING_PROVIDER=fake`
- `LLM_PROVIDER=mock`
- `RAGAS_JUDGE_LLM_PROVIDER=none`
- `RAGAS_JUDGE_EMBEDDING_PROVIDER=none`
- `DEEPEVAL_JUDGE_PROVIDER=none`
- `PROMPT_EXPERIMENTS_ENABLED=false`
- all LangSmith, Phoenix, and OpenTelemetry enable flags set to `false`
- the OpenTelemetry exporter type set to `none`
- model and observability credentials cleared from child processes
- `PYTHONHASHSEED=0`

The initial safety validator rejects a conflicting live-provider or external-export configuration
instead of silently overriding and concealing it. Tests patch network-capable construction points so
default verification fails if any external client or exporter is created. Local PostgreSQL access
is the only networked service allowed in strict mode.

Repository application defaults become fake/mock when provider variables are absent. The existing
`auto` option remains supported only as an explicit user configuration and is never used by the
verification path.

## Dataset Integrity and Versioning

The current JSON list format remains unchanged. A shared dataset inspection function validates and
returns a typed manifest containing:

- repository-relative dataset identifier;
- deterministic SHA-256 content fingerprint used as the dataset version;
- case count and ordered case IDs;
- category coverage;
- duplicate status;
- validation status.

QA validation enforces known categories, `easy|medium|hard` difficulty, citation expectation types,
known failure modes, and non-empty required evidence fields. Agent validation enforces known
categories, intents, workflow agent names, decision statuses, recommendations, summary statuses,
approval statuses, failure modes, and cross-field expectations. Load order remains file order.

The dataset fingerprint is added to structured evaluation output so CI metric deltas are compared
only for matching policy and dataset versions. This repairs the existing integration where PR
reporting understands dataset versions but the real evaluation report does not emit one.

## Architecture and Compatibility Checks

Static and runtime checks verify:

- core services do not import third-party evaluation result types;
- business services do not call vendor observability SDKs directly;
- workflow YAML contains no duplicated quality thresholds;
- third-party run IDs are absent from public API models;
- prompt experiment context is not caller-controlled through `POST /ask`;
- deterministic agent modules do not import the prompt registry or LLM prompt definitions;
- `rag.answer` is the only experimentable prompt surface;
- no prompt is promoted by experiment execution;
- experiment reports state that offline results do not establish production causal impact;
- internal trace IDs correlate optional sinks while external IDs remain adapter metadata.

API tests preserve the current `AskRequest` and `AskResponse` schema for successful, abstaining,
invalid, retrieval-error, model-error, unknown-experiment, decision, and approval paths in both
workflow modes.

## Factuality Guarantees

The closeout layer explicitly verifies zero allowed findings for:

- fabricated revenue or ROI;
- fabricated statistical significance;
- fabricated experiment results;
- contradictions with structured decisions;
- contradictions with approval state.

Existing detector categories and finding-level diagnostics remain authoritative. If decision and
approval contradictions continue to share the structured-contradiction category, the final report
separately derives their counts from detector metadata and structured field identifiers rather than
creating a second detector taxonomy.

The centralized policy adds only missing explicit zero-tolerance assertions. Existing thresholds are
not lowered. Tests retain the prior false-positive remediations, abstention behavior, report-table
validity, severity consistency, and detailed diagnostics.

## Observability Verification

Verification covers:

- NoOp provider behavior with all external sinks disabled;
- LangSmith and Phoenix configuration validation and dry-run redaction without network calls;
- OpenTelemetry in-memory trace and metric export;
- composite fan-out and provider failure isolation;
- one manual ExperimentOS trace hierarchy;
- one OpenTelemetry initialization authority;
- no duplicate graph spans;
- internal trace-ID correlation;
- deterministic sampling behavior;
- prompt, response, and retrieval payload omission by default;
- size, depth, collection, and retrieval-record limits;
- no hidden reasoning fields in exported payloads;
- trace coverage for `/ask`, agent workflow, legacy RAG, retrieval, prompt rendering, generation,
  decisions, approvals, and evaluation roots.

## CI and Security Corrections

The workflow continues producing reports and artifacts with `if: always()`, but the authoritative
AI quality result also incorporates failed prerequisite jobs. A failed format, lint, validation,
unit, offline-evaluation, or database-integration prerequisite therefore cannot be hidden by a
successful later quality-policy run.

Stable required checks documented for `main` remain:

- `format`
- `lint`
- `unit`
- `integration-db`
- `ai-quality-gate`

`ai-quality-gate` carries prerequisite failures, so `validate` and `offline-eval-smoke` do not need
separate branch-protection entries. `pr-quality-comment` remains informational and non-authoritative.

Write-capable artifact actions are pinned to verified immutable commit SHAs. Repository-level
permissions remain read-only except for the isolated pull-request comment job. The workflow does not
use `pull_request_target`, execute untrusted code with a write token, or expose secrets to forked
pull requests.

Security review also covers committed secrets, unsafe examples, credential logging, payload leakage,
unsafe YAML loading, shell injection, arbitrary paths, unbounded output, caller-selected experiment
variants, and accidental network calls.

## Dependency Review

`uv lock --check` must pass and the lockfile remains unchanged unless a justified dependency edit is
made. Optional RAGAS, DeepEval, LangSmith, Phoenix, and OpenTelemetry imports continue to fail clearly
only when their feature is enabled.

Dependencies are removed only when repository-wide import and command inspection proves they are
unused. In particular, `httpx2` is removed from the development group only if no test, script,
plugin, or documented command depends on it. No broad version upgrades are performed.

## Documentation and Capability Inventory

`docs/phase3/phase3_closeout.md` records Phase 3 objectives, delivered capabilities, architectural
decisions, guarantees, limitations, strict verification setup and command, CI behavior, production
readiness boundaries, deferred work, and recommended Phase 4 direction.

The final reliability report contains one inventory row per Phase 3 capability with:

- implementation location;
- configuration;
- CLI command;
- tests;
- generated reports;
- documentation;
- optional dependencies;
- default enabled or disabled state;
- external-service requirements;
- known limitations.

README, architecture, dataset, development, API, and every Phase 3 guide are reconciled with actual
commands, paths, defaults, CI enforcement, and limitations. Stale statements such as CI policy
enforcement being unimplemented are defects and are corrected.

## Final Report Recommendation Rules

The report recommendation is derived, not manually selected:

- `ready_to_close`: strict mode ran and every required configuration, formatting, lint, test,
  database, evaluation, factuality, observability, API, CI, security, report, and policy check passed.
- `ready_with_documented_limitations`: no critical failure remains, but the run was offline-only or
  a non-critical limitation prevents an unqualified closeout recommendation.
- `not_ready`: any required command, database check, report validation, quality policy, factuality
  invariant, API compatibility guarantee, or security invariant failed.

Skipped optional judge metrics are recorded as skipped and never converted to zero. They do not
block strict closeout when the policy marks them optional.

## Focused Test Strategy

Tests for the final layer cover:

- successful strict verification;
- successful offline-only diagnostics with a capped recommendation;
- failed required command;
- child-command timeout;
- original exit-code propagation;
- missing required report;
- malformed JSON or Markdown report;
- policy failure;
- each critical factuality invariant;
- optional metric skip preservation;
- rejection of live-provider or external-export settings;
- attempted network-client construction;
- concise summary generation;
- Markdown and JSON final report generation;
- dataset fingerprint stability and change detection;
- CI prerequisite failure propagation.

Underlying evaluation, prompt, observability, API, and database behaviors remain covered by their
existing focused suites rather than being duplicated in orchestration tests.

## Completion Evidence

Before completion, the implementation must run fresh:

- `uv lock --check`;
- Ruff formatting and lint checks;
- the full relevant deterministic test suite;
- clean PostgreSQL/pgvector migrations and deterministic ingestion;
- database-backed retrieval, `/ask`, workflow, and evaluation smoke tests;
- every documented offline Phase 3 CLI;
- observability dry-runs and in-memory exporters;
- strict centralized quality policy;
- strict `scripts/verify_phase3.py`;
- validation of both final closeout reports.

The handoff reports exact commands, exit codes, test counts, durations, skipped checks, generated
files, limitations, unresolved risks, milestone recommendation, and a Phase 4 direction. Claims are
based on those fresh results rather than existing committed reports.
