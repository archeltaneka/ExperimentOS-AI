# Dataset Guide

ExperimentOS AI uses three repository-owned evaluation assets plus the synthetic experiment corpus:

1. `data/synthetic/experiments/`
2. `data/eval/qa_dataset.json`
3. `data/eval/agent_dataset.json`
4. deterministic `/ask` E2E cases in `packages/evals/agent_e2e.py`

The synthetic corpus is the shared evidence source. The QA dataset exercises `legacy_rag`, the
agent dataset exercises the deterministic workflow service, and the E2E cases exercise the `/ask`
API contract in both default `agent_workflow` mode and `ASK_MODE=legacy_rag`.

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
- the synthetic experiment ID preserved in the database config

`metrics.csv`

- control and treatment metric rows
- primary and secondary metrics, sample sizes, lift, p-value, and notes
- the same `experiment_id` used by `metadata.json`

`report.md`

- the narrative analysis used for chunking and retrieval
- decisions, risks, caveats, and interpretation guidance

`events.csv`

- future-facing event-level evidence
- currently not ingested by `packages.ingestion.load_experiment`

## Generating The Corpus

Regenerate the synthetic corpus with:

```powershell
uv run python scripts/generate_synthetic_experiments.py
```

Warning:

- This deletes and recreates `data/synthetic/experiments`.
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

The command stores:

- one `experiments` row
- multiple `experiment_metrics` rows
- one `documents` row for `report.md`
- multiple `document_chunks` rows

## QA Evaluation Dataset

`data/eval/qa_dataset.json` is the Phase 1 offline QA dataset used by `packages.evals.run`.
It is also the single source of truth for the optional `packages.evals.run_ragas` and
`packages.evals.run_deepeval` adapters.

It is loaded by `packages.evals.dataset.load_evaluation_dataset`.

### QA Schema

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | Stable case identifier |
| `experiment_id` | string | Synthetic experiment ID, not DB UUID |
| `question` | string | Evaluation prompt |
| `expected_documents` | list of strings | Expected supporting document titles |
| `expected_keywords` | list of strings | Retrieval and answer clues |
| `category` | string | Coverage bucket for reporting |
| `difficulty` | string | Difficulty label |
| `reference_answer` | string | Human-written grounded answer |

Optional fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `expected_citation_required` | boolean | Whether grounded citation behavior is required |
| `expected_failure_mode` | string | Future-facing tag for unsupported-claim or retrieval-miss cases |
| `notes` | string | Author note for future dataset maintainers |

### QA Categories

The expanded QA dataset covers:

- `rollout_decision`
- `factual_retrieval`
- `result_interpretation`
- `risk_guardrail`
- `business_impact`
- `insufficient_evidence`
- `legacy_rag_fallback`

The current corpus intentionally includes negative cases where a future evaluator should refuse or
qualify unsupported claims about:

- definitive statistical significance
- ROI or revenue not grounded in the report
- business impact where evidence is incomplete

### How QA Evaluation Uses The Dataset

The harness:

1. loads `data/eval/qa_dataset.json`
2. resolves each synthetic experiment ID to the ingested database UUID through
   `Experiment.config["experiment_id"]`
3. runs the Phase 1 QA flow that remains available behind `ASK_MODE=legacy_rag`
4. aggregates retrieval, citation, latency, token, and category coverage metrics
5. writes `reports/evaluation.md`

The optional RAGAS path reuses the same dataset rows, generated answers, and retrieved contexts.
Its offline-safe context metrics also map `expected_documents` into RAGAS
`reference_context_ids`.

The optional DeepEval path reuses the same dataset rows and generated answers, then maps them into
DeepEval `Golden` and `LLMTestCase` objects without changing the repository-owned question schema.

Run it locally:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run python -m packages.evals.run --embedding-provider fake --llm-provider mock --output reports/evaluation.md
```

Run the optional RAGAS report against the same dataset:

```powershell
uv sync --group eval
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run python -m packages.evals.run_ragas --embedding-provider fake --llm-provider mock --output reports/phase3/ragas_report.md --json-output reports/phase3/ragas_report.json
```

Run the optional DeepEval report against the same dataset plus the existing workflow and `/ask`
surfaces:

```powershell
uv sync --group eval
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run python -m packages.evals.run_deepeval --mode offline --embedding-provider fake --llm-provider mock --output reports/phase3/deepeval_report.md --json-output reports/phase3/deepeval_report.json
```

## Agent Workflow Evaluation Dataset

`data/eval/agent_dataset.json` is the deterministic workflow-state dataset used by
`packages.evals.run_agent`.

It is loaded by `packages.evals.agent_dataset.load_agent_evaluation_dataset`.

### Agent Dataset Schema

Required fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | Stable case identifier |
| `question` | string | Workflow prompt |
| `category` | string | Coverage bucket |
| `expected_intent` | string | Expected planner intent |
| `expected_required_agents` | list of strings | Expected routed agents |

Optional fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `expected_decision_status` | string | Expected decision artifact status |
| `expected_recommendation` | string | Expected decision recommendation |
| `expected_summary_status` | string | Expected executive summary artifact status |
| `expected_approval_status` | string | Expected approval state such as `pending`, `rejected`, or `revision_requested` |
| `expected_min_citations` | integer | Minimum expected citation count |
| `expected_failure_mode` | string | Future-facing tag for insufficient-evidence or approval-path cases |
| `notes` | string | Author note for future maintainers |

### Agent Dataset Categories

The expanded agent dataset covers:

- `lookup`
- `rollout_decision`
- `business_impact`
- `risk_guardrail`
- `approval_workflow`
- `insufficient_evidence`

These cases are deterministic and repository-local. They should remain compatible with fake
embeddings, mock LLMs, and in-process workflow fixtures.

### How Agent Evaluation Uses The Dataset

The harness:

1. loads `data/eval/agent_dataset.json`
2. runs each prompt through `build_default_agent_workflow_service()`
3. checks planner intent, required-agent routing, citation coverage, decision outputs, approval
   status, and trace completeness
4. writes `reports/agent_evaluation.md`

Run it locally:

```powershell
uv run python -m packages.evals.run_agent --dataset data/eval/agent_dataset.json --output reports/agent_evaluation.md
```

## `/ask` End-To-End Evaluation Cases

The API E2E coverage is code-defined in `packages/evals/agent_e2e.py`.

This layer is not JSON-backed today because it validates the full `/ask` response contract, route
selection, fallback behavior, and structured artifacts directly.

Current E2E coverage includes:

- default `agent_workflow` decision-support cases
- executive-summary cases
- lookup-only cases
- risk-only and business-impact-only cases
- rejected and revision-requested approval scenarios
- insufficient-evidence decision scenarios
- `legacy_rag` fallback behavior
- structured failure surfacing

Run it locally:

```powershell
uv run python -m packages.evals.run_agent_e2e --output reports/agent_e2e_evaluation.md
```

## DeepEval Evaluation Surfaces

`packages.evals.run_deepeval` is an additive adapter layer over the existing evaluation assets.

It currently evaluates two explicit scopes:

- response evaluation for `legacy_rag` QA samples and final `/ask` responses
- workflow evaluation for deterministic `AgentWorkflowService` cases

Offline-safe deterministic metrics include:

- citation coverage
- response field completeness
- `legacy_rag` fallback compatibility
- error-state correctness
- routing accuracy
- decision status match
- approval status match
- summary status match
- trace completeness
- unsupported-claim avoidance for incomplete-evidence cases

Judge-based metrics remain opt-in:

- `answer_relevancy`
- `faithfulness`
- `hallucination`
- `contextual_relevancy`

The default offline mode never requires network calls or live model credentials. Judge mode is
explicit and uses the same repository-owned cases, but it only runs when judge configuration is
supplied directly.

## Phase 3 Baseline

The aggregate deterministic baseline combines all three evaluation surfaces:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run python -m packages.evals.run_baseline --embedding-provider fake --llm-provider mock --output reports/phase3/baseline_report.md
```

This writes:

- `reports/evaluation.md`
- `reports/agent_evaluation.md`
- `reports/agent_e2e_evaluation.md`
- `reports/phase3/baseline_report.md`

The optional DeepEval command writes:

- `reports/phase3/deepeval_report.md`
- `reports/phase3/deepeval_report.json`

## How To Add Future Cases

When adding QA cases:

- stay tied to the existing synthetic experiment corpus
- prefer grounded prompts over invented business facts
- add `expected_failure_mode` when the case exists to catch unsupported claims
- keep `expected_documents` and `expected_keywords` small and specific

When adding agent dataset cases:

- choose one primary category per case
- only set optional expectation fields that the current harness can validate cleanly
- keep approval expectations aligned with the deterministic workflow fixture behavior

When adding E2E cases:

- add them in `packages/evals/agent_e2e.py`
- prefer the smallest contract assertion that proves the route or artifact behavior
- keep `legacy_rag` compatibility explicit when the question is meant to compare both modes

General guidance:

- keep cases deterministic and repository-local
- do not require live OpenAI calls
- keep DeepEval additive; do not move repository-owned truth into DeepEval-specific schemas
- do not change `/ask` production behavior just to satisfy a dataset row
- update loader or contract tests when the schema changes
