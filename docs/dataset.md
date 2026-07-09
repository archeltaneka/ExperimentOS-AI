# Dataset Guide

ExperimentOS AI uses two local datasets:

1. A synthetic experiment corpus under `data/synthetic/experiments/`
2. An offline QA evaluation dataset at `data/eval/qa_dataset.json`

## Synthetic Experiment Corpus

The repository currently includes ten synthetic experiment folders:

- `exp-001-payment-recommendation`
- `exp-002-hotel-image-quality`
- `exp-003-search-ranking`
- `exp-004-checkout-ux`
- `exp-005-pricing`
- `exp-006-loyalty`
- `exp-007-crm-notifications`
- `exp-008-recommendation-systems`
- `exp-009-search-filters`
- `exp-010-premium-subscriptions`

Each folder contains:

- `metadata.json`
- `metrics.csv`
- `events.csv`
- `report.md`

### File Roles

`metadata.json`

- high-level experiment metadata
- owner and team information
- hypothesis, status, dates, variants, and business decision
- the synthetic experiment ID that is preserved in the database config

`metrics.csv`

- experiment metric rows for control and treatment variants
- includes metric name, variant, value, numerator, denominator, lift, p-value, and notes
- must include the same `experiment_id` as the metadata file

`report.md`

- the narrative analysis document used for chunking and retrieval
- contains decisions, caveats, risks, and metric interpretation

`events.csv`

- generated as future-facing evidence for event-level workflows
- currently not ingested by `packages.ingestion.load_experiment`

## Generating The Corpus

Regenerate the synthetic corpus with:

```powershell
uv run python scripts/generate_synthetic_experiments.py
```

Warning:

- This command deletes and recreates `data/synthetic/experiments`.
- Do not run it if you need to preserve local edits in that directory.

## Ingesting Synthetic Experiments

Ingest a single experiment with deterministic embeddings:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-001-payment-recommendation --embedding-provider fake
```

The ingestion pipeline currently requires:

- `metadata.json`
- `metrics.csv`
- `report.md`

The ingestion command stores:

- one `experiments` row
- multiple `experiment_metrics` rows
- one `documents` row for `report.md`
- multiple `document_chunks` rows, with or without embeddings

## Offline Evaluation Dataset

`data/eval/qa_dataset.json` is a JSON list of evaluation records used by `packages.evals.run`.

Each record includes:

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | Stable question identifier |
| `experiment_id` | string | Synthetic experiment ID, not DB UUID |
| `question` | string | Evaluation prompt |
| `expected_documents` | list of strings | Expected document titles |
| `expected_keywords` | list of strings | Retrieval and answer clues |
| `category` | string | Category such as `decision`, `metric`, `caveat`, or `risk` |
| `difficulty` | string | Difficulty label |
| `reference_answer` | string | Human-written expected answer |

Current dataset characteristics:

- covers all 10 synthetic experiments
- includes 4 questions per experiment
- focuses on `decision`, `metric`, `caveat`, and `risk` categories
- is validated by `packages.evals.dataset.load_evaluation_dataset`

## How Evaluation Uses The Dataset

The evaluation harness:

1. Loads `data/eval/qa_dataset.json`
2. Resolves each synthetic experiment ID to the ingested database UUID through `Experiment.config["experiment_id"]`
3. Runs the Phase 1 QA flow that remains available behind `ASK_MODE=legacy_rag`
4. Aggregates metrics and writes a Markdown report

Run the evaluation locally:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run python -m packages.evals.run --embedding-provider fake --llm-provider mock --output reports/evaluation.md
```

Read the report:

```powershell
Get-Content reports/evaluation.md
```

## Practical Notes

- Use `--embedding-provider fake` for deterministic local retrieval behavior.
- Use `--llm-provider mock` for deterministic local answer generation in evaluation.
- `/ask` expects a database UUID, while the evaluation dataset stores synthetic experiment IDs and resolves them internally.
- If you regenerate the synthetic corpus, re-ingest experiments before running retrieval or evaluation workflows against a fresh database.
