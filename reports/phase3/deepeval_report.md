# DeepEval Evaluation Report

## Summary

- Generated at: 2026-07-10T02:02:57.365136Z
- Evaluation mode: offline
- DeepEval available: yes
- DeepEval version: 4.0.7
- Response cases: 73
- Workflow cases: 8
- External judge used: no
- Judge provider/model: none / none
- Metrics requested: citation_coverage, response_field_completeness, error_state_correctness, fallback_compatibility, routing_accuracy, decision_status_match, approval_status_match, summary_status_match, trace_completeness, unsupported_claim_avoidance, answer_relevancy, faithfulness, hallucination, contextual_relevancy
- Metrics executed: citation_coverage, response_field_completeness, error_state_correctness, fallback_compatibility, routing_accuracy, decision_status_match, approval_status_match, summary_status_match, trace_completeness, unsupported_claim_avoidance
- Metrics skipped: answer_relevancy, faithfulness, hallucination, contextual_relevancy

## Aggregate Scores

| Metric | Type | Avg Score | Passed | Failed | Skipped |
| --- | --- | ---: | ---: | ---: | ---: |
| answer_relevancy | judge |  | 0 | 0 | 73 |
| approval_status_match | deterministic | 1.000 | 7 | 0 | 0 |
| citation_coverage | deterministic | 1.000 | 81 | 0 | 0 |
| contextual_relevancy | judge |  | 0 | 0 | 73 |
| decision_status_match | deterministic | 1.000 | 5 | 0 | 0 |
| error_state_correctness | deterministic | 1.000 | 1 | 0 | 0 |
| faithfulness | judge |  | 0 | 0 | 73 |
| fallback_compatibility | deterministic | 1.000 | 1 | 0 | 0 |
| hallucination | judge |  | 0 | 0 | 73 |
| response_field_completeness | deterministic | 1.000 | 72 | 0 | 0 |
| routing_accuracy | deterministic | 1.000 | 8 | 0 | 0 |
| summary_status_match | deterministic | 1.000 | 5 | 0 | 0 |
| trace_completeness | deterministic | 1.000 | 8 | 0 | 0 |
| unsupported_claim_avoidance | deterministic | 1.000 | 1 | 0 | 0 |

## Category Results

| Category | Pass | Fail | Skip |
| --- | ---: | ---: | ---: |
| agent_failure | 2 | 0 | 4 |
| approval_workflow | 12 | 0 | 0 |
| business_impact | 26 | 0 | 44 |
| decision_support | 6 | 0 | 12 |
| executive_summary | 4 | 0 | 8 |
| experiment_lookup | 4 | 0 | 8 |
| factual_retrieval | 20 | 0 | 40 |
| insufficient_evidence | 27 | 0 | 40 |
| legacy_fallback | 3 | 0 | 4 |
| legacy_rag_fallback | 4 | 0 | 8 |
| lookup | 3 | 0 | 0 |
| result_interpretation | 20 | 0 | 40 |
| risk_assessment | 2 | 0 | 4 |
| risk_guardrail | 24 | 0 | 40 |
| rollout_decision | 32 | 0 | 40 |

## Case Metrics

| Case | Category | Scope | Metric | Score | Status | Detail |
| --- | --- | --- | --- | ---: | --- | --- |
| legacy_rag::exp-001-rollout-decision | rollout_decision | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-001-factual-retrieval | factual_retrieval | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-001-result-interpretation | result_interpretation | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-001-risk-guardrail | risk_guardrail | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-001-business-impact | business_impact | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-001-insufficient-evidence | insufficient_evidence | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-002-rollout-decision | rollout_decision | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-002-factual-retrieval | factual_retrieval | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-002-result-interpretation | result_interpretation | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-002-risk-guardrail | risk_guardrail | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-002-business-impact | business_impact | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-002-insufficient-evidence | insufficient_evidence | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-003-rollout-decision | rollout_decision | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-003-factual-retrieval | factual_retrieval | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-003-result-interpretation | result_interpretation | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-003-risk-guardrail | risk_guardrail | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-003-business-impact | business_impact | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-003-insufficient-evidence | insufficient_evidence | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-004-rollout-decision | rollout_decision | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-004-factual-retrieval | factual_retrieval | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-004-result-interpretation | result_interpretation | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-004-risk-guardrail | risk_guardrail | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-004-business-impact | business_impact | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-004-insufficient-evidence | insufficient_evidence | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-005-rollout-decision | rollout_decision | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-005-factual-retrieval | factual_retrieval | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-005-result-interpretation | result_interpretation | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-005-risk-guardrail | risk_guardrail | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-005-business-impact | business_impact | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-005-insufficient-evidence | insufficient_evidence | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-006-rollout-decision | rollout_decision | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-006-factual-retrieval | factual_retrieval | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-006-result-interpretation | result_interpretation | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-006-risk-guardrail | risk_guardrail | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-006-business-impact | business_impact | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-006-insufficient-evidence | insufficient_evidence | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-007-rollout-decision | rollout_decision | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-007-factual-retrieval | factual_retrieval | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-007-result-interpretation | result_interpretation | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-007-risk-guardrail | risk_guardrail | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-007-business-impact | business_impact | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-007-insufficient-evidence | insufficient_evidence | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-008-rollout-decision | rollout_decision | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-008-factual-retrieval | factual_retrieval | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-008-result-interpretation | result_interpretation | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-008-risk-guardrail | risk_guardrail | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-008-business-impact | business_impact | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-008-insufficient-evidence | insufficient_evidence | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-009-rollout-decision | rollout_decision | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-009-factual-retrieval | factual_retrieval | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-009-result-interpretation | result_interpretation | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-009-risk-guardrail | risk_guardrail | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-009-business-impact | business_impact | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-009-insufficient-evidence | insufficient_evidence | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-010-rollout-decision | rollout_decision | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-010-factual-retrieval | factual_retrieval | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-010-result-interpretation | result_interpretation | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-010-risk-guardrail | risk_guardrail | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-010-business-impact | business_impact | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-010-insufficient-evidence | insufficient_evidence | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-001-legacy-rag-lookup | legacy_rag_fallback | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-004-legacy-rag-lookup | legacy_rag_fallback | response | citation_coverage | 1.000 | passed |  |
| agent_workflow::decision-loyalty-default | decision_support | response | citation_coverage | 1.000 | passed |  |
| agent_workflow::summary-payment-default | executive_summary | response | citation_coverage | 1.000 | passed |  |
| agent_workflow::lookup-payment-default | experiment_lookup | response | citation_coverage | 1.000 | passed |  |
| agent_workflow::lookup-hotel-default | experiment_lookup | response | citation_coverage | 1.000 | passed |  |
| agent_workflow::risk-checkout-default | risk_assessment | response | citation_coverage | 1.000 | passed |  |
| agent_workflow::decision-pricing-default | decision_support | response | citation_coverage | 1.000 | passed |  |
| agent_workflow::impact-search-default | business_impact | response | citation_coverage | 1.000 | passed |  |
| agent_workflow::decision-premium-needs-more-data | decision_support | response | citation_coverage | 1.000 | passed |  |
| agent_workflow::summary-loyalty-revision-requested | executive_summary | response | citation_coverage | 1.000 | passed |  |
| legacy_rag::legacy-fallback | legacy_fallback | response | citation_coverage | 1.000 | passed |  |
| agent_workflow::failure-default | agent_failure | response | citation_coverage | 1.000 | passed |  |
| agent_workflow::lookup-payment | lookup | workflow | citation_coverage | 1.000 | passed |  |
| agent_workflow::decision-loyalty-rollout | rollout_decision | workflow | citation_coverage | 1.000 | passed |  |
| agent_workflow::decision-pricing-do-not-rollout | rollout_decision | workflow | citation_coverage | 1.000 | passed |  |
| agent_workflow::summary-checkout-pending | approval_workflow | workflow | citation_coverage | 1.000 | passed |  |
| agent_workflow::summary-loyalty-revision-requested | approval_workflow | workflow | citation_coverage | 1.000 | passed |  |
| agent_workflow::risk-search-filters | risk_guardrail | workflow | citation_coverage | 1.000 | passed |  |
| agent_workflow::impact-search-ranking | business_impact | workflow | citation_coverage | 1.000 | passed |  |
| agent_workflow::decision-premium-needs-more-data | insufficient_evidence | workflow | citation_coverage | 1.000 | passed |  |
| legacy_rag::exp-001-rollout-decision | rollout_decision | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-001-factual-retrieval | factual_retrieval | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-001-result-interpretation | result_interpretation | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-001-risk-guardrail | risk_guardrail | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-001-business-impact | business_impact | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-001-insufficient-evidence | insufficient_evidence | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-002-rollout-decision | rollout_decision | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-002-factual-retrieval | factual_retrieval | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-002-result-interpretation | result_interpretation | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-002-risk-guardrail | risk_guardrail | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-002-business-impact | business_impact | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-002-insufficient-evidence | insufficient_evidence | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-003-rollout-decision | rollout_decision | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-003-factual-retrieval | factual_retrieval | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-003-result-interpretation | result_interpretation | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-003-risk-guardrail | risk_guardrail | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-003-business-impact | business_impact | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-003-insufficient-evidence | insufficient_evidence | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-004-rollout-decision | rollout_decision | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-004-factual-retrieval | factual_retrieval | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-004-result-interpretation | result_interpretation | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-004-risk-guardrail | risk_guardrail | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-004-business-impact | business_impact | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-004-insufficient-evidence | insufficient_evidence | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-005-rollout-decision | rollout_decision | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-005-factual-retrieval | factual_retrieval | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-005-result-interpretation | result_interpretation | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-005-risk-guardrail | risk_guardrail | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-005-business-impact | business_impact | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-005-insufficient-evidence | insufficient_evidence | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-006-rollout-decision | rollout_decision | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-006-factual-retrieval | factual_retrieval | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-006-result-interpretation | result_interpretation | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-006-risk-guardrail | risk_guardrail | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-006-business-impact | business_impact | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-006-insufficient-evidence | insufficient_evidence | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-007-rollout-decision | rollout_decision | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-007-factual-retrieval | factual_retrieval | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-007-result-interpretation | result_interpretation | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-007-risk-guardrail | risk_guardrail | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-007-business-impact | business_impact | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-007-insufficient-evidence | insufficient_evidence | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-008-rollout-decision | rollout_decision | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-008-factual-retrieval | factual_retrieval | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-008-result-interpretation | result_interpretation | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-008-risk-guardrail | risk_guardrail | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-008-business-impact | business_impact | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-008-insufficient-evidence | insufficient_evidence | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-009-rollout-decision | rollout_decision | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-009-factual-retrieval | factual_retrieval | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-009-result-interpretation | result_interpretation | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-009-risk-guardrail | risk_guardrail | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-009-business-impact | business_impact | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-009-insufficient-evidence | insufficient_evidence | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-010-rollout-decision | rollout_decision | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-010-factual-retrieval | factual_retrieval | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-010-result-interpretation | result_interpretation | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-010-risk-guardrail | risk_guardrail | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-010-business-impact | business_impact | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-010-insufficient-evidence | insufficient_evidence | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-001-legacy-rag-lookup | legacy_rag_fallback | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::exp-004-legacy-rag-lookup | legacy_rag_fallback | response | response_field_completeness | 1.000 | passed |  |
| agent_workflow::decision-loyalty-default | decision_support | response | response_field_completeness | 1.000 | passed |  |
| agent_workflow::summary-payment-default | executive_summary | response | response_field_completeness | 1.000 | passed |  |
| agent_workflow::lookup-payment-default | experiment_lookup | response | response_field_completeness | 1.000 | passed |  |
| agent_workflow::lookup-hotel-default | experiment_lookup | response | response_field_completeness | 1.000 | passed |  |
| agent_workflow::risk-checkout-default | risk_assessment | response | response_field_completeness | 1.000 | passed |  |
| agent_workflow::decision-pricing-default | decision_support | response | response_field_completeness | 1.000 | passed |  |
| agent_workflow::impact-search-default | business_impact | response | response_field_completeness | 1.000 | passed |  |
| agent_workflow::decision-premium-needs-more-data | decision_support | response | response_field_completeness | 1.000 | passed |  |
| agent_workflow::summary-loyalty-revision-requested | executive_summary | response | response_field_completeness | 1.000 | passed |  |
| legacy_rag::legacy-fallback | legacy_fallback | response | response_field_completeness | 1.000 | passed |  |
| agent_workflow::failure-default | agent_failure | response | error_state_correctness | 1.000 | passed |  |
| legacy_rag::legacy-fallback | legacy_fallback | response | fallback_compatibility | 1.000 | passed |  |
| agent_workflow::lookup-payment | lookup | workflow | routing_accuracy | 1.000 | passed |  |
| agent_workflow::decision-loyalty-rollout | rollout_decision | workflow | routing_accuracy | 1.000 | passed |  |
| agent_workflow::decision-pricing-do-not-rollout | rollout_decision | workflow | routing_accuracy | 1.000 | passed |  |
| agent_workflow::summary-checkout-pending | approval_workflow | workflow | routing_accuracy | 1.000 | passed |  |
| agent_workflow::summary-loyalty-revision-requested | approval_workflow | workflow | routing_accuracy | 1.000 | passed |  |
| agent_workflow::risk-search-filters | risk_guardrail | workflow | routing_accuracy | 1.000 | passed |  |
| agent_workflow::impact-search-ranking | business_impact | workflow | routing_accuracy | 1.000 | passed |  |
| agent_workflow::decision-premium-needs-more-data | insufficient_evidence | workflow | routing_accuracy | 1.000 | passed |  |
| agent_workflow::decision-loyalty-rollout | rollout_decision | workflow | decision_status_match | 1.000 | passed |  |
| agent_workflow::decision-pricing-do-not-rollout | rollout_decision | workflow | decision_status_match | 1.000 | passed |  |
| agent_workflow::summary-checkout-pending | approval_workflow | workflow | decision_status_match | 1.000 | passed |  |
| agent_workflow::summary-loyalty-revision-requested | approval_workflow | workflow | decision_status_match | 1.000 | passed |  |
| agent_workflow::decision-premium-needs-more-data | insufficient_evidence | workflow | decision_status_match | 1.000 | passed |  |
| agent_workflow::decision-loyalty-rollout | rollout_decision | workflow | approval_status_match | 1.000 | passed |  |
| agent_workflow::decision-pricing-do-not-rollout | rollout_decision | workflow | approval_status_match | 1.000 | passed |  |
| agent_workflow::summary-checkout-pending | approval_workflow | workflow | approval_status_match | 1.000 | passed |  |
| agent_workflow::summary-loyalty-revision-requested | approval_workflow | workflow | approval_status_match | 1.000 | passed |  |
| agent_workflow::risk-search-filters | risk_guardrail | workflow | approval_status_match | 1.000 | passed |  |
| agent_workflow::impact-search-ranking | business_impact | workflow | approval_status_match | 1.000 | passed |  |
| agent_workflow::decision-premium-needs-more-data | insufficient_evidence | workflow | approval_status_match | 1.000 | passed |  |
| agent_workflow::decision-loyalty-rollout | rollout_decision | workflow | summary_status_match | 1.000 | passed |  |
| agent_workflow::decision-pricing-do-not-rollout | rollout_decision | workflow | summary_status_match | 1.000 | passed |  |
| agent_workflow::summary-checkout-pending | approval_workflow | workflow | summary_status_match | 1.000 | passed |  |
| agent_workflow::summary-loyalty-revision-requested | approval_workflow | workflow | summary_status_match | 1.000 | passed |  |
| agent_workflow::decision-premium-needs-more-data | insufficient_evidence | workflow | summary_status_match | 1.000 | passed |  |
| agent_workflow::lookup-payment | lookup | workflow | trace_completeness | 1.000 | passed |  |
| agent_workflow::decision-loyalty-rollout | rollout_decision | workflow | trace_completeness | 1.000 | passed |  |
| agent_workflow::decision-pricing-do-not-rollout | rollout_decision | workflow | trace_completeness | 1.000 | passed |  |
| agent_workflow::summary-checkout-pending | approval_workflow | workflow | trace_completeness | 1.000 | passed |  |
| agent_workflow::summary-loyalty-revision-requested | approval_workflow | workflow | trace_completeness | 1.000 | passed |  |
| agent_workflow::risk-search-filters | risk_guardrail | workflow | trace_completeness | 1.000 | passed |  |
| agent_workflow::impact-search-ranking | business_impact | workflow | trace_completeness | 1.000 | passed |  |
| agent_workflow::decision-premium-needs-more-data | insufficient_evidence | workflow | trace_completeness | 1.000 | passed |  |
| agent_workflow::decision-premium-needs-more-data | insufficient_evidence | workflow | unsupported_claim_avoidance | 1.000 | passed |  |
| legacy_rag::exp-001-rollout-decision | rollout_decision | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-factual-retrieval | factual_retrieval | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-result-interpretation | result_interpretation | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-risk-guardrail | risk_guardrail | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-business-impact | business_impact | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-insufficient-evidence | insufficient_evidence | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-rollout-decision | rollout_decision | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-factual-retrieval | factual_retrieval | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-result-interpretation | result_interpretation | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-risk-guardrail | risk_guardrail | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-business-impact | business_impact | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-insufficient-evidence | insufficient_evidence | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-rollout-decision | rollout_decision | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-factual-retrieval | factual_retrieval | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-result-interpretation | result_interpretation | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-risk-guardrail | risk_guardrail | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-business-impact | business_impact | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-insufficient-evidence | insufficient_evidence | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-rollout-decision | rollout_decision | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-factual-retrieval | factual_retrieval | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-result-interpretation | result_interpretation | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-risk-guardrail | risk_guardrail | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-business-impact | business_impact | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-insufficient-evidence | insufficient_evidence | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-rollout-decision | rollout_decision | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-factual-retrieval | factual_retrieval | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-result-interpretation | result_interpretation | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-risk-guardrail | risk_guardrail | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-business-impact | business_impact | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-insufficient-evidence | insufficient_evidence | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-rollout-decision | rollout_decision | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-factual-retrieval | factual_retrieval | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-result-interpretation | result_interpretation | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-risk-guardrail | risk_guardrail | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-business-impact | business_impact | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-insufficient-evidence | insufficient_evidence | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-rollout-decision | rollout_decision | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-factual-retrieval | factual_retrieval | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-result-interpretation | result_interpretation | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-risk-guardrail | risk_guardrail | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-business-impact | business_impact | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-insufficient-evidence | insufficient_evidence | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-rollout-decision | rollout_decision | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-factual-retrieval | factual_retrieval | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-result-interpretation | result_interpretation | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-risk-guardrail | risk_guardrail | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-business-impact | business_impact | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-insufficient-evidence | insufficient_evidence | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-rollout-decision | rollout_decision | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-factual-retrieval | factual_retrieval | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-result-interpretation | result_interpretation | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-risk-guardrail | risk_guardrail | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-business-impact | business_impact | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-insufficient-evidence | insufficient_evidence | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-rollout-decision | rollout_decision | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-factual-retrieval | factual_retrieval | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-result-interpretation | result_interpretation | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-risk-guardrail | risk_guardrail | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-business-impact | business_impact | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-insufficient-evidence | insufficient_evidence | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-legacy-rag-lookup | legacy_rag_fallback | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-legacy-rag-lookup | legacy_rag_fallback | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::decision-loyalty-default | decision_support | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::summary-payment-default | executive_summary | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::lookup-payment-default | experiment_lookup | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::lookup-hotel-default | experiment_lookup | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::risk-checkout-default | risk_assessment | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::decision-pricing-default | decision_support | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::impact-search-default | business_impact | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::decision-premium-needs-more-data | decision_support | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::summary-loyalty-revision-requested | executive_summary | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::legacy-fallback | legacy_fallback | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::failure-default | agent_failure | response | answer_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-rollout-decision | rollout_decision | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-factual-retrieval | factual_retrieval | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-result-interpretation | result_interpretation | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-risk-guardrail | risk_guardrail | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-business-impact | business_impact | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-insufficient-evidence | insufficient_evidence | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-rollout-decision | rollout_decision | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-factual-retrieval | factual_retrieval | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-result-interpretation | result_interpretation | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-risk-guardrail | risk_guardrail | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-business-impact | business_impact | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-insufficient-evidence | insufficient_evidence | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-rollout-decision | rollout_decision | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-factual-retrieval | factual_retrieval | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-result-interpretation | result_interpretation | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-risk-guardrail | risk_guardrail | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-business-impact | business_impact | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-insufficient-evidence | insufficient_evidence | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-rollout-decision | rollout_decision | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-factual-retrieval | factual_retrieval | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-result-interpretation | result_interpretation | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-risk-guardrail | risk_guardrail | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-business-impact | business_impact | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-insufficient-evidence | insufficient_evidence | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-rollout-decision | rollout_decision | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-factual-retrieval | factual_retrieval | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-result-interpretation | result_interpretation | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-risk-guardrail | risk_guardrail | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-business-impact | business_impact | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-insufficient-evidence | insufficient_evidence | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-rollout-decision | rollout_decision | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-factual-retrieval | factual_retrieval | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-result-interpretation | result_interpretation | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-risk-guardrail | risk_guardrail | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-business-impact | business_impact | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-insufficient-evidence | insufficient_evidence | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-rollout-decision | rollout_decision | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-factual-retrieval | factual_retrieval | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-result-interpretation | result_interpretation | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-risk-guardrail | risk_guardrail | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-business-impact | business_impact | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-insufficient-evidence | insufficient_evidence | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-rollout-decision | rollout_decision | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-factual-retrieval | factual_retrieval | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-result-interpretation | result_interpretation | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-risk-guardrail | risk_guardrail | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-business-impact | business_impact | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-insufficient-evidence | insufficient_evidence | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-rollout-decision | rollout_decision | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-factual-retrieval | factual_retrieval | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-result-interpretation | result_interpretation | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-risk-guardrail | risk_guardrail | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-business-impact | business_impact | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-insufficient-evidence | insufficient_evidence | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-rollout-decision | rollout_decision | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-factual-retrieval | factual_retrieval | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-result-interpretation | result_interpretation | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-risk-guardrail | risk_guardrail | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-business-impact | business_impact | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-insufficient-evidence | insufficient_evidence | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-legacy-rag-lookup | legacy_rag_fallback | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-legacy-rag-lookup | legacy_rag_fallback | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::decision-loyalty-default | decision_support | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::summary-payment-default | executive_summary | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::lookup-payment-default | experiment_lookup | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::lookup-hotel-default | experiment_lookup | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::risk-checkout-default | risk_assessment | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::decision-pricing-default | decision_support | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::impact-search-default | business_impact | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::decision-premium-needs-more-data | decision_support | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::summary-loyalty-revision-requested | executive_summary | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::legacy-fallback | legacy_fallback | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::failure-default | agent_failure | response | faithfulness |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-rollout-decision | rollout_decision | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-factual-retrieval | factual_retrieval | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-result-interpretation | result_interpretation | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-risk-guardrail | risk_guardrail | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-business-impact | business_impact | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-insufficient-evidence | insufficient_evidence | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-rollout-decision | rollout_decision | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-factual-retrieval | factual_retrieval | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-result-interpretation | result_interpretation | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-risk-guardrail | risk_guardrail | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-business-impact | business_impact | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-insufficient-evidence | insufficient_evidence | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-rollout-decision | rollout_decision | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-factual-retrieval | factual_retrieval | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-result-interpretation | result_interpretation | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-risk-guardrail | risk_guardrail | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-business-impact | business_impact | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-insufficient-evidence | insufficient_evidence | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-rollout-decision | rollout_decision | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-factual-retrieval | factual_retrieval | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-result-interpretation | result_interpretation | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-risk-guardrail | risk_guardrail | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-business-impact | business_impact | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-insufficient-evidence | insufficient_evidence | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-rollout-decision | rollout_decision | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-factual-retrieval | factual_retrieval | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-result-interpretation | result_interpretation | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-risk-guardrail | risk_guardrail | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-business-impact | business_impact | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-insufficient-evidence | insufficient_evidence | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-rollout-decision | rollout_decision | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-factual-retrieval | factual_retrieval | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-result-interpretation | result_interpretation | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-risk-guardrail | risk_guardrail | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-business-impact | business_impact | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-insufficient-evidence | insufficient_evidence | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-rollout-decision | rollout_decision | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-factual-retrieval | factual_retrieval | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-result-interpretation | result_interpretation | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-risk-guardrail | risk_guardrail | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-business-impact | business_impact | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-insufficient-evidence | insufficient_evidence | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-rollout-decision | rollout_decision | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-factual-retrieval | factual_retrieval | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-result-interpretation | result_interpretation | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-risk-guardrail | risk_guardrail | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-business-impact | business_impact | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-insufficient-evidence | insufficient_evidence | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-rollout-decision | rollout_decision | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-factual-retrieval | factual_retrieval | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-result-interpretation | result_interpretation | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-risk-guardrail | risk_guardrail | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-business-impact | business_impact | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-insufficient-evidence | insufficient_evidence | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-rollout-decision | rollout_decision | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-factual-retrieval | factual_retrieval | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-result-interpretation | result_interpretation | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-risk-guardrail | risk_guardrail | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-business-impact | business_impact | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-insufficient-evidence | insufficient_evidence | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-legacy-rag-lookup | legacy_rag_fallback | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-legacy-rag-lookup | legacy_rag_fallback | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::decision-loyalty-default | decision_support | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::summary-payment-default | executive_summary | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::lookup-payment-default | experiment_lookup | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::lookup-hotel-default | experiment_lookup | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::risk-checkout-default | risk_assessment | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::decision-pricing-default | decision_support | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::impact-search-default | business_impact | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::decision-premium-needs-more-data | decision_support | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::summary-loyalty-revision-requested | executive_summary | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::legacy-fallback | legacy_fallback | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::failure-default | agent_failure | response | hallucination |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-rollout-decision | rollout_decision | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-factual-retrieval | factual_retrieval | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-result-interpretation | result_interpretation | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-risk-guardrail | risk_guardrail | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-business-impact | business_impact | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-insufficient-evidence | insufficient_evidence | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-rollout-decision | rollout_decision | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-factual-retrieval | factual_retrieval | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-result-interpretation | result_interpretation | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-risk-guardrail | risk_guardrail | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-business-impact | business_impact | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-002-insufficient-evidence | insufficient_evidence | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-rollout-decision | rollout_decision | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-factual-retrieval | factual_retrieval | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-result-interpretation | result_interpretation | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-risk-guardrail | risk_guardrail | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-business-impact | business_impact | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-003-insufficient-evidence | insufficient_evidence | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-rollout-decision | rollout_decision | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-factual-retrieval | factual_retrieval | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-result-interpretation | result_interpretation | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-risk-guardrail | risk_guardrail | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-business-impact | business_impact | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-insufficient-evidence | insufficient_evidence | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-rollout-decision | rollout_decision | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-factual-retrieval | factual_retrieval | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-result-interpretation | result_interpretation | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-risk-guardrail | risk_guardrail | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-business-impact | business_impact | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-005-insufficient-evidence | insufficient_evidence | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-rollout-decision | rollout_decision | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-factual-retrieval | factual_retrieval | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-result-interpretation | result_interpretation | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-risk-guardrail | risk_guardrail | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-business-impact | business_impact | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-006-insufficient-evidence | insufficient_evidence | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-rollout-decision | rollout_decision | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-factual-retrieval | factual_retrieval | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-result-interpretation | result_interpretation | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-risk-guardrail | risk_guardrail | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-business-impact | business_impact | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-007-insufficient-evidence | insufficient_evidence | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-rollout-decision | rollout_decision | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-factual-retrieval | factual_retrieval | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-result-interpretation | result_interpretation | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-risk-guardrail | risk_guardrail | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-business-impact | business_impact | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-008-insufficient-evidence | insufficient_evidence | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-rollout-decision | rollout_decision | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-factual-retrieval | factual_retrieval | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-result-interpretation | result_interpretation | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-risk-guardrail | risk_guardrail | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-business-impact | business_impact | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-009-insufficient-evidence | insufficient_evidence | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-rollout-decision | rollout_decision | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-factual-retrieval | factual_retrieval | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-result-interpretation | result_interpretation | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-risk-guardrail | risk_guardrail | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-business-impact | business_impact | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-010-insufficient-evidence | insufficient_evidence | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-001-legacy-rag-lookup | legacy_rag_fallback | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::exp-004-legacy-rag-lookup | legacy_rag_fallback | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::decision-loyalty-default | decision_support | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::summary-payment-default | executive_summary | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::lookup-payment-default | experiment_lookup | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::lookup-hotel-default | experiment_lookup | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::risk-checkout-default | risk_assessment | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::decision-pricing-default | decision_support | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::impact-search-default | business_impact | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::decision-premium-needs-more-data | decision_support | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::summary-loyalty-revision-requested | executive_summary | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| legacy_rag::legacy-fallback | legacy_fallback | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |
| agent_workflow::failure-default | agent_failure | response | contextual_relevancy |  | skipped | Judge metrics are disabled in offline mode to avoid implicit live provider calls. |

## Skipped Metrics

- `answer_relevancy`: Judge metrics are disabled in offline mode to avoid implicit live provider calls.
- `contextual_relevancy`: Judge metrics are disabled in offline mode to avoid implicit live provider calls.
- `faithfulness`: Judge metrics are disabled in offline mode to avoid implicit live provider calls.
- `hallucination`: Judge metrics are disabled in offline mode to avoid implicit live provider calls.

## Failing Cases

No failing cases were recorded.

## Limitations

- DeepEval remains additive; the existing custom evaluation harnesses and RAGAS stay intact.
- No Confident AI cloud integration, tracing, or observability hooks are enabled in this adapter.
- Workflow deterministic metrics remain ExperimentOS-owned even when DeepEval is installed.
- Unsupported-claim avoidance is a deterministic heuristic, not a semantic judge score.
- Offline mode skips judge-based metrics by design and never invokes a live model.
