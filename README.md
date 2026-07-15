# ExperimentOS AI

> Turn experiment artifacts into searchable evidence, grounded answers, and repeatable evaluations.

ExperimentOS AI is an early-stage Python 3.12 backend for loading experiment reports into Postgres, retrieving relevant evidence with pgvector, and answering questions with traceable citations. The repository is designed for deterministic local development, synthetic experimentation data, and evaluation workflows that can run without live model APIs.

## Hero

Experiment teams accumulate analysis across Markdown reports, CSV exports, event logs, and follow-up notes. ExperimentOS AI turns that raw material into a developer-friendly backend surface for ingestion, retrieval, grounded QA, and offline evaluation.

## Motivation

Most experiment knowledge decays because the original evidence is hard to recover. Teams remember the decision, but not the exact metric movement, caveats, rollout constraints, or report sections that justified it.

ExperimentOS AI exists to make that evidence queryable:

- Load experiment artifacts into a local database.
- Index report chunks for semantic retrieval.
- Answer questions against experiment-specific context.
- Evaluate retrieval and QA quality against a fixed dataset.
- Keep local workflows deterministic with fake embeddings and mock LLMs when needed.

## Architecture Overview

The current repository is organized around a small set of backend workflows:

- `packages/ingestion/` parses synthetic experiment folders and stores reports, metrics, and chunks.
- `packages/db/` defines SQLAlchemy models, async sessions, and Alembic metadata.
- `packages/retrieval/` performs semantic search over pgvector-backed chunk embeddings.
- `packages/qa/` turns retrieved chunks into grounded answers with citations.
- `packages/agents/` contains the Phase 2 LangGraph decision workflow that now powers `POST /ask` by default.
- `apps/api/` exposes `GET /health` and `POST /ask`.
- `packages/evals/` runs the offline QA harness and the integrated `/ask` agent E2E harness.

### Architecture Diagram

```mermaid
flowchart LR
    A[data/synthetic/experiments/*] --> B[Ingestion CLI]
    A1[metadata.json] --> B
    A2[metrics.csv] --> B
    A3[report.md] --> B
    A4[events.csv<br/>generated, not ingested yet] -.-> B

    B --> C[(Postgres 16 + pgvector)]
    B --> D[Embedding provider]

    C --> E[Retrieval service]
    D --> E
    E --> F[Question answering service]
    F --> G[LLM provider]

    H[FastAPI app] --> I[GET /health]
    H --> J[POST /ask]
    J --> O[Ask service adapter]
    O --> P[Agent workflow service]
    O -. legacy_rag .-> F
    P --> Q[LangGraph workflow]

    E --> K[Retrieval CLI]
    L[data/eval/qa_dataset.json] --> M[Offline evaluator]
    F --> M
    M --> N[reports/evaluation.md]
```

See [Architecture](docs/architecture.md) for component boundaries and data flow details.

Phase 2 is now complete at the API validation layer: `/ask` defaults to the LangGraph
workflow, and the repository includes both workflow-state evaluation and integrated `/ask`
E2E evaluation coverage.

## Features

| Area | Status | Notes |
| --- | --- | --- |
| FastAPI API | Available | `GET /health` and `POST /ask` are implemented. |
| Experiment ingestion | Available | Loads `metadata.json`, `metrics.csv`, and `report.md`. |
| pgvector retrieval | Available | Semantic search via CLI and shared service layer. |
| Grounded QA | Available | `legacy_rag` mode preserves the original retrieval plus LLM answer path. |
| Offline evaluation | Available | Runs the Phase 1 QA dataset and produces a Markdown report. |
| Optional RAGAS evaluation | Available | Adds framework-backed retrieval and answer-quality scoring without replacing the custom evaluator. |
| Agent E2E evaluation | Available | Validates the integrated `/ask` contract, routing, trace, metrics, citations, approval, and fallback behavior. |
| Deterministic local runs | Available | Fake embeddings and mock LLMs support offline workflows. |
| Synthetic dataset | Available | Ten synthetic experiments plus a QA evaluation dataset. |
| Event ingestion | Planned | `events.csv` is generated today but not ingested yet. |
| Agent workflows | Available | `POST /ask` defaults to the Phase 2 LangGraph workflow; set `ASK_MODE=legacy_rag` to restore the Phase 1 QA path. |

## Repository Structure

```text
apps/
  api/                      FastAPI application entry point and dependency wiring
data/
  eval/                     Offline QA evaluation dataset
  synthetic/experiments/    Generated synthetic experiment corpus
docs/
  architecture.md           System architecture and boundaries
  api.md                    API contract documentation
  dataset.md                Synthetic dataset reference
  development.md            Local development and workflow guide
  assets/screenshots/       Placeholder screenshot assets
migrations/                 Alembic migration scripts
packages/
  agents/                   Phase 2 LangGraph workflow and agent modules
  config/                   Environment loading
  db/                       SQLAlchemy models and async session helpers
  evals/                    Offline evaluation harness and report generation
  experiments/              Future experiment domain package boundary
  ingestion/                Experiment loading, chunking, and embeddings
  llm/                      LLM client abstractions and providers
  qa/                       Grounded question answering service
  retrieval/                Semantic retrieval CLI and service
reports/                    Curated baseline/reference artifacts versioned in git
scripts/                    Utility scripts including synthetic data generation
tests/                      Unit, API, migration, and integration tests
```

## Repository Output Policy

Use `artifacts/local/...` for routine local verification output.
Use `reports/` only when intentionally refreshing curated baseline/reference artifacts that belong
in git.

## Quick Start

Prerequisites:

- Python `3.12`
- `uv`
- Docker with Compose support

From the repository root:

```powershell
uv sync
Copy-Item .env.example .env
docker compose up -d postgres
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run alembic upgrade head
uv run python scripts/generate_synthetic_experiments.py
uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-001-payment-recommendation --embedding-provider fake
uv run uvicorn apps.api.main:app --reload
```

In another PowerShell session:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/health"
```

`/ask` now defaults to the Phase 2 agent workflow. To switch back to the original grounded QA path:

```powershell
$env:ASK_MODE = "legacy_rag"
```

## API Example

`/ask` requires the database UUID of an ingested experiment, not the synthetic folder ID. After ingesting data, list experiment IDs with:

```powershell
docker compose exec postgres psql -U experimentos -d experimentos -c "select id, name, config->>'experiment_id' as synthetic_experiment_id from experiments order by name;"
```

Then call the API:

```powershell
$body = @{
    question = "Why was the adaptive payment method recommendation approved for rollout?"
    experiment_id = "00000000-0000-0000-0000-000000000000"
    top_k = 3
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri "http://127.0.0.1:8000/ask" `
    -ContentType "application/json" `
    -Body $body
```

The response always returns the original core fields:

- `answer`
- `citations`
- `retrieved_chunks`
- `retrieval_metrics`
- `llm_metrics`

In default `agent_workflow` mode it can also return:

- `intent`
- `required_agents`
- `decision`
- `executive_summary`
- `agent_trace`
- `agent_metrics`
- `approval_status`

Full request and response documentation lives in [API Reference](docs/api.md).

## Evaluation Example

Run the offline evaluation harness with deterministic local providers:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run python -m packages.evals.run --embedding-provider fake --llm-provider mock --output artifacts/local/evaluation.md --json-output artifacts/local/evaluation.json
Get-Content artifacts/local/evaluation.md
```

Enable the optional RAGAS integration and run the offline-safe report:

```powershell
uv sync --group eval
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run python -m packages.evals.run_ragas --embedding-provider fake --llm-provider mock --output artifacts/local/phase3/ragas_report.md --json-output artifacts/local/phase3/ragas_report.json
Get-Content artifacts/local/phase3/ragas_report.md
```

By default this RAGAS path computes offline-safe ID-based context precision and recall from the
repository dataset. Judge-backed metrics such as `faithfulness`, `context_precision`,
`context_recall`, and `answer_relevancy` are opt-in and are skipped unless you configure a judge
LLM and, for `answer_relevancy`, judge embeddings.

See [Dataset Guide](docs/dataset.md) and [Development Guide](docs/development.md) for dataset setup and workflow details.

Run the integrated `/ask` E2E evaluation:

```powershell
uv run python -m packages.evals.run_agent_e2e --output artifacts/local/agent_e2e_evaluation.md
Get-Content artifacts/local/agent_e2e_evaluation.md
```

Run the Phase 3 reliability baseline without external LLMOps tooling:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run python -m packages.evals.run_baseline --embedding-provider fake --llm-provider mock --output reports/phase3/baseline_report.md
Get-Content reports/phase3/baseline_report.md
```

This baseline coordinates the existing repository-local QA, agent workflow, and `/ask` E2E
evaluations. The baseline remains deterministic and repository-owned; optional RAGAS reporting and
optional LangSmith, Phoenix, and OpenTelemetry sinks now live beside it rather than replacing it.
All are disabled by default, and ExperimentOS-owned traces and reports remain authoritative. See
[Phase 3 Reliability Baseline](docs/phase3/reliability_baseline.md) and
[Phase 3 Closeout](docs/phase3/phase3_closeout.md).

Run prompt regression for a prompt-backed surface:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run python -m packages.evals.run_prompt_regression --prompt-id rag.answer --baseline-version 1 --candidate-version 1 --offline --embedding-provider fake --llm-provider mock --output artifacts/local/phase3/prompt_regression.md --json-output artifacts/local/phase3/prompt_regression.json
Get-Content artifacts/local/phase3/prompt_regression.md
```

This command reuses the existing `legacy_rag` QA dataset, freezes retrieval between compared prompt
versions, and layers offline-safe custom, RAGAS, and DeepEval comparisons on top of the same local
surfaces. See [Phase 3 Prompt Regression](docs/phase3/prompt_regression.md).

Run the offline prompt experiment workflow:

```powershell
uv run python -m packages.evals.run_prompt_experiment validate --experiment rag-answer-abstention-v1-v2
uv run python -m packages.evals.run_prompt_experiment run --experiment rag-answer-abstention-v1-v2 --mode offline --report-dir artifacts/local/phase3/prompt_experiments
Get-Content artifacts/local/phase3/prompt_experiments/rag-answer-abstention-v1-v2.md
```

This workflow keeps runtime experimentation disabled by default, reuses the immutable prompt
registry, and writes local Markdown and JSON artifacts without using production traffic. See
[Phase 3 Prompt Experiments](docs/phase3/prompt_experiments.md).

Run the strict Phase 3 closeout after starting PostgreSQL and setting `DATABASE_URL`:

```powershell
uv run python scripts/verify_phase3.py
```

Without PostgreSQL, `uv run python scripts/verify_phase3.py --offline-only` runs an explicitly
non-closeout diagnostic and can never recommend `ready_to_close`. See
[Phase 3 Closeout](docs/phase3/phase3_closeout.md) for setup, guarantees, and boundaries.

## Development Workflow

Core commands:

```powershell
uv sync
uv run ruff check .
uv run pytest
```

## CI Parity

The GitHub Actions baseline is defined in `.github/workflows/ci.yml`. It runs fully offline with
`ASK_MODE=agent_workflow`, fake embeddings, mock LLMs, prompt experiments disabled by default, and
external observability sinks turned off. `legacy_rag` remains supported and is still covered by the
database-backed tier.

Fast offline parity:

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
uv sync --group dev --frozen
uv run ruff format --check .
uv run ruff check .
uv sync --group dev --group observability --frozen
uv run python -m packages.llm.prompt_registry_cli validate
uv run python -m packages.evals.run_prompt_experiment validate --experiment rag-answer-abstention-v1-v2
uv run python -m packages.observability.cli validate --provider all
uv sync --group dev --group eval --group observability --frozen
uv run pytest tests/test_api_health.py tests/test_api_ask.py tests/test_agent_workflow.py tests/test_prompt_registry.py tests/test_prompt_registry_cli.py tests/test_prompt_experiment_cli.py tests/test_prompt_experiment_validation.py tests/test_observability_cli.py tests/test_prompt_regression.py tests/test_factuality.py tests/test_quality_policy.py tests/test_ci_quality_gate.py tests/test_evaluation_harness.py tests/test_ragas_evaluation.py tests/test_phase3_baseline.py tests/test_github_actions_ci.py tests/test_repository_hygiene.py -v
New-Item -ItemType Directory -Force -Path artifacts/ci/offline/phase3 | Out-Null
uv run python -m packages.evals.run_prompt_regression --prompt-id rag.answer --baseline-version 1 --candidate-version 1 --offline --dataset data/eval/ci_smoke_dataset.json --embedding-provider fake --llm-provider mock --output artifacts/ci/offline/phase3/prompt_regression.md --json-output artifacts/ci/offline/phase3/prompt_regression.json
uv run python -m packages.evals.run_factuality --dataset data/eval/ci_smoke_dataset.json --agent-dataset data/eval/agent_dataset.json --target agent_workflow --mode offline --embedding-provider fake --llm-provider mock --output artifacts/ci/offline/phase3/factuality_report.md --json-output artifacts/ci/offline/phase3/factuality_report.json
uv run python -m packages.evals.run_quality_policy --report-dir artifacts/ci/offline --warn-only --output artifacts/ci/offline/phase3/quality_policy.md --json-output artifacts/ci/offline/phase3/quality_policy.json
```

Database-backed parity:

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

See [GitHub Actions CI Baseline](docs/phase3/github_actions.md) for the job-by-job breakdown,
cache summary, and artifact outputs.

Database-backed path:

```powershell
docker compose up -d postgres
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run alembic upgrade head
uv run pytest tests/test_db_models.py tests/test_ingestion_load_experiment.py tests/test_retrieval_service.py
```

Focused guides:

- [Development](docs/development.md)
- [Architecture](docs/architecture.md)
- [API Reference](docs/api.md)
- [Dataset Guide](docs/dataset.md)

## Screenshots

Current repository assets are placeholders rather than captured UI screenshots:

![Health Endpoint Placeholder](docs/assets/screenshots/api-health-placeholder.svg)
![Ask Endpoint Placeholder](docs/assets/screenshots/ask-endpoint-placeholder.svg)
![Evaluation Report Placeholder](docs/assets/screenshots/evaluation-report-placeholder.svg)
![Retrieval CLI Placeholder](docs/assets/screenshots/retrieval-cli-placeholder.svg)

## Roadmap

| Milestone | Direction |
| --- | --- |
| Retrieval quality | Improve ranking, filtering, and metadata-aware search. |
| Dataset depth | Expand evaluation coverage and retrieval regression checks. |
| Deployment validation | Add load, soak, and operational readiness checks for a real target environment. |
| Event support | Ingest `events.csv` into the experiment knowledge model. |
| Operational reliability | Add deployment-specific alerting and runbooks without weakening repository-owned policy. |

## Future Work

- Add real screenshots once the API flows and generated reports stabilize.
- Publish deployment guidance for containerized or hosted environments.
- Add richer experiment entities for variants, segments, and event-level evidence.
- Expose retrieval and QA flows through a user-facing frontend.
- Expand evaluation scoring beyond retrieval success and citation coverage.

## License

This project is licensed under the terms of the [LICENSE](LICENSE).
# Pull Request AI Quality Reports

Pull requests receive a concise AI quality summary in the GitHub job summary and, when permissions
allow, one updateable PR comment. The `ai-quality-gate` check controls merge eligibility; full
structured and Markdown reports are always available as CI artifacts.
