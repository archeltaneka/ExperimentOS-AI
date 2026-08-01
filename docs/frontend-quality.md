# Frontend quality workflow

The portfolio UI uses a deliberately small test pyramid. The standard suite is deterministic: it
uses `NEXT_PUBLIC_DATA_MODE=mock`, fixed in-repository fixtures, no FastAPI server, and no OpenAI,
LangSmith, Phoenix, or other external credentials.

## Layers and commands

Run commands from `apps/web/`:

```powershell
npm ci
npm run lint
npm run typecheck
npm run test
npm run build
npm run verify
```

`npm run test` covers pure domain and fixture contracts, service adapters, and public component
behaviour with Vitest, React Testing Library, jsdom, and user-facing roles. `npm run verify` runs
the same lint, type, test, and production-build quality gates used in CI.

Tests that render TanStack Query consumers should use `renderWithProviders` from
`tests/render.tsx`. It creates a fresh `QueryClient` with retries disabled for every test. Keep
route setup explicit; the helper deliberately does not hide routing or service behaviour.

Mock services are selected through `createServices({ dataMode: "mock" })`, not through direct
fixture imports in presentation modules. To add a component test, mock the service hook at that
boundary or provide a dedicated service adapter, then assert what a user can read or operate. To
add an evaluation fixture, keep IDs and timestamps stable and extend `fixture-integrity.test.ts`
when you add a cross-reference or gate calculation.

Accessibility coverage is targeted rather than a compliance claim: representative tests assert
headings, labels, landmarks, accessible navigation, button names, menu state, focus return, table
semantics, and status text. Automated tests do not replace manual keyboard and screen-reader
review.

There is no browser suite at present. The UI has no browser-only integration that is not already
covered by deterministic component tests, so Playwright would add download and maintenance cost
without a distinct regression signal. Reassess this when a real browser-only flow or live frontend
integration is introduced.

## CI

`.github/workflows/frontend-quality.yml` always runs for pull requests and pushes to `main`. It is
intentionally not path-filtered: skipped required workflows can remain pending under branch
protection. Its stable required check is `Frontend Quality / frontend-quality`; it installs with
`npm ci` using `apps/web/package-lock.json`, then runs lint, type checking, tests, and the
production build in mock mode.

The existing `CI` workflow remains the backend quality pipeline and is not changed or weakened by
this workflow. The two workflows use separate dependency managers and credentials. Until the
backend pipeline itself adopts safe job-level path decisions with an always-running required
aggregator, it may still run on frontend changes; the frontend workflow never causes backend jobs
to be skipped or hidden.

Only `NEXT_PUBLIC_DATA_MODE=mock` is required by frontend CI. Live mode requires
`NEXT_PUBLIC_API_BASE_URL` and is intentionally not exercised in the standard suite. Never expose
secrets through `NEXT_PUBLIC_` variables or add live-service fallbacks to fixture tests.

## Manual check

Before a UI release, manually check the major routes, desktop and mobile navigation, keyboard
navigation, the deterministic Ask flow, explorer filters, known and unknown experiment details,
evaluation gate summary, roadmap active phase, and browser console. Confirm that planned Phase 4
methods and automated business-impact estimation are not presented as operational.
