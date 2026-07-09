# RAGAS Evaluation Report

## Dataset

- Source dataset: `data\eval\qa_dataset.json`
- Dataset size: 62
- Eligible samples: 62
- Excluded samples: 0

## Providers

- QA embedding provider: fake
- QA embedding model: fake
- QA LLM provider: mock
- QA LLM model: mock
- Judge LLM provider: none
- Judge LLM model: none
- Judge embedding provider: none
- Judge embedding model: none

## RAGAS Runtime

- RAGAS available: yes
- RAGAS version: 0.4.3
- Metrics requested: id_based_context_precision, id_based_context_recall, context_precision, context_recall, faithfulness, answer_relevancy
- Metrics run: id_based_context_precision, id_based_context_recall
- Import note: Applied a local VertexAI import shim because ragas imports that optional integration eagerly in this environment.

## Metric Summary

| Metric | Status | Average Score | Reason |
| --- | --- | ---: | --- |
| id_based_context_precision | computed | 1.0000 |  |
| id_based_context_recall | computed | 1.0000 |  |
| context_precision | skipped | n/a | judge llm provider `none` does not enable RAGAS judge metrics |
| context_recall | skipped | n/a | judge llm provider `none` does not enable RAGAS judge metrics |
| faithfulness | skipped | n/a | judge llm provider `none` does not enable RAGAS judge metrics |
| answer_relevancy | skipped | n/a | judge llm provider `none` does not enable RAGAS judge metrics |

## Per-Case Results

| ID | Experiment | Category | Difficulty | Contexts | Documents | Source Error | Scores |
| --- | --- | --- | --- | ---: | ---: | --- | --- |
| exp-001-rollout-decision | exp-001-payment-recommendation | rollout_decision | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-001-factual-retrieval | exp-001-payment-recommendation | factual_retrieval | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-001-result-interpretation | exp-001-payment-recommendation | result_interpretation | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-001-risk-guardrail | exp-001-payment-recommendation | risk_guardrail | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-001-business-impact | exp-001-payment-recommendation | business_impact | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-001-insufficient-evidence | exp-001-payment-recommendation | insufficient_evidence | hard | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-002-rollout-decision | exp-002-hotel-image-quality | rollout_decision | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-002-factual-retrieval | exp-002-hotel-image-quality | factual_retrieval | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-002-result-interpretation | exp-002-hotel-image-quality | result_interpretation | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-002-risk-guardrail | exp-002-hotel-image-quality | risk_guardrail | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-002-business-impact | exp-002-hotel-image-quality | business_impact | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-002-insufficient-evidence | exp-002-hotel-image-quality | insufficient_evidence | hard | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-003-rollout-decision | exp-003-search-ranking | rollout_decision | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-003-factual-retrieval | exp-003-search-ranking | factual_retrieval | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-003-result-interpretation | exp-003-search-ranking | result_interpretation | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-003-risk-guardrail | exp-003-search-ranking | risk_guardrail | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-003-business-impact | exp-003-search-ranking | business_impact | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-003-insufficient-evidence | exp-003-search-ranking | insufficient_evidence | hard | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-004-rollout-decision | exp-004-checkout-ux | rollout_decision | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-004-factual-retrieval | exp-004-checkout-ux | factual_retrieval | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-004-result-interpretation | exp-004-checkout-ux | result_interpretation | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-004-risk-guardrail | exp-004-checkout-ux | risk_guardrail | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-004-business-impact | exp-004-checkout-ux | business_impact | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-004-insufficient-evidence | exp-004-checkout-ux | insufficient_evidence | hard | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-005-rollout-decision | exp-005-pricing | rollout_decision | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-005-factual-retrieval | exp-005-pricing | factual_retrieval | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-005-result-interpretation | exp-005-pricing | result_interpretation | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-005-risk-guardrail | exp-005-pricing | risk_guardrail | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-005-business-impact | exp-005-pricing | business_impact | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-005-insufficient-evidence | exp-005-pricing | insufficient_evidence | hard | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-006-rollout-decision | exp-006-loyalty | rollout_decision | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-006-factual-retrieval | exp-006-loyalty | factual_retrieval | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-006-result-interpretation | exp-006-loyalty | result_interpretation | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-006-risk-guardrail | exp-006-loyalty | risk_guardrail | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-006-business-impact | exp-006-loyalty | business_impact | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-006-insufficient-evidence | exp-006-loyalty | insufficient_evidence | hard | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-007-rollout-decision | exp-007-crm-notifications | rollout_decision | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-007-factual-retrieval | exp-007-crm-notifications | factual_retrieval | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-007-result-interpretation | exp-007-crm-notifications | result_interpretation | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-007-risk-guardrail | exp-007-crm-notifications | risk_guardrail | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-007-business-impact | exp-007-crm-notifications | business_impact | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-007-insufficient-evidence | exp-007-crm-notifications | insufficient_evidence | hard | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-008-rollout-decision | exp-008-recommendation-systems | rollout_decision | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-008-factual-retrieval | exp-008-recommendation-systems | factual_retrieval | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-008-result-interpretation | exp-008-recommendation-systems | result_interpretation | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-008-risk-guardrail | exp-008-recommendation-systems | risk_guardrail | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-008-business-impact | exp-008-recommendation-systems | business_impact | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-008-insufficient-evidence | exp-008-recommendation-systems | insufficient_evidence | hard | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-009-rollout-decision | exp-009-search-filters | rollout_decision | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-009-factual-retrieval | exp-009-search-filters | factual_retrieval | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-009-result-interpretation | exp-009-search-filters | result_interpretation | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-009-risk-guardrail | exp-009-search-filters | risk_guardrail | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-009-business-impact | exp-009-search-filters | business_impact | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-009-insufficient-evidence | exp-009-search-filters | insufficient_evidence | hard | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-010-rollout-decision | exp-010-premium-subscriptions | rollout_decision | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-010-factual-retrieval | exp-010-premium-subscriptions | factual_retrieval | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-010-result-interpretation | exp-010-premium-subscriptions | result_interpretation | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-010-risk-guardrail | exp-010-premium-subscriptions | risk_guardrail | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-010-business-impact | exp-010-premium-subscriptions | business_impact | medium | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-010-insufficient-evidence | exp-010-premium-subscriptions | insufficient_evidence | hard | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-001-legacy-rag-lookup | exp-001-payment-recommendation | legacy_rag_fallback | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |
| exp-004-legacy-rag-lookup | exp-004-checkout-ux | legacy_rag_fallback | easy | 5 | 1 |  | id_based_context_precision=1.0000, id_based_context_recall=1.0000 |

## Limitations

- Judge-backed metrics are opt-in. This run used no judge LLM, so model-backed RAGAS metrics were skipped by design.
