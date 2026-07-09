# Phase 3 Reliability Baseline Report

- Generated at: 2026-07-09T10:18:36.039011Z
- Overall status: pass

## Evaluation Status

| Evaluation | Status | Reason | Dataset | Report |
| --- | --- | --- | --- | --- |
| RAG Evaluation | pass | completed without sample errors | data\eval\qa_dataset.json | `reports\evaluation.md` |
| Agent Workflow Evaluation | pass | all deterministic workflow cases passed | data\eval\agent_dataset.json | `reports\agent_evaluation.md` |
| Agent Workflow E2E Evaluation | pass | all deterministic API cases passed | n/a | `reports\agent_e2e_evaluation.md` |

## Commands Run

- `uv run python -m packages.evals.run --dataset data\eval\qa_dataset.json --output reports\evaluation.md --top-k 5 --embedding-provider ollama --embedding-model nomic-embed-text --llm-provider ollama --llm-model qwen2.5:7b`
- `uv run python -m packages.evals.run_agent --dataset data\eval\agent_dataset.json --output reports\agent_evaluation.md`
- `uv run python -m packages.evals.run_agent_e2e --output reports\agent_e2e_evaluation.md`

## RAG Evaluation

- Status: pass
- Reason: completed without sample errors
- Dataset: data\eval\qa_dataset.json
- Report path: `reports\evaluation.md`

### Key Metrics

- Questions evaluated: 40
- Retrieval success rate: 100.0%
- Average citation coverage: 100.0%
- Average retrieval latency: 1020.7 ms
- Average LLM latency: 4834.0 ms

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

- Samples evaluated: 3
- Pass/fail summary: 3 passed, 0 failed
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

- Total test/eval cases: 7
- Pass/fail summary: 7 passed, 0 failed
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

## Known Gaps

- No threshold policy exists yet for turning these metrics into CI gates.
- No direct hallucination or factuality score is computed yet.
- No external tracing or observability export is enabled yet.

## Next Recommended Reliability Work

- Expand the evaluation datasets with more edge cases and insufficient-evidence coverage.
- Add deterministic hallucination and factual grounding checks on top of the existing reports.
- Define a threshold policy before introducing CI quality gates.
