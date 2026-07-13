# GitHub Actions CI Baseline Design

## Goal

Add a production-quality GitHub Actions CI baseline for Phase 3 that validates the repository on
every push and pull request, stays deterministic and offline by default, and still exercises the
real PostgreSQL plus pgvector integration path.

## Scope

In scope:

- A repository CI workflow at `.github/workflows/ci.yml`
- A two-tier job design: fast offline validation plus database-backed integration
- `uv`-based dependency installation and caching
- Offline smoke execution for existing evaluation and validation commands
- Artifact upload for generated reports
- CI documentation in `docs/phase3/github_actions.md`
- README updates that map CI jobs to local reproduction commands

Out of scope:

- Failing builds based on evaluation score thresholds
- PR annotations
- Scheduled workflows
- Deployment or release automation
- Live OpenAI, Gemini, LangSmith, Phoenix, or OTLP connectivity

## Constraints

- Preserve current application behavior
- Preserve `agent_workflow` as the default `/ask` mode
- Preserve `legacy_rag` compatibility
- Keep all CI execution offline with fake embeddings and mock LLMs
- Treat PostgreSQL plus pgvector as required production dependencies
- Use a GitHub Actions service container instead of Docker Compose inside CI
- Cache Python and uv state only; never cache Postgres data
- Keep failures easy to diagnose by separating offline and DB-backed jobs

## Current Repository Signals

The repository already provides the needed building blocks:

- `uv` dependency management via `pyproject.toml` and `uv.lock`
- Ruff lint configuration in `pyproject.toml`
- A broad pytest suite with database-backed tests guarded by `DATABASE_URL`
- Existing offline-safe evaluation CLIs:
  - `packages.evals.run`
  - `packages.evals.run_baseline`
  - `packages.evals.run_prompt_regression`
  - `packages.evals.run_factuality`
  - `packages.evals.run_quality_policy`
  - `packages.evals.run_prompt_experiment`
- Existing config and validation CLIs:
  - `packages.llm.prompt_registry_cli`
  - `packages.observability.cli`
- Existing reports written under `reports/` and `reports/phase3/`

The codebase already encodes the desired runtime behavior:

- `agent_workflow` is the default `/ask` mode
- `legacy_rag` remains supported through `ASK_MODE=legacy_rag`
- factuality, prompt regression, and baseline flows already support offline fake/mock settings
- the quality-policy CLI only becomes a gate when called with strict behavior

## Recommended Approach

Use a single workflow file, `.github/workflows/ci.yml`, with explicit job separation instead of
monolithic steps or reusable sub-workflows.

Why this approach:

- It keeps failure diagnosis straightforward for a baseline CI issue
- It maps cleanly to the repository's existing CLI and pytest surfaces
- It avoids unnecessary indirection while remaining maintainable
- It still allows later extraction into reusable workflows if the repository grows

Rejected alternatives:

- Reusable sub-workflows now: more indirection than value at this stage
- One monolithic job: hides whether failures came from offline validation, DB bootstrap,
  migration, ingestion, retrieval, or evaluation wiring

## Workflow Structure

Create `.github/workflows/ci.yml` with:

- triggers:
  - `push`
  - `pull_request`
  - `workflow_dispatch`
- workflow-level permission:
  - `contents: read`
- workflow-level environment forcing offline-safe defaults:
  - `APP_ENV=ci`
  - `EMBEDDING_PROVIDER=fake`
  - `LLM_PROVIDER=mock`
  - `ASK_MODE=agent_workflow`
  - `PROMPT_EXPERIMENTS_ENABLED=false`
  - `EXPERIMENTOS_LANGSMITH_ENABLED=false`
  - `EXPERIMENTOS_PHOENIX_ENABLED=false`
  - `EXPERIMENTOS_OTEL_ENABLED=false`

Use these jobs:

1. `format`
2. `lint`
3. `validate`
4. `unit`
5. `offline-eval-smoke`
6. `integration-db`
7. `artifacts`

## Job Responsibilities

### `format`

Purpose:

- Validate repository formatting without changing files

Commands:

- install project dependencies needed for formatting
- `uv run ruff format --check .`

Failure semantics:

- Fails on formatting drift only

### `lint`

Purpose:

- Enforce repository lint rules

Commands:

- install project dependencies needed for linting
- `uv run ruff check .`

Failure semantics:

- Fails on Ruff violations only

### `validate`

Purpose:

- Run non-database static and configuration validation already supported by the repository

Coverage:

- prompt registry validation
- prompt experiment definition validation
- observability configuration validation in offline-safe mode
- config-only or schema-only tests that do not need the database

Representative commands:

- `uv run python -m packages.llm.prompt_registry_cli validate`
- `uv run python -m packages.evals.run_prompt_experiment validate --experiment rag-answer-abstention-v1-v2`
- `uv run python -m packages.observability.cli validate --provider all`

Notes:

- This job must not add new validation tools
- It validates existing CLI contracts only

### `unit`

Purpose:

- Run fast deterministic pytest coverage that does not need a live database

Coverage:

- non-database tests
- prompt registry tests
- prompt experiment tests that use offline fixtures
- observability tests that avoid external sinks
- evaluation harness unit tests that rely on stubs and fixtures

Selection strategy:

- Prefer an explicit non-database pytest subset rather than relying on implicit skips across the
  entire suite, so CI logs stay intentional and runtime remains predictable

### `offline-eval-smoke`

Purpose:

- Prove the key offline evaluation and policy commands execute successfully in CI-safe mode

Coverage:

- prompt regression smoke
- factuality smoke
- quality-policy command validation

Execution rules:

- fake embeddings
- mock LLM
- offline mode only
- no judge mode
- outputs written to a CI artifact directory such as `artifacts/ci/offline`

Representative commands:

- `uv run python -m packages.evals.run_prompt_regression --prompt-id rag.answer --baseline-version 1 --candidate-version 1 --offline --embedding-provider fake --llm-provider mock --output ... --json-output ...`
- `uv run python -m packages.evals.run_factuality --target all --mode offline --embedding-provider fake --llm-provider mock --output ... --json-output ...`
- `uv run python -m packages.evals.run_quality_policy --report-dir <offline-report-dir> --warn-only --output ... --json-output ...`

Quality-policy handling:

- Use non-strict behavior so the command is validated without making report status a gate yet

### `integration-db`

Purpose:

- Validate the real database-backed path with clean schema setup, ingestion, retrieval,
  API/service wiring, and lightweight evaluation smoke

Runner and service:

- `runs-on: ubuntu-latest`
- GitHub Actions service container:
  - image: pinned `pgvector/pgvector:pg16`
  - CI-only database name, username, and password
  - service-level health check using `pg_isready`

Environment:

- `DATABASE_URL` points to the service container
- `EMBEDDING_PROVIDER=fake`
- `LLM_PROVIDER=mock`
- `ASK_MODE=agent_workflow`
- all external observability providers disabled

Bootstrap sequence:

1. wait for database readiness with a bounded retry loop
2. run `uv run alembic upgrade head`
3. seed the minimum deterministic dataset from repository-owned synthetic experiments
4. run targeted DB-backed tests
5. run lightweight DB-backed evaluation smoke

Seeding strategy:

- Reuse existing ingestion CLI with existing synthetic experiment folders
- Ingest only the minimum number of experiments required for retrieval, `/ask`, and evaluation
  smoke, likely one or two synthetic experiments rather than the full local corpus
- Never reuse developer-local state

Why not add a CI-only seeder now:

- Existing ingestion behavior is part of what CI should validate
- Reusing repository-owned fixtures reduces divergence

Test scope:

- migration and model tests requiring a live database
- ingestion integration
- retrieval integration
- a small real `/ask` integration slice if current tests are still mostly dependency-overridden
- agent workflow integration that preserves current defaults and fallback compatibility

Evaluation smoke scope:

- `packages.evals.run` with fake/mock providers against the seeded DB
- `packages.evals.run_baseline` with fake/mock providers if runtime stays acceptable
- optional prompt regression smoke only if the seeded dataset is sufficient and runtime remains
  bounded

Non-goals for this job:

- full dataset ingestion
- judge-backed framework metrics
- score threshold enforcement

### `artifacts`

Purpose:

- Upload generated reports even when earlier smoke or integration steps fail

Behavior:

- depends on `offline-eval-smoke` and `integration-db`
- uses `if: ${{ always() }}`
- uploads only files that were generated
- uses `if-no-files-found: warn`

Expected artifact groups:

- offline evaluation smoke reports
- database-backed evaluation reports
- quality policy report outputs
- baseline report outputs

## Setup and Caching

Each job should use:

- `actions/checkout`
- `actions/setup-python` for Python `3.12`
- `astral-sh/setup-uv` with caching enabled

Caching rules:

- cache uv downloads and managed Python state keyed from `uv.lock`
- do not cache Postgres volumes or data directories
- do not cache generated reports

Rationale:

- dependency caching improves runtime without introducing stateful database behavior
- database determinism is more important than saving container startup time

## Timeouts and Diagnostics

Add explicit bounds so CI failures are actionable:

- bounded database readiness wait loop
- step timeouts for integration tests
- step timeouts for DB-backed evaluation smoke

Logging principles:

- keep jobs separated by responsibility
- prefer direct command output rather than wrapper scripts that obscure the failing command
- preserve generated Markdown and JSON reports as downloadable artifacts

## Failure Policy

CI should fail on:

- formatter errors
- lint errors
- validation CLI failures
- migration failures
- ingestion failures
- pytest failures
- runtime failures in offline or DB-backed evaluation commands

CI should not fail yet on:

- evaluation scores
- quality policy report status
- missing judge-backed metrics in offline mode

This preserves the baseline contract:

- the pipeline verifies that commands work
- the pipeline does not yet gate merges on AI quality thresholds

## Documentation Changes

Add `docs/phase3/github_actions.md` covering:

- workflow overview
- job descriptions
- CI environment defaults
- cache strategy
- artifact outputs
- local reproduction commands for offline and DB-backed tiers

Update `README.md` so the development/CI section maps local commands to:

- offline validation tier
- database-backed integration tier
- report generation paths

## Implementation Notes

Prefer small helper conventions inside the workflow rather than new repository scripts unless the
same commands would meaningfully improve local developer workflows too.

If a small DB-backed `/ask` integration test is missing today, add one as part of implementation
instead of overstating the current test coverage.

If `run_baseline` proves too heavy for every PR after measurement, keep it lightweight by reducing
the seeded dataset rather than replacing the DB-backed job with mocks.

## Risks and Mitigations

Risk:

- The current non-database and database-backed pytest boundaries may be blurry

Mitigation:

- Use explicit test target lists in CI rather than broad `pytest` calls

Risk:

- Existing evaluation CLIs may assume a larger seeded corpus than the integration tier provides

Mitigation:

- Seed the smallest dataset that still satisfies the chosen smoke commands, and narrow the smoke
  command scope if needed

Risk:

- Quality-policy CLI can return non-zero when used as a gate

Mitigation:

- Invoke it with non-gating behavior in CI for now

Risk:

- Existing `/ask` tests may not exercise the real DB path

Mitigation:

- Add a dedicated DB-backed integration test during implementation

## Acceptance Mapping

- CI runs on push and PR:
  - covered by workflow triggers
- offline only for AI providers:
  - enforced by fake/mock providers and disabled external observability
- PostgreSQL and pgvector validated:
  - covered by the `integration-db` service container job
- artifacts uploaded:
  - covered by the `artifacts` job
- existing tests pass:
  - covered by explicit offline and DB-backed pytest jobs
- existing evaluations execute:
  - covered by offline smoke plus lightweight DB-backed smoke
- no quality thresholds enforced yet:
  - covered by non-strict quality-policy execution and score-non-gating failure policy

## Implementation Files

Expected primary files to change during implementation:

- `.github/workflows/ci.yml`
- `README.md`
- `docs/phase3/github_actions.md`
- possibly one or more targeted tests if a real DB-backed `/ask` integration slice is missing
