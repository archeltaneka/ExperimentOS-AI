# Agent Workflow Evaluation Report

## Summary

| Metric | Value |
| --- | ---: |
| Samples evaluated | 8 |
| Pass count | 8 |
| Fail count | 0 |
| Workflow success rate | 100.0% |
| Average workflow latency | 2.3 ms |
| Average trace completeness | 100.0% |
| Planner intent accuracy | 100.0% |
| Required agent routing accuracy | 100.0% |
| Citation coverage | 100.0% |
| Decision recommendation coverage | 100.0% |

## Per-Agent Latency

| Agent | Avg Latency (ms) |
| --- | ---: |
| planner | 0.0 |
| retrieval | 18.0 |
| experiment_analysis | 0.0 |
| business_impact | 0.1 |
| risk_assessment | 0.1 |
| decision | 0.1 |
| human_approval | 0.0 |
| executive_summary | 0.0 |

## Status Distribution

| Decision Status | Count |
| --- | ---: |
| decided | 4 |
| needs_more_data | 1 |
| not_required | 3 |

| Approval Status | Count |
| --- | ---: |
| approved | 1 |
| not_requested | 4 |
| pending | 1 |
| rejected | 1 |
| revision_requested | 1 |

## Tool Usage

- Total tool calls: 25
- Total tool failures: 0
- Average tool calls per sample: 3.12

## Sample Results

| ID | Category | Intent | Routing | Citations | Recommendation | Workflow | Pass | Error |
| --- | --- | --- | ---: | ---: | --- | --- | --- | --- |
| lookup-payment | lookup | experiment_lookup | 100.0% | 100.0% | unknown | success | yes |  |
| decision-loyalty-rollout | rollout_decision | decision_support | 100.0% | 100.0% | rollout | success | yes |  |
| decision-pricing-do-not-rollout | rollout_decision | decision_support | 100.0% | 100.0% | do_not_rollout | success | yes |  |
| summary-checkout-pending | approval_workflow | executive_summary | 100.0% | 100.0% | rollout | success | yes |  |
| summary-loyalty-revision-requested | approval_workflow | executive_summary | 100.0% | 100.0% | rollout | success | yes |  |
| risk-search-filters | risk_guardrail | risk_assessment | 100.0% | 100.0% | unknown | success | yes |  |
| impact-search-ranking | business_impact | business_impact | 100.0% | 100.0% | unknown | success | yes |  |
| decision-premium-needs-more-data | insufficient_evidence | decision_support | 100.0% | 100.0% | needs_more_data | success | yes |  |

## Failure Cases

No failure cases were recorded.
