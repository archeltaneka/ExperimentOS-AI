# ExperimentOS AI

ExperimentOS AI is starting as a Python backend workspace. Issue #1 sets up the project skeleton, uv dependency management, a minimal FastAPI API app, package boundaries, tests, and data directories.

## Local Setup

```bash
uv sync
copy .env.example .env
docker compose up -d postgres
uv run uvicorn apps.api.main:app --reload
```

## Local Database

The local database runs Postgres with pgvector through Docker Compose.

```bash
docker compose up -d postgres
docker compose ps
```

The database URL in `.env.example` matches the Compose credentials:
`postgresql+psycopg://experimentos:experimentos@localhost:5432/experimentos`.

When migrations are introduced in a future issue, enable pgvector with:

```sql
CREATE EXTENSION vector;
```

## Project Layout

```text
apps/api/              FastAPI application
packages/ingestion/   ingestion package boundary
packages/retrieval/   retrieval package boundary
packages/experiments/ experiment domain package boundary
packages/agents/      future agent package boundary
packages/evals/       evaluation package boundary
data/raw/             raw input data
data/processed/       processed data artifacts
data/synthetic/       synthetic fixtures
tests/                automated tests
```

Health check: `GET http://127.0.0.1:8000/health`

## Test

```bash
uv run ruff check .
uv run pytest
```
