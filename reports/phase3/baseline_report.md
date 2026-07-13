# Phase 3 Reliability Baseline Report

- Generated at: 2026-07-13T00:30:11.348095Z
- Overall status: fail

## Evaluation Status

| Evaluation | Status | Reason | Dataset | Report |
| --- | --- | --- | --- | --- |
| RAG Evaluation | pass | completed without sample errors | data\eval\qa_dataset.json | `reports\evaluation.md` |
| Agent Workflow Evaluation | pass | all deterministic workflow cases passed | data\eval\agent_dataset.json | `reports\agent_evaluation.md` |
| Agent Workflow E2E Evaluation | pass | all deterministic API cases passed | n/a | `reports\agent_e2e_evaluation.md` |
| Factuality Evaluation | warning | Some cases could not be parsed conservatively into explicit claims. | data\eval\qa_dataset.json, data\eval\agent_dataset.json | `reports\phase3\factuality_report.md` |

## Commands Run

- `uv run python -m packages.evals.run --dataset data\eval\qa_dataset.json --output reports\evaluation.md --top-k 5 --embedding-provider fake --embedding-model fake --llm-provider mock --llm-model mock`
- `uv run python -m packages.evals.run_agent --dataset data\eval\agent_dataset.json --output reports\agent_evaluation.md`
- `uv run python -m packages.evals.run_agent_e2e --output reports\agent_e2e_evaluation.md`
- `uv run python -m packages.evals.run_factuality --dataset data\eval\qa_dataset.json --agent-dataset data\eval\agent_dataset.json --target all --mode offline --output reports\phase3\factuality_report.md --json-output reports\phase3\factuality_report.json --top-k 5 --embedding-provider fake --llm-provider mock`

## RAG Evaluation

- Status: pass
- Reason: completed without sample errors
- Dataset: data\eval\qa_dataset.json
- Report path: `reports\evaluation.md`

### Key Metrics

- Questions evaluated: 62
- Retrieval success rate: 100.0%
- Average citation coverage: 100.0%
- Average retrieval latency: 50.9 ms
- Average LLM latency: 0.0 ms

### Missing Metrics

- factual grounding
- hallucination risk
- routing accuracy
- decision quality
- trace completeness
- regression stability

### Known Limitations

- The Phase 1 QA harness measures retrieval and citation behavior but does not score factual grounding directly.
- The QA harness uses the legacy_rag path rather than the default agent_workflow path.

## Agent Workflow Evaluation

- Status: pass
- Reason: all deterministic workflow cases passed
- Dataset: data\eval\agent_dataset.json
- Report path: `reports\agent_evaluation.md`

### Key Metrics

- Samples evaluated: 8
- Pass/fail summary: 8 passed, 0 failed
- Workflow success rate: 100.0%
- Routing accuracy: 100.0%
- Trace completeness: 100.0%

### Missing Metrics

- factual grounding
- hallucination risk
- regression stability

### Known Limitations

- The agent workflow evaluator uses a deterministic in-process workflow service rather than the live FastAPI /ask route.
- The agent workflow evaluator measures structural workflow quality, not prose quality.

## Agent Workflow E2E Evaluation

- Status: pass
- Reason: all deterministic API cases passed
- Dataset: n/a
- Report path: `reports\agent_e2e_evaluation.md`

### Key Metrics

- Total test/eval cases: 11
- Pass/fail summary: 11 passed, 0 failed
- Default agent workflow coverage: 100.0%
- Legacy fallback coverage: 100.0%
- Approval status coverage: 100.0%

### Missing Metrics

- database-backed retrieval quality
- factual grounding
- hallucination risk
- regression stability

### Known Limitations

- The E2E evaluator uses deterministic fake workflow and legacy QA backends rather than the live database-backed retrieval path.
- Assertions are structural and intentionally avoid exact prose matching.
- Failure-path coverage validates structured API surfacing, not downstream recovery behavior.

## Factuality Evaluation

- Status: warning
- Reason: Some cases could not be parsed conservatively into explicit claims.
- Dataset: data\eval\qa_dataset.json, data\eval\agent_dataset.json
- Report path: `reports\phase3\factuality_report.md`

### Key Metrics

- Cases evaluated: 70
- Policy result: warning
- Critical findings: 0
- Citation failures: 0
- Unsupported numerical claims: 0

### Missing Metrics

- production blocking
- automatic answer repair
- human fact-check workflow

### Known Limitations

- Deterministic checks are conservative and do not prove universal factual correctness.
- Numerical and workflow assertions remain deterministic; judge metrics are optional.
- Offline mode never invokes a live provider.

## Known Gaps

- No threshold policy exists yet for turning these metrics into CI gates.
- LangSmith and Phoenix tracing are optional external sinks; internal ExperimentOS traces remain authoritative and production alerting is still absent.
- Cross-service distributed tracing remains out of scope.

## Registered Prompts

| Prompt ID | Active Version | Status |
| --- | --- | --- |
| rag.answer | 1 | active |
| rag.decision | 1 | experimental |
| rag.summary | 1 | experimental |

## Prompt Provenance

- legacy_rag responses expose prompt_id and prompt_version metadata.
- offline QA evaluation samples and reports carry prompt provenance when available.
- agent_workflow remains prompt-free until an LLM-backed surface exists.

## Prompt Regression Coverage

- Prompt regression compares prompt versions over the existing legacy_rag QA dataset.
- Prompt regression reuses a prompt-backed legacy /ask surface through the existing ask adapter.
- Offline mode stays deterministic by default and does not require a live provider.

## Prompt Experiment Framework

- Offline prompt experiment framework is available for rag.answer only.
- Deterministic assignment is reproducible and exposure tracking is prompt-use based.
- Runtime experimentation remains disabled by default and public /ask behavior is unchanged.

## Remaining Prompt Risks

- Only legacy_rag is prompt-backed today; agent_workflow remains deterministic application logic.
- Prompt regression focuses on structural and evidence-grounded deltas rather than exact prose matching.

## Next Recommended Reliability Work

- Define category-specific threshold policies before introducing CI quality gates.
- Add report-level regression diffs so future baseline runs can compare changed failure cases directly.
- Expand observability coverage from local and evaluation runs into deployed service operations.
