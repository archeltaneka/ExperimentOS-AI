# Task 2 Report

## What I implemented

- Added [`apps/api/ask_service.py`](/C:/Users/Archel/Documents/Personal%20Projects/ExperimentOS-AI/apps/api/ask_service.py) with:
  - `AskRequest`
  - unified `AskResponse`
  - `AskService` protocol
  - `LegacyRagAskService`
  - `AgentWorkflowAskService`
  - `get_ask_mode()`
  - `map_agent_state_to_ask_response()`
  - `AgentWorkflowExecutionError`
- Updated [`apps/api/main.py`](/C:/Users/Archel/Documents/Personal%20Projects/ExperimentOS-AI/apps/api/main.py) so `POST /ask` depends on `get_ask_service()` and returns the unified `AskResponse`.
- Split `/ask` endpoint coverage into a dedicated [`tests/test_api_ask.py`](/C:/Users/Archel/Documents/Personal%20Projects/ExperimentOS-AI/tests/test_api_ask.py).
- Trimmed [`tests/test_api_health.py`](/C:/Users/Archel/Documents/Personal%20Projects/ExperimentOS-AI/tests/test_api_health.py) back to health/config helper coverage.

## What I tested and results

- `uv run pytest tests/test_api_health.py tests/test_api_ask.py -v`
  - Result: passed
  - Summary: `11 passed in 1.47s`
- `uv run ruff check .`
  - Result: passed
  - Summary: `All checks passed!`

## TDD evidence

### RED

Command:

```powershell
uv run pytest tests/test_api_health.py tests/test_api_ask.py -v
```

Relevant output:

```text
ERROR tests/test_api_ask.py
ModuleNotFoundError: No module named 'apps.api.ask_service'
```

### GREEN

Command:

```powershell
uv run pytest tests/test_api_health.py tests/test_api_ask.py -v
```

Relevant output:

```text
tests/test_api_health.py::test_health_endpoint_returns_ok PASSED
tests/test_api_health.py::test_embedding_provider_name_uses_dotenv PASSED
tests/test_api_health.py::test_llm_client_auto_prefers_gemini_when_api_key_is_set PASSED
tests/test_api_health.py::test_llm_client_loads_dotenv_for_gemini_auto_provider PASSED
tests/test_api_health.py::test_llm_client_uses_ollama_provider_from_dotenv PASSED
tests/test_api_ask.py::test_ask_endpoint_defaults_to_agent_workflow_response PASSED
tests/test_api_ask.py::test_ask_endpoint_uses_legacy_rag_when_configured PASSED
tests/test_api_ask.py::test_ask_endpoint_rejects_empty_question PASSED
tests/test_api_ask.py::test_ask_endpoint_returns_404_for_unknown_experiment PASSED
tests/test_api_ask.py::test_ask_endpoint_returns_502_for_embedding_failure PASSED
tests/test_api_ask.py::test_ask_endpoint_returns_502_for_llm_failure PASSED

11 passed in 1.47s
```

## Files changed

- [`apps/api/ask_service.py`](/C:/Users/Archel/Documents/Personal%20Projects/ExperimentOS-AI/apps/api/ask_service.py)
- [`apps/api/main.py`](/C:/Users/Archel/Documents/Personal%20Projects/ExperimentOS-AI/apps/api/main.py)
- [`tests/test_api_health.py`](/C:/Users/Archel/Documents/Personal%20Projects/ExperimentOS-AI/tests/test_api_health.py)
- [`tests/test_api_ask.py`](/C:/Users/Archel/Documents/Personal%20Projects/ExperimentOS-AI/tests/test_api_ask.py)

## Self-review findings

- The route now exposes one stable response model for both runtime modes and keeps existing QA dependency construction intact behind the adapter boundary.
- The legacy adapter uses dataclass serialization for `retrieved_chunks`, `retrieval_metrics`, and `llm_metrics` because those runtime objects are dataclasses in the current codebase rather than Pydantic models.
- The agent-workflow adapter converts unexpected workflow exceptions into `AgentWorkflowExecutionError` so the route can consistently surface them as `502`.

## Any concerns

- `map_agent_state_to_ask_response()` is included here because the agent-workflow adapter needs a concrete API response mapper to function. Task 3 may add deeper mapper-specific test coverage and could refine this mapping further, but the current implementation already matches the response contract needed for Task 2.
