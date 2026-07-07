# Development Guide

This guide covers local setup and the main developer workflows for ExperimentOS AI. All commands below are written for PowerShell and assume you are running them from the repository root.

## Local Development

Prerequisites:

- Python `3.12`
- `uv`
- Docker with Compose support

Initial setup:

```powershell
uv sync
Copy-Item .env.example .env
docker compose up -d postgres
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run alembic upgrade head
```

Run the API:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run uvicorn apps.api.main:app --reload
```

Check the service:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/health"
```

## Migrations

Alembic is configured through `alembic.ini` and the `migrations/` directory.

Apply the current schema:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run alembic upgrade head
```

After model changes, create a migration and then re-apply:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run alembic revision --autogenerate -m "describe-change"
uv run alembic upgrade head
```

Recommended migration verification:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run pytest tests/test_alembic_config.py tests/test_db_models.py
```

## Ingestion Workflow

Generate the synthetic corpus:

```powershell
uv run python scripts/generate_synthetic_experiments.py
```

Important:

- The generator deletes and recreates `data/synthetic/experiments`.
- Do not run it if you need to preserve local, uncommitted synthetic data.

Ingest a single experiment with deterministic embeddings:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-001-payment-recommendation --embedding-provider fake
```

Ingest without storing embeddings:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-001-payment-recommendation --skip-embeddings
```

What is currently ingested:

- `metadata.json`
- `metrics.csv`
- `report.md`

What is not yet ingested:

- `events.csv`

## Retrieval Workflow

Search across all ingested experiments:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run python -m packages.retrieval.search --query "wallet telemetry rollout decision" --embedding-provider fake --top-k 3
```

Search within one experiment UUID:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run python -m packages.retrieval.search --query "wallet telemetry rollout decision" --experiment-id 00000000-0000-0000-0000-000000000000 --embedding-provider fake --top-k 3
```

Search with metadata filters:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run python -m packages.retrieval.search --query "decision summary" --embedding-provider fake --metadata section=Decision --top-k 3
```

List experiment UUIDs mapped to synthetic IDs:

```powershell
docker compose exec postgres psql -U experimentos -d experimentos -c "select id, name, config->>'experiment_id' as synthetic_experiment_id from experiments order by name;"
```

## Evaluation Workflow

The evaluation harness reads `data/eval/qa_dataset.json`, maps synthetic experiment IDs to database UUIDs, answers each question through the QA service, and writes a Markdown report.

Run the default local evaluation:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run python -m packages.evals.run --embedding-provider fake --llm-provider mock --output reports/evaluation.md
```

Read the generated report:

```powershell
Get-Content reports/evaluation.md
```

Customize the run:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run python -m packages.evals.run --dataset data/eval/qa_dataset.json --output reports/evaluation.md --top-k 5 --embedding-provider fake --llm-provider mock
```

## Provider Choices

For deterministic local work, prefer:

- `--embedding-provider fake`
- `--llm-provider mock`

Current embedding provider choices:

- `auto`
- `fake`
- `openai`
- `gemini`
- `huggingface`
- `ollama`

Current evaluation LLM provider choices:

- `mock`
- `openai`
- `gemini`
- `ollama`

Current API LLM behavior:

- `LLM_PROVIDER=mock` forces the mock client.
- `LLM_PROVIDER=gemini` requires `GEMINI_API_KEY`.
- `LLM_PROVIDER=openai` uses the OpenAI client.
- `LLM_PROVIDER=auto` prefers Gemini when `GEMINI_API_KEY` is set, otherwise OpenAI when `OPENAI_API_KEY` is set, otherwise mock.

## Linting And Tests

Run lint:

```powershell
uv run ruff check .
```

Run all tests:

```powershell
uv run pytest
```

Run non-database tests only:

```powershell
uv run pytest tests/test_api_health.py tests/test_db_session.py tests/test_alembic_config.py tests/test_document_chunking.py tests/test_package_imports.py tests/test_synthetic_experiment_dataset.py tests/test_evaluation_harness.py
```

Run the main database-backed path:

```powershell
docker compose up -d postgres
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run alembic upgrade head
uv run pytest tests/test_db_models.py tests/test_ingestion_load_experiment.py tests/test_retrieval_service.py
```
