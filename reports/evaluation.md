# Evaluation Harness Report

## Providers

- Embedding provider: fake
- Embedding model: fake
- LLM provider: mock
- LLM model: mock

## Summary

- Questions evaluated: 62
- Retrieval success rate: 100.0%
- Average citation coverage: 100.0%
- Average retrieval latency: 49.4 ms
- Average LLM latency: 0.0 ms
- Average similarity: 0.009
- Token usage: 37213 total (36021 input, 1192 output)
- Estimated cost: $0.000000

## Category Coverage

| Category | Questions | Retrieval Success | Avg Citation Coverage |
| --- | ---: | ---: | ---: |
| business_impact | 10 | 100.0% | 100.0% |
| factual_retrieval | 10 | 100.0% | 100.0% |
| insufficient_evidence | 10 | 100.0% | 100.0% |
| legacy_rag_fallback | 2 | 100.0% | 100.0% |
| result_interpretation | 10 | 100.0% | 100.0% |
| risk_guardrail | 10 | 100.0% | 100.0% |
| rollout_decision | 10 | 100.0% | 100.0% |

## Sample Results

| ID | Experiment | Category | Prompt | Retrieval | Citation Coverage | Avg Similarity | Error |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| exp-001-rollout-decision | exp-001-payment-recommendation | rollout_decision | rag.answer@1 | yes | 100.0% | -0.002 |  |
| exp-001-factual-retrieval | exp-001-payment-recommendation | factual_retrieval | rag.answer@1 | yes | 100.0% | 0.027 |  |
| exp-001-result-interpretation | exp-001-payment-recommendation | result_interpretation | rag.answer@1 | yes | 100.0% | -0.005 |  |
| exp-001-risk-guardrail | exp-001-payment-recommendation | risk_guardrail | rag.answer@1 | yes | 100.0% | 0.016 |  |
| exp-001-business-impact | exp-001-payment-recommendation | business_impact | rag.answer@1 | yes | 100.0% | 0.025 |  |
| exp-001-insufficient-evidence | exp-001-payment-recommendation | insufficient_evidence | rag.answer@1 | yes | 100.0% | 0.035 |  |
| exp-002-rollout-decision | exp-002-hotel-image-quality | rollout_decision | rag.answer@1 | yes | 100.0% | 0.009 |  |
| exp-002-factual-retrieval | exp-002-hotel-image-quality | factual_retrieval | rag.answer@1 | yes | 100.0% | -0.017 |  |
| exp-002-result-interpretation | exp-002-hotel-image-quality | result_interpretation | rag.answer@1 | yes | 100.0% | 0.017 |  |
| exp-002-risk-guardrail | exp-002-hotel-image-quality | risk_guardrail | rag.answer@1 | yes | 100.0% | 0.010 |  |
| exp-002-business-impact | exp-002-hotel-image-quality | business_impact | rag.answer@1 | yes | 100.0% | -0.013 |  |
| exp-002-insufficient-evidence | exp-002-hotel-image-quality | insufficient_evidence | rag.answer@1 | yes | 100.0% | 0.004 |  |
| exp-003-rollout-decision | exp-003-search-ranking | rollout_decision | rag.answer@1 | yes | 100.0% | 0.029 |  |
| exp-003-factual-retrieval | exp-003-search-ranking | factual_retrieval | rag.answer@1 | yes | 100.0% | 0.043 |  |
| exp-003-result-interpretation | exp-003-search-ranking | result_interpretation | rag.answer@1 | yes | 100.0% | 0.001 |  |
| exp-003-risk-guardrail | exp-003-search-ranking | risk_guardrail | rag.answer@1 | yes | 100.0% | 0.003 |  |
| exp-003-business-impact | exp-003-search-ranking | business_impact | rag.answer@1 | yes | 100.0% | 0.049 |  |
| exp-003-insufficient-evidence | exp-003-search-ranking | insufficient_evidence | rag.answer@1 | yes | 100.0% | 0.001 |  |
| exp-004-rollout-decision | exp-004-checkout-ux | rollout_decision | rag.answer@1 | yes | 100.0% | -0.053 |  |
| exp-004-factual-retrieval | exp-004-checkout-ux | factual_retrieval | rag.answer@1 | yes | 100.0% | 0.007 |  |
| exp-004-result-interpretation | exp-004-checkout-ux | result_interpretation | rag.answer@1 | yes | 100.0% | -0.036 |  |
| exp-004-risk-guardrail | exp-004-checkout-ux | risk_guardrail | rag.answer@1 | yes | 100.0% | 0.001 |  |
| exp-004-business-impact | exp-004-checkout-ux | business_impact | rag.answer@1 | yes | 100.0% | -0.007 |  |
| exp-004-insufficient-evidence | exp-004-checkout-ux | insufficient_evidence | rag.answer@1 | yes | 100.0% | 0.027 |  |
| exp-005-rollout-decision | exp-005-pricing | rollout_decision | rag.answer@1 | yes | 100.0% | -0.012 |  |
| exp-005-factual-retrieval | exp-005-pricing | factual_retrieval | rag.answer@1 | yes | 100.0% | 0.027 |  |
| exp-005-result-interpretation | exp-005-pricing | result_interpretation | rag.answer@1 | yes | 100.0% | 0.015 |  |
| exp-005-risk-guardrail | exp-005-pricing | risk_guardrail | rag.answer@1 | yes | 100.0% | 0.045 |  |
| exp-005-business-impact | exp-005-pricing | business_impact | rag.answer@1 | yes | 100.0% | 0.029 |  |
| exp-005-insufficient-evidence | exp-005-pricing | insufficient_evidence | rag.answer@1 | yes | 100.0% | -0.014 |  |
| exp-006-rollout-decision | exp-006-loyalty | rollout_decision | rag.answer@1 | yes | 100.0% | -0.004 |  |
| exp-006-factual-retrieval | exp-006-loyalty | factual_retrieval | rag.answer@1 | yes | 100.0% | 0.004 |  |
| exp-006-result-interpretation | exp-006-loyalty | result_interpretation | rag.answer@1 | yes | 100.0% | 0.002 |  |
| exp-006-risk-guardrail | exp-006-loyalty | risk_guardrail | rag.answer@1 | yes | 100.0% | 0.044 |  |
| exp-006-business-impact | exp-006-loyalty | business_impact | rag.answer@1 | yes | 100.0% | -0.026 |  |
| exp-006-insufficient-evidence | exp-006-loyalty | insufficient_evidence | rag.answer@1 | yes | 100.0% | -0.000 |  |
| exp-007-rollout-decision | exp-007-crm-notifications | rollout_decision | rag.answer@1 | yes | 100.0% | -0.022 |  |
| exp-007-factual-retrieval | exp-007-crm-notifications | factual_retrieval | rag.answer@1 | yes | 100.0% | -0.008 |  |
| exp-007-result-interpretation | exp-007-crm-notifications | result_interpretation | rag.answer@1 | yes | 100.0% | -0.004 |  |
| exp-007-risk-guardrail | exp-007-crm-notifications | risk_guardrail | rag.answer@1 | yes | 100.0% | -0.012 |  |
| exp-007-business-impact | exp-007-crm-notifications | business_impact | rag.answer@1 | yes | 100.0% | 0.002 |  |
| exp-007-insufficient-evidence | exp-007-crm-notifications | insufficient_evidence | rag.answer@1 | yes | 100.0% | 0.008 |  |
| exp-008-rollout-decision | exp-008-recommendation-systems | rollout_decision | rag.answer@1 | yes | 100.0% | -0.011 |  |
| exp-008-factual-retrieval | exp-008-recommendation-systems | factual_retrieval | rag.answer@1 | yes | 100.0% | 0.011 |  |
| exp-008-result-interpretation | exp-008-recommendation-systems | result_interpretation | rag.answer@1 | yes | 100.0% | 0.020 |  |
| exp-008-risk-guardrail | exp-008-recommendation-systems | risk_guardrail | rag.answer@1 | yes | 100.0% | -0.013 |  |
| exp-008-business-impact | exp-008-recommendation-systems | business_impact | rag.answer@1 | yes | 100.0% | 0.032 |  |
| exp-008-insufficient-evidence | exp-008-recommendation-systems | insufficient_evidence | rag.answer@1 | yes | 100.0% | 0.050 |  |
| exp-009-rollout-decision | exp-009-search-filters | rollout_decision | rag.answer@1 | yes | 100.0% | -0.015 |  |
| exp-009-factual-retrieval | exp-009-search-filters | factual_retrieval | rag.answer@1 | yes | 100.0% | 0.033 |  |
| exp-009-result-interpretation | exp-009-search-filters | result_interpretation | rag.answer@1 | yes | 100.0% | 0.024 |  |
| exp-009-risk-guardrail | exp-009-search-filters | risk_guardrail | rag.answer@1 | yes | 100.0% | 0.030 |  |
| exp-009-business-impact | exp-009-search-filters | business_impact | rag.answer@1 | yes | 100.0% | -0.025 |  |
| exp-009-insufficient-evidence | exp-009-search-filters | insufficient_evidence | rag.answer@1 | yes | 100.0% | 0.031 |  |
| exp-010-rollout-decision | exp-010-premium-subscriptions | rollout_decision | rag.answer@1 | yes | 100.0% | 0.064 |  |
| exp-010-factual-retrieval | exp-010-premium-subscriptions | factual_retrieval | rag.answer@1 | yes | 100.0% | 0.009 |  |
| exp-010-result-interpretation | exp-010-premium-subscriptions | result_interpretation | rag.answer@1 | yes | 100.0% | 0.004 |  |
| exp-010-risk-guardrail | exp-010-premium-subscriptions | risk_guardrail | rag.answer@1 | yes | 100.0% | 0.030 |  |
| exp-010-business-impact | exp-010-premium-subscriptions | business_impact | rag.answer@1 | yes | 100.0% | -0.007 |  |
| exp-010-insufficient-evidence | exp-010-premium-subscriptions | insufficient_evidence | rag.answer@1 | yes | 100.0% | 0.025 |  |
| exp-001-legacy-rag-lookup | exp-001-payment-recommendation | legacy_rag_fallback | rag.answer@1 | yes | 100.0% | 0.036 |  |
| exp-004-legacy-rag-lookup | exp-004-checkout-ux | legacy_rag_fallback | rag.answer@1 | yes | 100.0% | -0.017 |  |

## Follow-Up Candidates

No questions fell below the current retrieval or citation thresholds.
