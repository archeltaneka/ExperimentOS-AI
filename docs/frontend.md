# Frontend development

The ExperimentOS AI frontend lives in `apps/web/`. It is an independent Next.js application that
will consume backend APIs in later issues; it does not change how the FastAPI service runs.

## Prerequisites

- Node.js 20.9 or later
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

The root route is a temporary foundation preview only. It verifies typography, semantic tokens,
dark-first styling, primitive components, responsive spacing, and capability statuses. It is not a
landing page, application shell, navigation, dashboard, explorer, roadmap, or API surface.

## Environment variables

No frontend environment variables are needed today. When one is introduced, use `apps/web/.env.local`
for local values and expose only intentional browser-safe values with the `NEXT_PUBLIC_` prefix.
Do not place frontend secrets in the root backend `.env` file or commit `.env.local`.

## Current data status and Issue #1 boundary

No backend integration, API adapter, product workflow, experiment fixture, evaluation fixture, or
mock response exists yet. Recharts, Lucide, and Framer Motion are installed as approved foundation
dependencies; only Lucide and restrained Framer Motion are exercised by the temporary preview.

Issue #1 establishes the frontend foundation and design system only. A later issue will replace the
preview with the real product UI.
