# ExperimentOS AI portfolio messaging

## One-line description

ExperimentOS AI is an experiment-intelligence portfolio project combining pgvector retrieval,
grounded RAG, LangGraph workflows, and measurable AI-quality controls.

## Short description

ExperimentOS AI turns experiment artifacts into searchable evidence and grounded decision support.
It pairs a FastAPI/PostgreSQL/pgvector backend with a Next.js UI and makes reliability visible
through deterministic fixtures, golden datasets, prompt regression, and CI quality gates.

## Technical summary

The project separates presentation components from typed service contracts, transport mappers, HTTP
adapters, and deterministic fixtures. FastAPI, SQLAlchemy/Alembic, PostgreSQL + pgvector, and
LangGraph provide the backend foundation. Golden datasets, offline evaluation, RAGAS/DeepEval-oriented
checks, prompt registry/regression, and optional LangSmith, Phoenix, and OpenTelemetry integrations
make AI behaviour inspectable. Phase 4 contains foundations only; advanced causal methods are not
claimed as complete.

## Key technical highlights

- Evidence-first RAG with retrieved-context and citation contracts.
- Typed Next.js adapters preserving fixture/live boundaries.
- LangGraph workflow with explicit routing, approval state, and trace metadata.
- PostgreSQL + pgvector, SQLAlchemy, Alembic, FastAPI, Next.js, and TypeScript across clear boundaries.
- Golden datasets, prompt regression, factuality/hallucination evaluation, and CI quality gates.
- Explicit status gating for unfinished statistical and causal-inference work.

## Current status and demo disclaimer

The Portfolio UI MVP is complete in deterministic fixture mode. The local backend supports `/ask`
with PostgreSQL/pgvector and an ingested experiment; Explorer and Evaluation remain fixture-backed
because complete read APIs are unavailable. A public-demo target uses source-disclosed fixtures, not
live telemetry; planned Phase 4 methods produce no operational results.

## LinkedIn Projects / Featured entry

**ExperimentOS AI — Experiment intelligence, grounded RAG, and AI reliability**

Built an experiment-intelligence workspace that ingests artifacts, retrieves evidence with
PostgreSQL + pgvector, and supports grounded questions through FastAPI and LangGraph. Added a Next.js
UI with explicit fixture/live boundaries, golden datasets, prompt regression, evaluation checks,
optional observability integrations, and CI quality gates. Public-demo target: deterministic fixture
mode; live `/ask` is available locally. Repository: https://github.com/archeltaneka/ExperimentOS-AI

## Resume-ready entry

**ExperimentOS AI** — Python, FastAPI, PostgreSQL/pgvector, SQLAlchemy, Alembic, LangGraph, Next.js, TypeScript

- Built an evidence-first experimentation workspace with semantic retrieval and grounded `/ask` responses.
- Designed typed Next.js service adapters and deterministic fixtures that preserve honest live/fixture boundaries.
- Added golden datasets, prompt regression, factuality/hallucination evaluation, optional observability, and CI gates.

Repository: https://github.com/archeltaneka/ExperimentOS-AI

## Interview talking points

- The problem is preserving the evidence behind experimentation decisions.
- pgvector keeps similarity search beside relational metadata in an inspectable Postgres stack.
- Service adapters keep components independent from raw HTTP and fixture data.
- LangGraph makes routing, state, approval, and trace explicit rather than hiding it in one prompt.
- Human approval preserves decision support rather than autonomous decisions.
- Deterministic fixtures make the portfolio reliable without cost, credentials, or outage risk.
- Quality is measured with golden datasets, offline checks, prompt regression, and quality policy gates.
- Observability integrations are optional and configuration-dependent, not claims of live monitoring.
- Phase 4 adds validated inputs and descriptive foundations; causal estimators remain future work.
- The key limitation is missing complete live Explorer/Evaluation read APIs; next priority is safe, richer contracts.

## Two-to-four-minute demo walkthrough

1. Landing Page: problem, architecture, and phase labels.
2. Ask Experiment: submit an example prompt; inspect answer, citations, and retrieved context; state it is fixture-backed in demo mode.
3. Explorer/detail: filter records, open a known detail, and point out the source badge and fixture boundary.
4. Evaluation Dashboard: show pass/fail cases and explain they are deterministic artifacts, not telemetry.
5. Roadmap: contrast completed foundation/reliability work with Phase 4 foundations and planned methods.
6. Close: stable, honest fixture demo plus separately runnable backend and measurable quality controls.
