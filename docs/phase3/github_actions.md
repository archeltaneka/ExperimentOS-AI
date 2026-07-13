# GitHub Actions CI Baseline

The Phase 3 CI workflow lives at `.github/workflows/ci.yml` and runs on every `push`,
`pull_request`, and manual `workflow_dispatch`.

It is split into two tiers:

- Fast offline jobs: `format`, `lint`, `validate`, `unit`, `offline-eval-smoke`
- Database-backed job: `integration-db`

Repository-wide CI defaults keep runs deterministic and offline:

- `ASK_MODE=agent_workflow`
- `EMBEDDING_PROVIDER=fake`
- `LLM_PROVIDER=mock`
- prompt experiments disabled by default
- LangSmith, Phoenix, and OTLP export disabled
- `legacy_rag` remains available and is still exercised by database-backed tests and baseline smoke

## Workflow Structure

- `format`: syncs the dev environment and runs `uv run ruff format --check .`
- `lint`: syncs the dev environment and runs `uv run ruff check .`
- `validate`: validates the prompt registry, prompt experiment definition, and observability config
- `unit`: runs deterministic non-database tests, including API, agent workflow, prompt registry, factuality, quality policy, and CI contract coverage
- `offline-eval-smoke`: runs prompt regression, factuality, and quality-policy smoke commands without a database
- `integration-db`: starts `pgvector/pgvector:pg16`, waits for readiness, runs Alembic, seeds a tracked fixture, executes DB-backed tests, and runs the lightweight baseline smoke

## Local Reproduction

The GitHub workflow runs on Ubuntu. The commands below are PowerShell equivalents for reproducing
the same checks locally.

### Common CI Defaults

```powershell
$env:APP_ENV = "ci"
$env:ASK_MODE = "agent_workflow"
$env:EMBEDDING_PROVIDER = "fake"
$env:LLM_PROVIDER = "mock"
$env:PROMPT_EXPERIMENTS_ENABLED = "false"
$env:EXPERIMENTOS_LANGSMITH_ENABLED = "false"
$env:EXPERIMENTOS_PHOENIX_ENABLED = "false"
$env:EXPERIMENTOS_OTEL_ENABLED = "false"
$env:LANGSMITH_TRACING = "false"
$env:LANGSMITH_API_KEY = ""
$env:OPENAI_API_KEY = ""
$env:GOOGLE_API_KEY = ""
```

### Fast Offline Tier

```powershell
uv sync --group dev --frozen
uv run ruff format --check .
uv run ruff check .
uv sync --group dev --group observability --frozen
uv run python -m packages.llm.prompt_registry_cli validate
uv run python -m packages.evals.run_prompt_experiment validate --experiment rag-answer-abstention-v1-v2
uv run python -m packages.observability.cli validate --provider all
uv sync --group dev --group eval --group observability --frozen
uv run pytest tests/test_api_health.py tests/test_api_ask.py tests/test_agent_workflow.py tests/test_prompt_registry.py tests/test_prompt_registry_cli.py tests/test_prompt_experiment_cli.py tests/test_prompt_experiment_validation.py tests/test_observability_cli.py tests/test_prompt_regression.py tests/test_factuality.py tests/test_quality_policy.py tests/test_evaluation_harness.py tests/test_phase3_baseline.py tests/test_github_actions_ci.py -v
New-Item -ItemType Directory -Force -Path artifacts/ci/offline/phase3 | Out-Null
uv run python -m packages.evals.run_prompt_regression --prompt-id rag.answer --baseline-version 1 --candidate-version 1 --offline --dataset data/eval/ci_smoke_dataset.json --embedding-provider fake --llm-provider mock --output artifacts/ci/offline/phase3/prompt_regression.md --json-output artifacts/ci/offline/phase3/prompt_regression.json
uv run python -m packages.evals.run_factuality --dataset data/eval/ci_smoke_dataset.json --agent-dataset data/eval/agent_dataset.json --target agent_workflow --mode offline --embedding-provider fake --llm-provider mock --output artifacts/ci/offline/phase3/factuality_report.md --json-output artifacts/ci/offline/phase3/factuality_report.json
uv run python -m packages.evals.run_quality_policy --report-dir artifacts/ci/offline --warn-only --output artifacts/ci/offline/phase3/quality_policy.md --json-output artifacts/ci/offline/phase3/quality_policy.json
```

### Database-Backed Tier

Use a clean PostgreSQL instance with pgvector. In GitHub Actions this is a service container with
CI-only credentials; locally, the repository's `docker compose up -d postgres` path is the usual
equivalent.

```powershell
docker compose up -d postgres
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv sync --group dev --group eval --group observability --frozen
uv run alembic upgrade head
New-Item -ItemType Directory -Force -Path artifacts/ci/integration/phase3 | Out-Null
uv run python -m packages.ingestion.load_experiment --experiment-dir tests/fixtures/ci/exp-001-payment-recommendation --embedding-provider fake
uv run pytest tests/test_alembic_config.py tests/test_db_models.py tests/test_db_session.py tests/test_ingestion_load_experiment.py tests/test_retrieval_service.py tests/test_api_ask.py tests/test_agent_workflow.py tests/test_api_ask_db_integration.py -v
uv run python -m packages.evals.run_baseline --dataset data/eval/ci_smoke_dataset.json --agent-dataset data/eval/agent_dataset.json --embedding-provider fake --llm-provider mock --rag-output artifacts/ci/integration/evaluation.md --agent-output artifacts/ci/integration/agent_evaluation.md --agent-e2e-output artifacts/ci/integration/agent_e2e_evaluation.md --factuality-output artifacts/ci/integration/phase3/factuality_report.md --factuality-json-output artifacts/ci/integration/phase3/factuality_report.json --quality-policy-output artifacts/ci/integration/phase3/quality_policy.md --quality-policy-json-output artifacts/ci/integration/phase3/quality_policy.json --output artifacts/ci/integration/phase3/baseline_report.md
```

## Cache Summary

- Each job uses `astral-sh/setup-uv` with caching enabled and `uv.lock` as the dependency cache key input.
- Managed Python downloads are cached alongside uv's package cache.
- PostgreSQL data is not cached; `integration-db` always migrates and reseeds a fresh database.

## Artifact Summary

- `offline-eval-smoke` uploads `artifacts/ci/offline`
- `integration-db` uploads `artifacts/ci/integration`

When generated, those artifacts include:

- prompt regression Markdown and JSON
- factuality Markdown and JSON
- quality policy Markdown and JSON
- DB-backed baseline, QA, agent, and `/ask` evaluation reports

Artifact upload steps run with `if: ${{ always() }}` and warn rather than fail when no files are
present, which keeps command failures visible without hiding partial output.
