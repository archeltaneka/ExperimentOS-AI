# API Reference

ExperimentOS AI currently exposes a minimal FastAPI surface:

- `GET /health`
- `POST /ask`

Base URL during local development:

```text
http://127.0.0.1:8000
```

## `GET /health`

Health check endpoint for local verification.

Request:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/health"
```

Example response:

```json
{
  "status": "ok",
  "service": "experimentos-api"
}
```

## `POST /ask`

Answer a question against a single ingested experiment.

### Request Body

| Field | Type | Required | Constraints | Notes |
| --- | --- | --- | --- | --- |
| `question` | string | Yes | minimum length `1`, must not be whitespace-only | The natural-language question to answer |
| `experiment_id` | string | Yes | minimum length `1` | Must be a database UUID for an ingested experiment |
| `top_k` | integer | No | default `5`, range `1..20` | Number of chunks to retrieve |

### Important Identifier Note

The API uses the database UUID in the `experiments.id` column, not the synthetic folder ID such as `exp-001-payment-recommendation`.

List the current mappings:

```powershell
docker compose exec postgres psql -U experimentos -d experimentos -c "select id, name, config->>'experiment_id' as synthetic_experiment_id from experiments order by name;"
```

### Example Request

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

### Response Shape

Successful responses return:

| Field | Type | Description |
| --- | --- | --- |
| `answer` | string | Final answer text from the QA service |
| `citations` | array | Compact citation objects derived from retrieved chunks |
| `retrieved_chunks` | array | Full retrieved chunk objects returned by the retrieval layer |
| `retrieval_metrics` | object | Retrieval latency and relevance summary |
| `llm_metrics` | object | LLM model, token counts, and latency |

Example response:

```json
{
  "answer": "The launch passed guardrails.",
  "citations": [
    {
      "experiment_id": "exp-123",
      "document": "Launch Report",
      "similarity": 0.91
    }
  ],
  "retrieved_chunks": [
    {
      "experiment_id": "exp-123",
      "metadata": {
        "section": "Decision"
      },
      "experiment_name": "Payment Recommendation Launch",
      "document_id": "doc-123",
      "document_name": "Launch Report",
      "chunk_text": "The launch passed guardrails.",
      "similarity": 0.91
    }
  ],
  "retrieval_metrics": {
    "embedding_time_ms": 3.0,
    "vector_search_time_ms": 5.0,
    "retrieved_chunks": 1,
    "average_similarity": 0.91
  },
  "llm_metrics": {
    "model": "mock-answerer",
    "input_tokens": 42,
    "output_tokens": 5,
    "latency_ms": 1.5
  }
}
```

### Error Behavior

| Status | When it happens | Detail source |
| --- | --- | --- |
| `422` | Request validation fails, such as whitespace-only `question` | Pydantic validation |
| `404` | The experiment UUID is unknown | `UnknownExperimentError` |
| `502` | Embedding generation or retrieval fails | `EmbeddingFailureError` |
| `502` | LLM generation fails | `LLMGenerationError` |

Example validation failure:

```powershell
$body = @{
    question = "   "
    experiment_id = "00000000-0000-0000-0000-000000000000"
} | ConvertTo-Json

Invoke-WebRequest `
    -Method Post `
    -Uri "http://127.0.0.1:8000/ask" `
    -ContentType "application/json" `
    -Body $body
```

## Local End-To-End Example

1. Start Postgres and apply migrations.
2. Generate and ingest at least one synthetic experiment.
3. Look up the database UUID.
4. Start the FastAPI app.
5. Call `/ask`.

Commands:

```powershell
uv sync
Copy-Item .env.example .env
docker compose up -d postgres
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run alembic upgrade head
uv run python scripts/generate_synthetic_experiments.py
uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-001-payment-recommendation --embedding-provider fake
docker compose exec postgres psql -U experimentos -d experimentos -c "select id, name, config->>'experiment_id' as synthetic_experiment_id from experiments order by name;"
uv run uvicorn apps.api.main:app --reload
```
