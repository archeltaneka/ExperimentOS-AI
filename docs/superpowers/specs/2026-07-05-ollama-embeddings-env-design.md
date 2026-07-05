# Ollama Embeddings And Env Design

## Goal

Add Ollama as a supported embedding provider and make the project load configuration from
`.env` consistently instead of requiring manual PowerShell environment variable assignment.
The `.env` file is the local source of truth and overrides any conflicting shell variables.

## Context

The ingestion and retrieval packages already use a shared `EmbeddingProvider` protocol and
`build_embedding_provider()` factory. FastAPI currently loads `.env` directly in
`apps/api/main.py`, while Alembic, ingestion CLI, retrieval CLI, and lower-level database code
read from `os.environ` without a shared bootstrap. This causes local workflows to require
commands such as `$env:DATABASE_URL = "..."` before running migrations or database-backed tests.

Ollama's current embedding API uses `POST /api/embed` with a `model` field and an `input` value
that can be a string or list of strings. The response includes an `embeddings` list with one
vector per input. The older `/api/embeddings` endpoint is superseded by `/api/embed`.

## Architecture

Create a small environment bootstrap module that wraps `python-dotenv` and calls
`load_dotenv(override=True)`. Database/session creation, API startup, and provider factory code
will call this helper before reading environment variables. This keeps configuration loading in
one place and makes `.env` values override already-set shell variables.

Keep Ollama embeddings inside `packages.ingestion.embeddings` because embedding providers already
live there. `OllamaEmbeddingProvider` will use `OLLAMA_BASE_URL`, `OLLAMA_EMBEDDING_MODEL`, and the
existing storage dimension. It will call `/api/embed`, validate that the response contains an
`embeddings` list, coerce values to floats, pad shorter vectors to `EMBEDDING_DIMENSION`, and
reject wider vectors.

## Configuration

`.env.example` will document:

- `DATABASE_URL`
- `EMBEDDING_PROVIDER=auto`
- `OLLAMA_BASE_URL=http://localhost:11434`
- `OLLAMA_EMBEDDING_MODEL=nomic-embed-text`
- existing LLM and OpenAI settings

Runtime commands should no longer instruct users to assign `$env:DATABASE_URL` manually. Local
setup should be `copy .env.example .env`, edit `.env` if needed, then run `uv` commands normally.

## CLI Behavior

Both ingestion and retrieval CLIs should accept `--embedding-provider ollama`, with `local` kept as
an alias in the provider factory. Existing provider options remain available:

- `auto`
- `fake`
- `openai`
- `huggingface`
- `ollama`

`auto` remains unchanged: it uses OpenAI when `OPENAI_API_KEY` is present and otherwise fake
embeddings. Ollama is selected explicitly through `.env` or CLI arguments.

## Error Handling

Ollama HTTP errors and connection errors should surface as `RuntimeError` messages that include
the failed provider context. Invalid response shapes should fail fast with clear messages. Vector
dimension mismatches should use the same behavior as the Hugging Face provider: pad shorter vectors
and reject vectors wider than the configured storage dimension.

## Testing

Tests will avoid real network calls by injecting a fake `post_json` callable into
`OllamaEmbeddingProvider`. Coverage should include:

- provider factory accepts `ollama`
- `/api/embed` URL and payload are correct
- vectors are padded to storage dimension
- oversized vectors are rejected
- ingestion and retrieval CLI parsers accept `ollama`
- `.env` loading overrides a conflicting shell `DATABASE_URL`

Database-backed tests remain gated by `DATABASE_URL`, but the value should come from `.env` after
the shared bootstrap runs.

## Documentation

Update README setup and migration instructions so they rely on `.env`. Remove local workflow
examples that tell users to set `$env:DATABASE_URL` manually. Mention that Ollama embeddings require
the model to be available in the local Ollama server, for example `nomic-embed-text`.
