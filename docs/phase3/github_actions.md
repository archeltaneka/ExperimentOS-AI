# GitHub Actions CI

The Phase 3 CI workflow lives at `.github/workflows/ci.yml` and runs on every
`pull_request`, every push to `main`, and manual `workflow_dispatch`.

Workflow runs now use workflow-level concurrency cancellation:

- group: `${{ github.workflow }}-${{ github.ref }}`
- superseded runs are cancelled with `cancel-in-progress: true`

It is split into three layers:

- Fast offline verification: `format`, `lint`, `validate`, `unit`, `offline-eval-smoke`
- Database-backed verification: `integration-db`
- Database-backed blocking gate: `ai-quality-gate`

Repository-wide CI defaults keep runs deterministic and offline:

- `ASK_MODE=agent_workflow`
- `EMBEDDING_PROVIDER=fake`
- `LLM_PROVIDER=mock`
- `RAGAS_JUDGE_LLM_PROVIDER=none`
- `RAGAS_JUDGE_EMBEDDING_PROVIDER=none`
- `DEEPEVAL_JUDGE_PROVIDER=none`
- prompt experiments disabled by default
- LangSmith, Phoenix, and OTLP export disabled
- Python hashing fixed with `PYTHONHASHSEED=0`
- `legacy_rag` remains available and is still exercised by database-backed tests and baseline smoke

## Workflow Structure

- `format`: syncs the dev environment and runs `uv run ruff format --check .`
- `lint`: syncs the dev environment and runs `uv run ruff check .`
- `validate`: validates the prompt registry, prompt experiment definition, and observability config
- `unit`: runs deterministic non-database tests, including API, agent workflow, prompt registry, factuality, quality policy, and CI contract coverage
- `offline-eval-smoke`: runs prompt regression, factuality, and quality-policy smoke commands without a database
- `integration-db`: starts `pgvector/pgvector:pg16`, waits for readiness, runs Alembic, seeds a tracked fixture, executes DB-backed tests, and runs the lightweight baseline smoke
- `ai-quality-gate`: starts its own `pgvector/pgvector:pg16` service, validates the CI environment, seeds the tracked fixture, runs the required deterministic evaluation suites, enforces the centralized quality policy, writes a GitHub job summary, and always uploads artifacts

## Local Reproduction

The GitHub workflow runs on Ubuntu. The commands below are PowerShell equivalents for reproducing
the same checks locally.

### Common CI Defaults

```powershell
$env:APP_ENV = "ci"
$env:ASK_MODE = "agent_workflow"
$env:EMBEDDING_PROVIDER = "fake"
$env:LLM_PROVIDER = "mock"
$env:RAGAS_JUDGE_LLM_PROVIDER = "none"
$env:RAGAS_JUDGE_EMBEDDING_PROVIDER = "none"
$env:DEEPEVAL_JUDGE_PROVIDER = "none"
$env:PROMPT_EXPERIMENTS_ENABLED = "false"
$env:EXPERIMENTOS_LANGSMITH_ENABLED = "false"
$env:EXPERIMENTOS_PHOENIX_ENABLED = "false"
$env:EXPERIMENTOS_OTEL_ENABLED = "false"
$env:EXPERIMENTOS_OTEL_EXPORTER_TYPE = "none"
$env:LANGSMITH_TRACING = "false"
$env:LANGSMITH_API_KEY = ""
$env:OPENAI_API_KEY = ""
$env:GOOGLE_API_KEY = ""
$env:PYTHONHASHSEED = "0"
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

### AI Quality Gate

This is the local equivalent of the blocking CI job.

```powershell
docker compose up -d postgres
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv sync --group dev --group eval --group observability --frozen
uv run alembic upgrade head
New-Item -ItemType Directory -Force -Path artifacts/ci/ai-quality/phase3 | Out-Null
uv run python scripts/validate_ci_environment.py --output artifacts/ci/ai-quality/phase3/ci_environment.json
uv run python scripts/run_ai_quality_gate.py --artifact-root artifacts/ci/ai-quality --artifact-name ai-quality-gate-local --policy-changed false
Get-Content artifacts/ci/ai-quality/phase3/github_summary.md
```

The gate runs these suites in order:

- prompt registry validation
- prompt experiment definition validation
- custom RAG evaluation
- custom agent workflow evaluation
- `/ask` end-to-end evaluation
- prompt regression
- factuality evaluation
- offline prompt experiment sample
- offline-safe RAGAS evaluation
- offline DeepEval evaluation
- centralized quality policy enforcement

## Cache Summary

- Each job uses `astral-sh/setup-uv` with caching enabled and `uv.lock` as the dependency cache key input.
- Managed Python downloads are cached alongside uv's package cache.
- PostgreSQL data is not cached; `integration-db` always migrates and reseeds a fresh database.

## Artifact Summary

- `offline-eval-smoke` uploads `artifacts/ci/offline`
- `integration-db` uploads `artifacts/ci/integration`
- `ai-quality-gate` uploads `artifacts/ci/ai-quality`

When generated, those artifacts include:

- prompt regression Markdown and JSON
- factuality Markdown and JSON
- RAGAS Markdown and JSON
- DeepEval Markdown and JSON
- quality policy Markdown and JSON
- DB-backed QA, agent, and `/ask` evaluation reports in Markdown and JSON
- prompt experiment Markdown and JSON
- CI environment fingerprint, artifact manifest, gate result JSON, and GitHub summary Markdown

Artifact upload steps run with `if: ${{ always() }}` and warn rather than fail when no files are
present, which keeps command failures visible without hiding partial output.

## Job Summary

`ai-quality-gate` appends a concise Markdown summary to `$GITHUB_STEP_SUMMARY` with:

- overall quality status
- policy version
- category status breakdown
- critical violations
- warning-only deviations
- skipped optional metrics
- artifact bundle name
- whether external judges were used
- whether live providers were configured
- whether the quality policy file changed in the current revision
