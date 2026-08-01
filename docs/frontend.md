# Frontend development

The ExperimentOS AI frontend lives in `apps/web/`. It is an independent Next.js application with a
typed data boundary: deterministic fixture mode is the default portfolio experience, while local
live mode can call the existing FastAPI contracts. It does not change how the FastAPI service runs.

## Prerequisites

- Node.js 22.13 or later
- npm (included with Node.js)
- Python 3.12, `uv`, and Docker only when working on the backend

## Commands

Run these commands from `apps/web/`:

```powershell
npm install
npm run dev
npm run lint
npm run typecheck
npm run test
npm run build
```

`npm run dev` starts the frontend at `http://localhost:3000` by default. The FastAPI API remains
independently runnable from the repository root with `uv run uvicorn apps.api.main:app --reload`.

## Architecture

- `app/` owns routes, the root layout, metadata, global styles, and the TanStack Query provider.
- `components/ui/` contains the minimal local shadcn/ui-style primitives configured by
  `components.json`.
- `components/` contains shared composition components.
- `features/`, `hooks/`, `services/`, `types/`, `mock/`, and `styles/` document the future homes for
  their respective responsibilities without creating premature abstractions.
- `lib/capability-status.ts` centralizes honest capability labels and styling.

Issue #115 provides the shared shell: a sticky desktop sidebar at the `lg` breakpoint and a labelled
mobile navigation drawer below it. The drawer closes on backdrop interaction, route selection, or
Escape and returns focus to its trigger. Route definitions are centralized in `lib/navigation.ts`.
All five MVP routes are intentionally limited to placeholders until their dedicated issues.

## Environment variables

Use `apps/web/.env.local` for local frontend values and expose only intentional browser-safe values
with the `NEXT_PUBLIC_` prefix.
Do not place frontend secrets in the root backend `.env` file or commit `.env.local`.

Issue #116 introduces `NEXT_PUBLIC_DATA_MODE` and `NEXT_PUBLIC_API_BASE_URL` for the typed frontend
data boundary. See [`docs/frontend-data-layer.md`](frontend-data-layer.md) for adapter selection,
verified `/ask` contract details, deterministic-fixture rules, and current backend gaps.

## Current data status

The five public UI routes are implemented: Landing Page, Ask Experiment, Experiment Explorer/detail,
Evaluation Dashboard, and Roadmap. `NEXT_PUBLIC_DATA_MODE=mock` selects deterministic fixtures for a
stable portfolio demo. In `live` mode, Ask calls the existing `POST /ask` API and Explorer can use the
partial experiment-read adapter. The complete Explorer record and all Evaluation views remain
fixture-backed because the backend does not expose the fields or results APIs required by those pages.

Every data-backed page renders a source disclosure. A fixture is never labelled as live telemetry;
the roadmap is local versioned product configuration. Planned Phase 4 capabilities are statuses, not
operational features. See [frontend data layer](frontend-data-layer.md) and
[portfolio deployment](deployment.md) for the canonical capability and hosting boundary.
