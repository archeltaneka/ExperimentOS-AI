# Phase 3 Reliability Baseline

Phase 3 starts from the repository's current deterministic evaluation and observability surfaces.
The goal of this baseline is to measure what ExperimentOS AI already knows about quality while
keeping the default local baseline stable, even as optional tooling such as RAGAS and DeepEval is
added beside it.

## Current Evaluation Capabilities

### Phase 1 RAG Evaluation

Current QA reliability measurement is provided by the offline evaluation harness:

- entrypoint: `packages.evals.run`
- dataset: `data/eval/qa_dataset.json`
- output: `reports/evaluation.md`
- path under test: `legacy_rag` via `QuestionAnsweringService`

What it measures today:

- retrieval success rate
- citation coverage
- retrieval latency
- LLM latency
- similarity averages
- token and estimated cost reporting
- prompt provenance for prompt-backed `legacy_rag` responses
- category coverage across rollout, risk, business-impact, insufficient-evidence, and legacy cases

What it does not measure directly today:

- factual grounding as a first-class score
- hallucination risk
- routing accuracy
- decision quality
- trace completeness
- longitudinal regression stability

### Optional RAGAS Evaluation

Phase 3 now also exposes an additive RAGAS report:

- entrypoint: `packages.evals.run_ragas`
- dataset: `data/eval/qa_dataset.json`
- outputs:
  - `reports/phase3/ragas_report.md`
  - `reports/phase3/ragas_report.json`
- path under test: the existing `legacy_rag` QA evaluation flow reused through
  `packages.evals.run.build_evaluation_run`

What it measures safely by default:

- ID-based context precision from retrieved vs expected document IDs
- ID-based context recall from retrieved vs expected document IDs
- per-case metric reporting over the repository-owned QA dataset
- explicit skipped-metric reporting when judge-backed metrics are not configured

What remains opt-in:

- judge-LLM `context_precision`
- judge-LLM `context_recall`
- judge-LLM `faithfulness`
- judge-LLM plus embeddings `answer_relevancy`

This keeps CI and default local runs free from unintended live OpenAI or Gemini calls.

### Optional DeepEval Evaluation

Phase 3 now also exposes an additive DeepEval report:

- entrypoint: `packages.evals.run_deepeval`
- datasets and surfaces:
  - `data/eval/qa_dataset.json`
  - `data/eval/agent_dataset.json`
  - code-defined `/ask` E2E cases from `packages.evals.agent_e2e`
- outputs:
  - `reports/phase3/deepeval_report.md`
  - `reports/phase3/deepeval_report.json`
- paths under test:
  - `legacy_rag` QA responses
  - default `agent_workflow` final `/ask` responses
  - deterministic `AgentWorkflowService` state outputs

What it measures safely by default:

- deterministic citation coverage
- response field completeness
- `legacy_rag` fallback compatibility
- error-state correctness
- routing accuracy
- decision status match
- approval status match
- summary status match
- trace completeness
- unsupported-claim avoidance for incomplete-evidence cases
- explicit skipped-metric reporting for judge-based metrics

What remains opt-in:

- judge-based `answer_relevancy`
- judge-based `faithfulness`
- judge-based `hallucination`
- judge-based `contextual_relevancy`

Current DeepEval integration notes:

- it keeps ExperimentOS-owned datasets and result models as the source of truth
- it does not change the default baseline command or make DeepEval a production dependency
- offline mode does not invoke live providers
- judge mode is explicit and fails fast when judge configuration or credentials are missing
- no Confident AI cloud integration, tracing, or observability is enabled yet

### Phase 2 Agent Evaluation

Current workflow-state measurement is provided by the agent evaluator:

- entrypoint: `packages.evals.run_agent`
- dataset: `data/eval/agent_dataset.json`
- output: `reports/agent_evaluation.md`
- path under test: `AgentWorkflowService` and the LangGraph workflow

What it measures today:

- workflow success rate
- planner intent accuracy
- required-agent routing accuracy
- citation coverage
- recommendation coverage
- approval-status coverage
- trace completeness
- per-agent latency
- tool call and tool failure counts

Current limitations:

- it validates a deterministic in-process workflow harness rather than the live `/ask` route
- it does not score factual grounding or hallucination risk directly
- it is better at structural correctness than prose-quality evaluation

### Phase 2 API End-to-End Evaluation

Current API-level validation is provided by the `/ask` E2E evaluator:

- entrypoint: `packages.evals.run_agent_e2e`
- output: `reports/agent_e2e_evaluation.md`
- path under test: `POST /ask` in default `agent_workflow` mode and `ASK_MODE=legacy_rag`

What it measures today:

- default agent workflow coverage
- legacy fallback coverage
- intent accuracy
- routing accuracy
- citation coverage
- decision coverage
- executive summary coverage
- approval status coverage
- average workflow latency

Current limitations:

- it uses deterministic fake workflow and legacy QA backends instead of the live DB-backed
  retrieval path
- it validates response structure rather than exact prose quality
- it does not expose external traces or telemetry exporters

## Current Workflow Observability

Current workflow observability is local and repository-owned:

- `packages/agents/observability.py` derives structured workflow observations from final
  `AgentState`
- `/ask` returns `agent_trace` and `agent_metrics` in default `agent_workflow` mode
- agent evaluation reports summarize trace completeness, per-node latency, and tool activity

This is enough to support deterministic local inspection, but it is not yet an external
observability stack.

## Current Prompt Registry Coverage

Phase 3 now also has a repository-owned prompt registry for the prompt-backed QA path:

- entrypoint: `packages.llm.prompt_registry`
- CLI: `packages.llm.prompt_registry_cli`
- compatibility facade: `packages.llm.prompts`

Current registered prompts:

- `rag.answer`
  - active version: `1`
  - runtime use: yes, `legacy_rag`
- `rag.decision`
  - active version: `1`
  - runtime use: no, compatibility helper only
- `rag.summary`
  - active version: `1`
  - runtime use: no, compatibility helper only

Prompt provenance coverage today:

- `QuestionAnsweringService` responses include `prompt_id` and `prompt_version` when a prompt is
  rendered
- `POST /ask` exposes `prompt_metadata` only for `legacy_rag`
- offline QA evaluation samples and reports carry prompt provenance when available
- deterministic `agent_workflow` remains intentionally prompt-free

## Current Prompt Regression Coverage

Phase 3 now also includes a deterministic prompt-regression workflow:

- entrypoint: `packages.evals.run_prompt_regression`
- outputs:
  - `reports/phase3/prompt_regression.md`
  - `reports/phase3/prompt_regression.json`
- prompt surface under test: `rag.answer`
- runtime paths under test:
  - `legacy_rag` QA evaluation cases
  - prompt-backed `legacy_rag` `/ask` compatibility through the ask adapter

What prompt regression measures today:

- prompt rendering success across versions
- answer generation presence
- expected keyword coverage
- document-reference coverage in deterministic offline outputs
- retrieval consistency between baseline and candidate runs
- legacy fallback response compatibility
- offline-safe RAGAS and DeepEval deltas over the reused evaluation surfaces

What it intentionally does not do yet:

- prompt A/B testing
- automatic prompt optimization
- CI enforcement
- prompt coverage for deterministic `agent_workflow`

## Current API Integration Coverage

The API layer already has deterministic integration-style coverage for:

- default `agent_workflow` routing
- `legacy_rag` fallback behavior
- decision-support responses
- executive-summary responses
- retrieval-only lookup behavior
- structured error handling
- `agent_trace`, `agent_metrics`, and approval-status surfacing

Those checks live mainly in `tests/test_api_ask.py` and `packages/evals/agent_e2e.py`.

## Quality Dimensions To Track In Phase 3

Phase 3 should track these dimensions consistently across local reports and later CI gates:

- retrieval quality
- citation coverage
- factual grounding
- hallucination risk
- routing accuracy
- decision quality
- trace completeness
- latency/runtime
- regression stability

## Known Gaps At The Baseline

- there is no single threshold policy yet for deciding pass or fail across all evaluation surfaces
- there is no direct hallucination or factual-grounding score in the default deterministic baseline
- the aggregate baseline report does not yet diff failures or regressions across runs
- there is no external trace export or observability backend integrated yet
- there is no CI enforcement yet for deterministic AI quality signals
- judge-backed RAGAS metrics are optional and not enabled by default
- judge-backed DeepEval metrics are optional and not enabled by default
- prompt regression is available for `legacy_rag`, but prompt-backed `agent_workflow` surfaces do
  not exist yet

## What Phase 3 Will Improve

Phase 3 should add reliability in this order:

1. establish one aggregate baseline command and report
2. keep expanding deterministic datasets whenever new regressions or failure modes are discovered
3. keep deterministic prompt-regression comparisons on `legacy_rag` prompts before introducing
   prompt A/B testing
4. add deterministic regression checks around groundedness and unsupported claims
5. define threshold policy before CI gates
6. add optional external evaluation and observability tools without replacing the local baseline

## Running The Baseline

The Phase 3 baseline should be run with deterministic local settings:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run python -m packages.evals.run_baseline --embedding-provider fake --llm-provider mock --output reports/phase3/baseline_report.md
```

This command coordinates the existing local evaluations and writes:

- `reports/evaluation.md`
- `reports/agent_evaluation.md`
- `reports/agent_e2e_evaluation.md`
- `reports/phase3/baseline_report.md`

## Why The Baseline Stays Separate

The baseline intentionally stays deterministic and repository-owned.

Even with optional RAGAS and DeepEval support available, the repository still needs one local
source of truth for:

- what is already measured
- what is missing
- which metrics are safe for CI later
- which behaviors must remain backward compatible, especially `legacy_rag` fallback and default
  `agent_workflow`

Framework comparison:

- Custom evaluation:
  - project-specific deterministic assertions
  - routing, decision, approval, trace, fallback, and citation validation
- RAGAS:
  - optional RAG-focused retrieval and answer-quality metrics over the QA harness
- DeepEval:
  - standardized `Golden` and `LLMTestCase` adapters over the existing datasets and `/ask` cases
  - offline deterministic checks plus explicit judge-based metrics

RAGAS and DeepEval now help extend retrieval and answer-quality reporting, but they remain
additive rather than the primary pass/fail baseline.
