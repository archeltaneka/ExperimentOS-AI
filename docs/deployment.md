# Portfolio deployment and demo guide

## Selected public-demo mode

The selected mode is **fixture mode**: deploy only `apps/web` with `NEXT_PUBLIC_DATA_MODE=mock`.
This gives reviewers a stable demo without a database, API key, provider cost, or public writable
LLM endpoint. It matches the existing typed mock adapters and source disclosures.

Mixed mode is not selected. A live `/ask` service requires an ingested experiment UUID, PostgreSQL
with pgvector, a deliberate LLM provider, CORS configuration, and abuse/cost controls. Live mode is
not selected because the Explorer and Evaluation pages do not have complete read APIs.

## Vercel target

Vercel is the recommended host for the nested Next.js app:

1. Import `archeltaneka/ExperimentOS-AI` and set **Root Directory** to `apps/web`.
2. Keep the detected Next.js preset and defaults (`npm ci`, `npm run build`, and `.next` output).
3. Set `NEXT_PUBLIC_DATA_MODE=mock` for Preview and Production.
4. Leave `NEXT_PUBLIC_API_BASE_URL` unset for the public fixture demo.
5. Verify the HTTPS deployment using the checklist below before publishing its URL.

No `vercel.json` is required: Vercel detects Next.js and App Router routes, including dynamic
experiment details, work on direct navigation and refresh through the Next.js host. There is no
verified Vercel project, deployment, custom domain, or public URL at the time of this document.

## Environment variables

Create `apps/web/.env.local` from `apps/web/.env.example`:

```text
NEXT_PUBLIC_DATA_MODE=mock
# NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

| Variable | Public? | Purpose | Required | Failure behaviour |
| --- | --- | --- | --- | --- |
| `NEXT_PUBLIC_DATA_MODE` | Yes | `mock` fixtures or explicit `live` adapters. | No | Missing defaults to `mock`; invalid values throw a typed configuration error. |
| `NEXT_PUBLIC_API_BASE_URL` | Yes | Base URL for live Ask/partial Experiment adapters. | Only in `live` | Missing/blank `live` configuration throws a typed configuration error. |

Never put `DATABASE_URL`, provider keys, LangSmith keys, or other server credentials in
`NEXT_PUBLIC_*` variables.

## Fixture versus live boundary

| UI capability | Fixture mode | Live mode | Honest boundary |
| --- | --- | --- | --- |
| Landing / Roadmap | Repository-backed deterministic metadata | Same | No API required. |
| Ask Experiment | Deterministic answer fixture | `POST /ask` | Live Ask requires an ingested experiment UUID. |
| Explorer / detail | Complete deterministic records | Partial `GET /experiments` adapter | Live responses lack the complete UI record. |
| Evaluation Dashboard | Deterministic evaluation fixture | Same | No results or telemetry API exists. |

The backend CORS policy intentionally permits only local development origins without credentials.
Fixture-mode hosting requires no CORS change. A future protected backend must allow only its verified
frontend origin; do not introduce wildcard production CORS merely for a demo.

## Local backend boundary

The FastAPI service is not part of this Vercel target. Local live Ask requires Python 3.12, `uv`,
Docker, PostgreSQL 16 + pgvector, migrations, and an ingested experiment. Offline-safe work uses
`EMBEDDING_PROVIDER=fake` and `LLM_PROVIDER=mock`; any live provider credential stays in root `.env`.

```powershell
uv sync
Copy-Item .env.example .env
docker compose up -d postgres
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run alembic upgrade head
uv run python scripts/generate_synthetic_experiments.py
uv run uvicorn apps.api.main:app --reload
```

The generator deletes and recreates `data/synthetic/experiments`; do not run it over retained local data.

## Production-mode route checklist

From `apps/web`, run `npm ci`, `npm run verify`, then `npm run start`. Verify direct navigation and
refresh for `/`, `/ask-experiment`, `/experiment-explorer`, the known detail
`/experiment-explorer/8bb4bf4d-a372-4b6e-93a5-0dd9ad7c8750`, an unknown detail, `/evaluation-dashboard`,
and `/roadmap`. At desktop, tablet, and mobile widths, check keyboard navigation, source badges,
no localhost links in production-facing copy, no console/hydration error, no broken asset, and no
future Phase 4 method presented as operational.

## Screenshots and security review

Do not use untracked `docs/ui-references/` images as product screenshots: they are external design
references. Capture current production-mode views at a consistent viewport with no browser/personal
data visible, then store concise PNGs under `docs/assets/screenshots/` as `portfolio-landing`,
`portfolio-ask-result`, `portfolio-explorer`, `portfolio-detail`, `portfolio-evaluation`, and
`portfolio-roadmap`.

Root `.env` and frontend `.env.local` are ignored; examples contain no keys. Fixture mode contains
no backend URL, database connection, or provider key. This is a repository readiness review, not a
full security audit.

## Milestone audit

Portfolio UI MVP issues #114–#124 are closed. Issue #125 is the sole open milestone issue while its
repository-side documentation and verification work is in progress. Keep the milestone open until
the clean-tree, CI, and any claimed production-URL evidence are verified.
