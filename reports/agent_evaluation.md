# Agent Workflow Evaluation Report

## Summary

| Metric | Value |
| --- | ---: |
| Samples evaluated | 3 |
| Pass count | 3 |
| Fail count | 0 |
| Workflow success rate | 100.0% |
| Average workflow latency | 21.1 ms |
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
| business_impact | 1.0 |
| risk_assessment | 0.4 |
| decision | 16.2 |
| human_approval | 0.0 |
| executive_summary | 0.1 |

## Status Distribution

| Decision Status | Count |
| --- | ---: |
| decided | 2 |
| not_required | 1 |

| Approval Status | Count |
| --- | ---: |
| approved | 1 |
| not_requested | 1 |
| pending | 1 |

## Tool Usage

- Total tool calls: 10
- Total tool failures: 0
- Average tool calls per sample: 3.33

## Sample Results

| ID | Intent | Routing | Citations | Recommendation | Workflow | Pass | Error |
| --- | --- | ---: | ---: | --- | --- | --- | --- |
| lookup-payment | experiment_lookup | 100.0% | 100.0% | unknown | success | yes |  |
| decision-payment | decision_support | 100.0% | 100.0% | rollout | success | yes |  |
| summary-checkout | executive_summary | 100.0% | 100.0% | rollout | success | yes |  |

## Failure Cases

No failure cases were recorded.
