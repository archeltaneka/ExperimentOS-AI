# Frontend data layer

Issue #116 establishes the frontend boundary between presentation code and data access. It does not
add page UI or backend endpoints.

## Architecture

- `apps/web/types/domain.ts` holds frontend-friendly domain models and constrained status unions.
- `apps/web/services/transport/ask.ts` holds the snake_case `/ask` transport contract and maps it to
  domain models. UI code must not receive raw API dictionaries.
- `apps/web/services/contracts.ts` defines the small Ask, Experiment, Evaluation, and Roadmap service
  interfaces used by hooks and future presentation components.
- `apps/web/services/http-ask-service.ts` is the only real HTTP adapter. It supports abort signals,
  has a 15-second timeout, parses JSON explicitly, validates the stable response envelope, and
  converts failures to `ApiError`.
- `apps/web/services/mock-services.ts` supplies deterministic fixture adapters. Fixtures are isolated
  under `apps/web/mock/` by domain and contain fixed IDs, dates, and values; no runtime randomness or
  current-clock timestamps are used.
- `apps/web/hooks/use-services.ts` is the TanStack Query boundary. Components use these hooks, never
  `fetch`, environment variables, or fixture modules.

## Verified backend contract

The FastAPI backend exposes `POST /ask` with this request payload:

```json
{ "question": "string", "experiment_id": "non-empty string", "top_k": 5 }
```

`top_k` is optional (default `5`) and constrained to `1..20`. A live request checks that
`experiment_id` is a UUID belonging to an ingested database experiment. The response always includes
`answer`, `citations`, `retrieved_chunks`, `retrieval_metrics`, and `llm_metrics`; it can additionally
include nullable `prompt_metadata`, `intent`, `decision`, `executive_summary`, `agent_trace`,
`agent_metrics`, and `approval_status`. Nested citation and workflow structures are raw backend
dictionaries, so the mapper only promotes verified stable fields and keeps optional fields honest.

There is no backend request ID, response timestamp, experiment list/detail endpoint, evaluation API,
roadmap API, or observability read API. The frontend does not invent these routes.

## Adapter selection

Create `apps/web/.env.local` from `.env.example`:

```text
NEXT_PUBLIC_DATA_MODE=mock
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

`NEXT_PUBLIC_DATA_MODE` is required to be `mock` or `live` when supplied; an invalid value throws a
typed configuration error. `live` requires `NEXT_PUBLIC_API_BASE_URL`; no failure falls back to mock.
The explicit default remains `mock` so the portfolio starts without a backend.

| Service | Mock mode | Live mode |
| --- | --- | --- |
| Ask | deterministic fixture | real `POST /ask` |
| Experiments | deterministic fixture | deterministic fixture (no backend read route) |
| Evaluations | deterministic fixture | deterministic fixture (no backend read route) |
| Roadmap | local versioned product metadata | local versioned product metadata |

Each service has `DataSource` metadata. Future pages can disclose `Live backend`, `Development
fixture`, or `Local product configuration`; fixtures must never be labelled as production telemetry.

## Query and error conventions

`askQueryKeys` centralizes stable parameterized keys. Query hooks use five-minute stale data, no retries,
window-focus refetch disabled, and TanStack's abort signal. Ask is a mutation. Data is not eagerly
fetched at startup, and there is no polling or global state store.

`ApiError` distinguishes `network`, `timeout`, `aborted`, `invalid_response`, `validation`, `server`,
`not_found`, `configuration`, and `unsupported`. It carries a safe user message plus optional
developer diagnostic without exposing secrets.

## Fixture limitations

Fixtures demonstrate completed, running, inconclusive, and stopped experiments; approved, rejected,
and pending decisions; retrieval evidence; evaluation pass/fail states; and completed, active, and
future roadmap phases. Descriptive statistics may be shown as available. CUPED, sequential testing,
Bayesian A/B testing, Difference-in-Differences, propensity-score methods, Double Machine Learning,
EconML, DoWhy, and business-impact estimation are statuses only, never operational outputs.

## Adding a future endpoint

Add transport types and mapping functions first, then extend the corresponding service interface and
add a real adapter implementation. Update `createServices` deliberately, retain fixture fallback only
where documented, and expose the adapter through an existing or new hook. Presentation components
continue consuming domain models and hooks without importing an HTTP client or fixture.
