# Agent Workflow E2E Evaluation Report

## Summary

- Total test/eval cases: 7
- Pass/fail summary: 7 passed, 0 failed
- Default agent workflow coverage: 100.0%
- Legacy fallback coverage: 100.0%
- Intent accuracy: 100.0%
- Required agent routing accuracy: 100.0%
- Citation coverage: 100.0%
- Decision coverage: 100.0%
- Executive summary coverage: 100.0%
- Approval status coverage: 100.0%
- Average workflow latency: 9.7 ms

## Case Results

| Case | Mode | Status | Intent | Pass | Failures |
| --- | --- | ---: | --- | --- | --- |
| decision-loyalty-default | agent_workflow | 200 | decision_support | yes |  |
| summary-payment-default | agent_workflow | 200 | executive_summary | yes |  |
| lookup-hotel-default | agent_workflow | 200 | experiment_lookup | yes |  |
| risk-checkout-default | agent_workflow | 200 | risk_assessment | yes |  |
| impact-search-default | agent_workflow | 200 | business_impact | yes |  |
| legacy-fallback | legacy_rag | 200 | None | yes |  |
| failure-default | agent_workflow | 502 |  | yes |  |

## Known Limitations

- The E2E evaluator uses deterministic fake workflow and legacy QA backends rather than the live database-backed retrieval path.
- Assertions are structural and intentionally avoid exact prose matching.
- Failure-path coverage validates structured API surfacing, not downstream recovery behavior.

## Phase 3 Next Steps

- Add causal inference once the Phase 2 contract is stable.
- Add LLM-as-judge only after deterministic regression coverage is mature.
- Expand database-backed integrated evaluation beyond fake workflow fixtures.
