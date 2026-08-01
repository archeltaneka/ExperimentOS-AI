# ExperimentOS AI frontend

This independent UI defaults to deterministic fixture mode, so reviewers can view every page without
a database, API key, or backend process.

```powershell
npm ci
Copy-Item .env.example .env.local
npm run dev
```

`NEXT_PUBLIC_DATA_MODE=mock` is the portfolio default. Set `NEXT_PUBLIC_DATA_MODE=live` and
`NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` only with a local backend and ingested experiment.
`/ask` is the primary backend-capable UI workflow; full Explorer and Evaluation experiences remain
fixture-backed. Run `npm run verify` for linting, type checking, tests, and production build.

See [frontend development](../../docs/frontend.md), [data boundaries](../../docs/frontend-data-layer.md),
[frontend quality](../../docs/frontend-quality.md), and [deployment](../../docs/deployment.md).
