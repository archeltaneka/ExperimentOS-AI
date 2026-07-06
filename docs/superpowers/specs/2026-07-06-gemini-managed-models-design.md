# Gemini Managed Models Design

## Goal

Move the deployable API path away from local Ollama/Qwen defaults so ExperimentOS AI can run on a low-memory host such as Render free tier. Gemini should become a first-class managed provider for both answer generation and embeddings, while existing local and deterministic providers remain available for development and tests.

## Provider Defaults

The API should keep `LLM_PROVIDER=auto` and `EMBEDDING_PROVIDER=auto` as the simple deployment configuration. In auto mode:

- If `GEMINI_API_KEY` is set, use Gemini for both LLM generation and embeddings.
- Otherwise, if `OPENAI_API_KEY` is set, keep the existing OpenAI behavior.
- Otherwise, use deterministic local fallbacks: mock LLM responses and fake embeddings.

Explicit `LLM_PROVIDER=gemini` or `EMBEDDING_PROVIDER=gemini` should require `GEMINI_API_KEY` and fail with a clear configuration error when it is missing.

## Models

Use `gemini-embedding-001` as the default Gemini embedding model. Request a `1536`-dimension output so the existing pgvector column and tests do not require a schema migration.

Use a Gemini Flash model as the default LLM model, configurable through `GEMINI_MODEL`. Keep a separate `GEMINI_EMBEDDING_MODEL` override for embeddings. The implementation should not hard-code secrets and should read credentials from environment variables.

## Components

Add `GeminiEmbeddingProvider` in `packages/ingestion/embeddings.py`. It should follow the existing provider interface, accept an injectable client for tests, return one vector per input text, and fit or validate the configured storage dimension.

Add `GeminiLLMClient` in `packages/llm/client.py`. It should follow the existing async `LLMClient` protocol, accept an injectable client for tests, wrap API failures as `LLMClientError`, and report model, latency, and best-effort token metrics.

Update `apps/api/main.py` so `get_llm_client()` and the embedding provider path support Gemini in both explicit and auto modes.

Update CLI provider choices and labels in ingestion, retrieval, and evaluation flows so `gemini` is accepted and reports the chosen Gemini model names.

## Dependencies And Configuration

Add the official Google GenAI Python SDK dependency to `pyproject.toml` and `uv.lock`.

Update `.env.example` with:

- `GEMINI_API_KEY=`
- `GEMINI_MODEL=`
- `GEMINI_EMBEDDING_MODEL=gemini-embedding-001`

The app should continue to support `OPENAI_API_KEY` and OpenAI settings for users who choose OpenAI explicitly.

## Error Handling

Embedding failures should continue to surface through the existing QA embedding failure path and produce the current `/ask` 502 behavior. LLM failures should continue through `LLMClientError` and produce the current `/ask` 502 behavior.

Provider factory errors should be clear enough to diagnose missing dependencies, missing API keys, or unsupported provider names.

## Testing

Use TDD for the implementation. Add failing tests first for:

- Gemini embedding provider calls, dimension handling, and empty input behavior.
- `build_embedding_provider("gemini")` and auto selection when `GEMINI_API_KEY` is set.
- Gemini LLM client calls and metrics using a stub client.
- API LLM auto selection preferring Gemini when `GEMINI_API_KEY` is present.
- CLI parsing and evaluation labels for the `gemini` provider.

No test should call the real Gemini API.

Verification should run the relevant unit tests plus `uv run ruff check .` after Python changes.
