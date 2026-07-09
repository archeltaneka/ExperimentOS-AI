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

Default runtime mode: `agent_workflow`

Set `ASK_MODE=legacy_rag` to switch back to the original Phase 1 grounded QA path.

Current default path:

```text
POST /ask -> AskService -> AgentWorkflowService -> LangGraph workflow
```

Fallback path:

```text
POST /ask -> AskService -> QuestionAnsweringService -> RetrievalService -> LLM client
```

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

Successful responses always return:

| Field | Type | Description |
| --- | --- | --- |
| `answer` | string | Final answer text from the selected `/ask` mode |
| `citations` | array | Citation objects derived from workflow evidence or retrieved chunks |
| `retrieved_chunks` | array | Full retrieved chunk objects returned by the retrieval layer |
| `retrieval_metrics` | object | Retrieval latency and relevance summary |
| `llm_metrics` | object | LLM model, token counts, and latency. In `agent_workflow` mode this is a deterministic compatibility object. |

Agent workflow responses can also include:

| Field | Type | Description |
| --- | --- | --- |
| `intent` | string or null | Planner intent selected for the request |
| `required_agents` | array | Agents selected by the planner |
| `decision` | object or null | Structured decision artifact when produced |
| `executive_summary` | object or null | Structured executive summary artifact when produced |
| `agent_trace` | array | Structured per-node workflow trace entries |
| `agent_metrics` | object | Structured workflow metrics by node |
| `approval_status` | string or null | Human approval status when applicable |

Example response:

```json
{
  "answer": "Rollout is supported by the current evidence.",
  "citations": [
    {
      "experiment_id": "00000000-0000-0000-0000-000000000000",
      "quote": "Primary metric improved by 8.9% in treatment.",
      "section": "Results",
      "metadata": {
        "section": "Results",
        "document_name": "Launch Report"
      }
    }
  ],
  "retrieved_chunks": [
    {
      "experiment_id": "00000000-0000-0000-0000-000000000000",
      "metadata": {
        "section": "Decision"
      },
      "experiment_name": "Adaptive Payment Method Recommendation",
      "document_id": "doc-123",
      "document_name": "Launch Report",
      "chunk_text": "Primary metric improved by 8.9% in treatment.",
      "similarity": 0.91
    }
  ],
  "retrieval_metrics": {
    "embedding_time_ms": 10.0,
    "vector_search_time_ms": 8.0,
    "retrieved_chunks": 1,
    "average_similarity": 0.91
  },
  "llm_metrics": {
    "model": "agent-workflow",
    "input_tokens": 0,
    "output_tokens": 0,
    "latency_ms": 0.0
  },
  "intent": "decision_support",
  "required_agents": [
    "retrieval",
    "experiment_analysis",
    "business_impact",
    "risk_assessment",
    "decision",
    "human_approval",
    "executive_summary"
  ],
  "decision": {
    "decision_status": "decided",
    "recommendation": "rollout",
    "confidence": "medium",
    "rationale": "Positive lift outweighed manageable rollout risk."
  },
  "executive_summary": {
    "summary_status": "generated",
    "summary": "Rollout is supported by the current evidence."
  },
  "agent_trace": [
    {
      "node": "planner",
      "event": "planned",
      "at": "2026-07-09T00:00:00Z"
    }
  ],
  "agent_metrics": {
    "planner_rule_version": "deterministic_v1",
    "decision": {
      "status": "decided"
    }
  },
  "approval_status": "pending"
}
```

### Error Behavior

| Status | When it happens | Detail source |
| --- | --- | --- |
| `422` | Request validation fails, such as whitespace-only `question` | Pydantic validation |
| `404` | The experiment UUID is unknown | `UnknownExperimentError` |
| `502` | Embedding generation or retrieval fails | `EmbeddingFailureError` |
| `502` | LLM generation fails | `LLMGenerationError` |

If the experiment exists but the workflow cannot produce a richer answer, `/ask` still returns `200` with the best available answer content. In the empty-evidence case this falls back to the same insufficient-evidence answer used by the legacy QA path.

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

## Agent E2E Evaluation

Phase 2 `/ask` validation now has a deterministic API-level E2E harness in addition to the
workflow-state harness from `packages.evals.run_agent`.

Run it with:

```powershell
uv run python -m packages.evals.run_agent_e2e --output reports/agent_e2e_evaluation.md
Get-Content reports/agent_e2e_evaluation.md
```

The generated report summarizes:

- default `agent_workflow` coverage
- `legacy_rag` fallback coverage
- intent and routing accuracy
- citation, decision, executive summary, and approval coverage
- average request latency
