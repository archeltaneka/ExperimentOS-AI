# ExperimentOS AI

> A portfolio-grade experiment-intelligence workspace that turns experiment artifacts into searchable evidence, grounded answers, and repeatable AI-quality evaluation.

[Repository](https://github.com/archeltaneka/ExperimentOS-AI) · **Public demo:** deployment not yet connected — run the deterministic frontend locally with the quick start below. · **Project status:** Portfolio UI MVP complete in fixture mode; backend-backed `/ask` is available for local development.

Experiment teams accumulate reports, metric exports, and rollout notes, but the evidence behind a decision is often difficult to recover. ExperimentOS AI makes that evidence searchable, routes questions through a grounded RAG and agent-workflow boundary, and treats AI reliability as a measurable engineering concern.

> [!IMPORTANT]
> The portfolio UI is deliberately honest about its data sources. Its public-deployment target is **deterministic fixture mode**: Ask Experiment, Explorer, and Evaluation pages use fixed in-repository data, while the backend-capable `/ask` integration can be enabled locally. The UI never labels fixtures as live telemetry.

## At a glance

- Evidence ingestion, PostgreSQL + pgvector retrieval, grounded QA, and a FastAPI `/ask` API.
- A five-page Next.js portfolio UI with typed service adapters and visible source disclosures.
- LangGraph workflow orchestration, explicit approval state, and structured response metadata.
- Offline golden-dataset evaluation, prompt registry/regression checks, factuality and hallucination evaluation, and CI quality gates.
- Statistical-analysis contracts and validation foundations; causal estimators and automated business-impact estimation remain unavailable.

## Screenshots

Current UI screenshots are intentionally pending capture from a verified production-mode run. The repository does not use third-party design references as product media. Capture instructions and required views are in [deployment guidance](docs/deployment.md#screenshots-and-demo-media); until then, use the local quick start to view the current UI.

## Problem and product

ExperimentOS AI is inspired by internal experimentation and decision-support platforms used across large product organizations. It addresses a narrower, demonstrable problem: preserving the report evidence, retrieval context, and quality checks needed to discuss an experiment responsibly.

The MVP demonstrates:

- Ingestion of synthetic experiment folders containing metadata, metrics, and Markdown reports.
- Semantic retrieval over report chunks stored with pgvector.
- Grounded answers with citations and retrieved-context inspection.
- A structured LangGraph decision workflow behind the backend `/ask` path.
- A recruiter-facing UI for experiment discovery, answer review, evaluation evidence, and roadmap status.

## Architecture

Implemented components are shown with solid arrows. Dashed arrows represent planned or partial product stages; they are not a claim that the entire decision-intelligence pipeline is operational.

```mermaid
flowchart LR
    Repo[Experiment repository<br/>metadata, metrics, reports] --> Ingest[Ingestion]
    Ingest --> DB[(PostgreSQL + pgvector)]
    DB --> Retrieve[Retrieval]
    Retrieve --> RAG[Grounded RAG]
    RAG --> Agent[LangGraph agent workflow]
    Agent --> Ask[FastAPI /ask]
    Ask --> UI[Next.js portfolio UI]

    DB -. planned data foundation .-> Stats[Statistical analysis]
    Stats -. planned decision layer .-> Decision[Decision intelligence]

    Eval[Golden datasets + RAGAS + DeepEval] -. evaluates .-> RAG
    Registry[Prompt registry + regression checks] -. governs .-> RAG
    Observe[Optional LangSmith / Phoenix / OpenTelemetry] -. observes .-> Agent
    CI[GitHub Actions quality gates] -. protects .-> Eval
```

Read the canonical [architecture guide](docs/architecture.md) for backend component boundaries and [frontend data-layer guide](docs/frontend-data-layer.md) for adapter boundaries.

## Capability matrix

| Capability | Backend status | UI status | Public demo source | Notes |
| --- | --- | --- | --- | --- |
| Semantic retrieval | Implemented | Represented | Deterministic fixture | pgvector-backed retrieval is available locally. |
| RAG answering | Implemented | Demonstrated | Fixture by default; configurable live `/ask` locally | Live mode requires an ingested experiment UUID and a running backend. |
| Agent workflow | Implemented | Represented | Fixture by default | LangGraph powers backend `/ask`; no public writable endpoint is deployed. |
| Experiment Explorer/detail | Partial read API | Implemented | Deterministic fixture | The backend read contract lacks the complete portfolio record. |
| Evaluation dashboard | Evaluation tooling implemented | Implemented | Deterministic fixture/artifact | No frontend results or telemetry API exists. |
| Descriptive/statistical foundations | Implemented foundation | Represented | Fixture/status | Input validation and unadjusted-analysis foundations only. |
| CUPED and advanced causal methods | Planned/future research | Coming soon | None | Not operational. |
| Automated business-impact estimation | Unavailable | Unavailable | None | A projection contract is not an estimator. |

## Five-page UI

| Route | Purpose | Source in fixture-mode demo |
| --- | --- | --- |
| `/` | Problem, architecture, system depth, and current roadmap | Repository-backed roadmap metadata |
| `/ask-experiment` | Grounded-answer workspace with citations and retrieved context | Deterministic Ask fixture |
| `/experiment-explorer` | Searchable experiment records and detail links | Deterministic experiment fixtures |
| `/experiment-explorer/[experimentId]` | Deep-linkable experiment detail and unknown-record state | Deterministic fixture / explicit not found |
| `/evaluation-dashboard` | Evaluation metrics, gates, and case analysis | Deterministic evaluation fixture |
| `/roadmap` | Implemented, in-progress, planned, and research phases | Versioned roadmap metadata |

## Technology stack

- Frontend: Next.js 16, React 19, TypeScript, Tailwind CSS, TanStack Query, Vitest.
- API: Python 3.12, FastAPI, Pydantic.
- Data: PostgreSQL 16, pgvector, SQLAlchemy, Alembic.
- AI workflows: retrieval, RAG, LangGraph, optional OpenAI/Gemini/Ollama providers.
- Reliability: repository-owned golden datasets, RAGAS and DeepEval integrations, prompt registry, LangSmith/Phoenix/OpenTelemetry adapters, GitHub Actions.

## Repository structure

```text
apps/api/                 FastAPI API, including /health, /experiments, and /ask
apps/web/                 Next.js portfolio UI, typed services, fixtures, and UI tests
packages/db/              SQLAlchemy models, sessions, and Alembic metadata
packages/ingestion/       Experiment-folder parsing, chunking, and embeddings
packages/retrieval/       pgvector retrieval service and CLI
packages/qa/              Grounded question-answering service
packages/agents/          LangGraph workflow and structured agent state
packages/evals/           Offline evaluation, reliability, and quality-policy workflows
migrations/               Alembic schema migrations
tests/                    Backend unit, API, migration, and database integration tests
docs/                     Architecture, development, deployment, and reliability guides
.github/workflows/        Backend CI and frontend quality workflows
```

The UI keeps presentation, service contracts, transport mapping, and fixtures separate so a future API can replace an adapter without leaking raw HTTP payloads into components.

## Repository output policy

Use `artifacts/local/...` for routine local verification output. Use `reports/` only when intentionally refreshing curated baseline/reference artifacts that belong in git.

## Quick start: frontend-only deterministic demo

This is the lowest-friction path for a reviewer. It needs no database, API key, or backend process.

```sh
cd apps/web
npm ci
cp .env.example .env.local
npm run dev
```

Open `http://localhost:3000`. `.env.example` selects `NEXT_PUBLIC_DATA_MODE=mock`, so all five UI pages remain navigable on fixed, deterministic data.

For a production-like local run:

```sh
cd apps/web
npm run build
npm run start
```

## Frontend configuration and deployment

| Variable | Public? | Required | Valid values / example | Behaviour when absent |
| --- | --- | --- | --- | --- |
| `NEXT_PUBLIC_DATA_MODE` | Yes | No | `mock` (default) or `live` | Defaults to `mock`; any other supplied value raises a configuration error. |
| `NEXT_PUBLIC_API_BASE_URL` | Yes | Only for `live` mode | `http://localhost:8000` | `live` mode fails clearly before making a request. |

`NEXT_PUBLIC_*` values are embedded in the browser bundle. They must contain only public configuration, never API keys, database URLs, or provider credentials.

The intended public deployment is a **Vercel fixture-mode frontend** with `apps/web` configured as the project root and `NEXT_PUBLIC_DATA_MODE=mock`. Next.js is auto-detected; no `vercel.json` is needed. There is currently no verified deployment URL, so this README intentionally makes no uptime or hosting claim. See [deployment guidance](docs/deployment.md).

## Full-stack local setup

The backend is intentionally separate from the public portfolio demo. It requires PostgreSQL 16 with pgvector and an ingested experiment before the live Ask adapter can answer a question.

```sh
uv sync
cp .env.example .env
docker compose up -d postgres
export DATABASE_URL="postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run alembic upgrade head
uv run python scripts/generate_synthetic_experiments.py
uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-001-payment-recommendation --embedding-provider fake
uv run uvicorn apps.api.main:app --reload
```

In a second terminal, set the frontend to live Ask mode:

```text
NEXT_PUBLIC_DATA_MODE=live
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Then run `npm run dev` in `apps/web`. The current live API contract is `POST /ask`; experiment browsing/detail may use a partial read adapter, but the complete Explorer experience and the Evaluation Dashboard remain fixture-backed. [Frontend development](docs/frontend.md), [API reference](docs/api.md), and [development guide](docs/development.md) provide the deeper setup details.

## Testing and quality gates

Frontend CI runs a clean `npm ci`, linting, TypeScript checking, deterministic component/fixture tests, and a Next.js production build in mock mode:

```sh
cd apps/web
npm run verify
```

Backend quality checks include Ruff formatting/linting, unit and database-backed tests, offline evaluation smoke checks, and an AI quality gate. Start Postgres for the database path:

```sh
uv run ruff check .
uv run pytest
docker compose up -d postgres
export DATABASE_URL="postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run alembic upgrade head
uv run pytest tests/test_db_models.py tests/test_ingestion_load_experiment.py
```

To intentionally refresh the curated Phase 3 baseline report:

```sh
uv run python -m packages.evals.run_baseline --embedding-provider fake --llm-provider mock --output reports/phase3/baseline_report.md
```

See [frontend quality](docs/frontend-quality.md) and [GitHub Actions CI](docs/phase3/github_actions.md) for the authoritative workflow breakdown. The repository does not claim coverage percentages or browser-suite coverage that it does not measure.

## AI reliability and evaluation

AI quality is treated as an engineering surface, not just a model choice. Repository-owned golden datasets exercise retrieval and grounded-answer contracts. Optional RAGAS and DeepEval integrations add framework-oriented retrieval, factuality, hallucination, and prompt-regression measures without replacing deterministic local checks. A versioned prompt registry and offline experiments make prompt changes reviewable. Optional LangSmith, Phoenix, and OpenTelemetry adapters export selected, redacted observability data only when configured; they are not a claim of live production monitoring.

The CI quality gate combines these signals with policy checks. Details and configuration boundaries are in [Phase 3 reliability documentation](docs/phase3/reliability_baseline.md).

## Roadmap

| Phase | Status |
| --- | --- |
| Foundation | Completed |
| Agent Workflow | Completed |
| LLMOps and AI Reliability | Completed |
| Product Intelligence and Causal Inference | In progress — foundations only |
| Enterprise Platform | Future |
| Research and Advanced Intelligence | Future research |

Phase 4 currently includes typed contracts, eligibility validation, descriptive summaries, and an unadjusted randomized-analysis foundation. It does not expose CUPED, sequential testing, Bayesian A/B testing, Difference-in-Differences, propensity-score methods, Double Machine Learning, EconML, DoWhy, or business-impact estimation as operational functionality.

## Known limitations

- No public deployment has been verified yet; the documented target is fixture-mode frontend hosting.
- The portfolio UI uses deterministic fixtures where complete backend endpoints do not exist.
- `/ask` is the only backend-capable UI workflow; it requires local Postgres, ingested data, and deliberate live-mode configuration.
- There is no real experiment-list/detail contract rich enough for the full UI, no evaluation-results API, and no live telemetry dashboard.
- No authentication, multi-user collaboration, enterprise governance, or public LLM abuse/cost controls are implemented.
- This is a portfolio-oriented deployment boundary, not an enterprise-production deployment.

## Portfolio and contribution information

[Portfolio messaging, LinkedIn copy, resume entry, interview talking points, and demo walkthrough](docs/portfolio-messaging.md) are provided for accurate reuse. The project is licensed under the [MIT License](LICENSE). No standalone contributor governance document is currently provided; contributions should preserve fixture disclosure, typed service boundaries, and capability honesty.
