# Prompt Regression Report

- Prompt ID: rag.answer
- Baseline version: 1
- Candidate version: 1
- Dataset: data\eval\qa_dataset.json
- Cases run: 63
- Regressions: 0
- Improvements: 0
- Unchanged: 63
- Failures: 0
- Pass/fail: pass

## Metric Deltas

| Metric | Baseline | Candidate | Delta | Regressions | Improvements |
| --- | ---: | ---: | ---: | ---: | ---: |
| answer_generated | 1.000 | 1.000 | 0.000 | 0 | 0 |
| citation_coverage | 1.000 | 1.000 | 0.000 | 0 | 0 |
| document_reference_coverage | 1.000 | 1.000 | 0.000 | 0 | 0 |
| forbidden_hallucination_markers | 1.000 | 1.000 | 0.000 | 0 | 0 |
| keyword_coverage | 0.051 | 0.051 | 0.000 | 0 | 0 |
| legacy_fallback_compatibility | 1.000 | 1.000 | 0.000 | 0 | 0 |
| prompt_rendering_success | 1.000 | 1.000 | 0.000 | 0 | 0 |
| retrieval_consistency | 1.000 | 1.000 | 0.000 | 0 | 0 |
| structured_output_validity | 1.000 | 1.000 | 0.000 | 0 | 0 |

## Case Results

- `exp-001-rollout-decision` (legacy_rag): unchanged
- `exp-001-factual-retrieval` (legacy_rag): unchanged
- `exp-001-result-interpretation` (legacy_rag): unchanged
- `exp-001-risk-guardrail` (legacy_rag): unchanged
- `exp-001-business-impact` (legacy_rag): unchanged
- `exp-001-insufficient-evidence` (legacy_rag): unchanged
- `exp-002-rollout-decision` (legacy_rag): unchanged
- `exp-002-factual-retrieval` (legacy_rag): unchanged
- `exp-002-result-interpretation` (legacy_rag): unchanged
- `exp-002-risk-guardrail` (legacy_rag): unchanged
- `exp-002-business-impact` (legacy_rag): unchanged
- `exp-002-insufficient-evidence` (legacy_rag): unchanged
- `exp-003-rollout-decision` (legacy_rag): unchanged
- `exp-003-factual-retrieval` (legacy_rag): unchanged
- `exp-003-result-interpretation` (legacy_rag): unchanged
- `exp-003-risk-guardrail` (legacy_rag): unchanged
- `exp-003-business-impact` (legacy_rag): unchanged
- `exp-003-insufficient-evidence` (legacy_rag): unchanged
- `exp-004-rollout-decision` (legacy_rag): unchanged
- `exp-004-factual-retrieval` (legacy_rag): unchanged
- `exp-004-result-interpretation` (legacy_rag): unchanged
- `exp-004-risk-guardrail` (legacy_rag): unchanged
- `exp-004-business-impact` (legacy_rag): unchanged
- `exp-004-insufficient-evidence` (legacy_rag): unchanged
- `exp-005-rollout-decision` (legacy_rag): unchanged
- `exp-005-factual-retrieval` (legacy_rag): unchanged
- `exp-005-result-interpretation` (legacy_rag): unchanged
- `exp-005-risk-guardrail` (legacy_rag): unchanged
- `exp-005-business-impact` (legacy_rag): unchanged
- `exp-005-insufficient-evidence` (legacy_rag): unchanged
- `exp-006-rollout-decision` (legacy_rag): unchanged
- `exp-006-factual-retrieval` (legacy_rag): unchanged
- `exp-006-result-interpretation` (legacy_rag): unchanged
- `exp-006-risk-guardrail` (legacy_rag): unchanged
- `exp-006-business-impact` (legacy_rag): unchanged
- `exp-006-insufficient-evidence` (legacy_rag): unchanged
- `exp-007-rollout-decision` (legacy_rag): unchanged
- `exp-007-factual-retrieval` (legacy_rag): unchanged
- `exp-007-result-interpretation` (legacy_rag): unchanged
- `exp-007-risk-guardrail` (legacy_rag): unchanged
- `exp-007-business-impact` (legacy_rag): unchanged
- `exp-007-insufficient-evidence` (legacy_rag): unchanged
- `exp-008-rollout-decision` (legacy_rag): unchanged
- `exp-008-factual-retrieval` (legacy_rag): unchanged
- `exp-008-result-interpretation` (legacy_rag): unchanged
- `exp-008-risk-guardrail` (legacy_rag): unchanged
- `exp-008-business-impact` (legacy_rag): unchanged
- `exp-008-insufficient-evidence` (legacy_rag): unchanged
- `exp-009-rollout-decision` (legacy_rag): unchanged
- `exp-009-factual-retrieval` (legacy_rag): unchanged
- `exp-009-result-interpretation` (legacy_rag): unchanged
- `exp-009-risk-guardrail` (legacy_rag): unchanged
- `exp-009-business-impact` (legacy_rag): unchanged
- `exp-009-insufficient-evidence` (legacy_rag): unchanged
- `exp-010-rollout-decision` (legacy_rag): unchanged
- `exp-010-factual-retrieval` (legacy_rag): unchanged
- `exp-010-result-interpretation` (legacy_rag): unchanged
- `exp-010-risk-guardrail` (legacy_rag): unchanged
- `exp-010-business-impact` (legacy_rag): unchanged
- `exp-010-insufficient-evidence` (legacy_rag): unchanged
- `exp-001-legacy-rag-lookup` (legacy_rag): unchanged
- `exp-004-legacy-rag-lookup` (legacy_rag): unchanged
- `legacy-fallback` (legacy_rag.ask): unchanged

## RAGAS Comparison

| Metric | Baseline | Candidate | Delta |
| --- | ---: | ---: | ---: |
| id_based_context_precision | 1.000 | 1.000 | 0.000 |
| id_based_context_recall | 1.000 | 1.000 | 0.000 |

Notes:
- Judge-backed metrics are opt-in. This run used no judge LLM, so model-backed RAGAS metrics were skipped by design.

## DEEPEVAL Comparison

| Metric | Baseline | Candidate | Delta |
| --- | ---: | ---: | ---: |
| citation_coverage | 1.000 | 1.000 | 0.000 |
| fallback_compatibility | 1.000 | 1.000 | 0.000 |
| response_field_completeness | 1.000 | 1.000 | 0.000 |

Notes:
- DeepEval remains additive; the existing custom evaluation harnesses and RAGAS stay intact.
- No Confident AI cloud integration, tracing, or observability hooks are enabled in this adapter.
- Workflow deterministic metrics remain ExperimentOS-owned even when DeepEval is installed.
- Unsupported-claim avoidance is a deterministic heuristic, not a semantic judge score.
- Offline mode skips judge-based metrics by design and never invokes a live model.
