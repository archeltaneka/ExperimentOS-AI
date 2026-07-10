# Evaluation Harness Report

## Providers

- Embedding provider: ollama
- Embedding model: nomic-embed-text
- LLM provider: ollama
- LLM model: qwen2.5:7b

## Summary

- Questions evaluated: 62
- Retrieval success rate: 100.0%
- Average citation coverage: 100.0%
- Average retrieval latency: 650.1 ms
- Average LLM latency: 4348.1 ms
- Average similarity: 0.664
- Token usage: 72510 total (66623 input, 5887 output)
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
| exp-001-rollout-decision | exp-001-payment-recommendation | rollout_decision | rag.answer@1 | yes | 100.0% | 0.712 |  |
| exp-001-factual-retrieval | exp-001-payment-recommendation | factual_retrieval | rag.answer@1 | yes | 100.0% | 0.706 |  |
| exp-001-result-interpretation | exp-001-payment-recommendation | result_interpretation | rag.answer@1 | yes | 100.0% | 0.636 |  |
| exp-001-risk-guardrail | exp-001-payment-recommendation | risk_guardrail | rag.answer@1 | yes | 100.0% | 0.657 |  |
| exp-001-business-impact | exp-001-payment-recommendation | business_impact | rag.answer@1 | yes | 100.0% | 0.672 |  |
| exp-001-insufficient-evidence | exp-001-payment-recommendation | insufficient_evidence | rag.answer@1 | yes | 100.0% | 0.621 |  |
| exp-002-rollout-decision | exp-002-hotel-image-quality | rollout_decision | rag.answer@1 | yes | 100.0% | 0.731 |  |
| exp-002-factual-retrieval | exp-002-hotel-image-quality | factual_retrieval | rag.answer@1 | yes | 100.0% | 0.715 |  |
| exp-002-result-interpretation | exp-002-hotel-image-quality | result_interpretation | rag.answer@1 | yes | 100.0% | 0.704 |  |
| exp-002-risk-guardrail | exp-002-hotel-image-quality | risk_guardrail | rag.answer@1 | yes | 100.0% | 0.647 |  |
| exp-002-business-impact | exp-002-hotel-image-quality | business_impact | rag.answer@1 | yes | 100.0% | 0.696 |  |
| exp-002-insufficient-evidence | exp-002-hotel-image-quality | insufficient_evidence | rag.answer@1 | yes | 100.0% | 0.674 |  |
| exp-003-rollout-decision | exp-003-search-ranking | rollout_decision | rag.answer@1 | yes | 100.0% | 0.707 |  |
| exp-003-factual-retrieval | exp-003-search-ranking | factual_retrieval | rag.answer@1 | yes | 100.0% | 0.680 |  |
| exp-003-result-interpretation | exp-003-search-ranking | result_interpretation | rag.answer@1 | yes | 100.0% | 0.650 |  |
| exp-003-risk-guardrail | exp-003-search-ranking | risk_guardrail | rag.answer@1 | yes | 100.0% | 0.628 |  |
| exp-003-business-impact | exp-003-search-ranking | business_impact | rag.answer@1 | yes | 100.0% | 0.672 |  |
| exp-003-insufficient-evidence | exp-003-search-ranking | insufficient_evidence | rag.answer@1 | yes | 100.0% | 0.631 |  |
| exp-004-rollout-decision | exp-004-checkout-ux | rollout_decision | rag.answer@1 | yes | 100.0% | 0.736 |  |
| exp-004-factual-retrieval | exp-004-checkout-ux | factual_retrieval | rag.answer@1 | yes | 100.0% | 0.691 |  |
| exp-004-result-interpretation | exp-004-checkout-ux | result_interpretation | rag.answer@1 | yes | 100.0% | 0.677 |  |
| exp-004-risk-guardrail | exp-004-checkout-ux | risk_guardrail | rag.answer@1 | yes | 100.0% | 0.612 |  |
| exp-004-business-impact | exp-004-checkout-ux | business_impact | rag.answer@1 | yes | 100.0% | 0.683 |  |
| exp-004-insufficient-evidence | exp-004-checkout-ux | insufficient_evidence | rag.answer@1 | yes | 100.0% | 0.648 |  |
| exp-005-rollout-decision | exp-005-pricing | rollout_decision | rag.answer@1 | yes | 100.0% | 0.671 |  |
| exp-005-factual-retrieval | exp-005-pricing | factual_retrieval | rag.answer@1 | yes | 100.0% | 0.650 |  |
| exp-005-result-interpretation | exp-005-pricing | result_interpretation | rag.answer@1 | yes | 100.0% | 0.622 |  |
| exp-005-risk-guardrail | exp-005-pricing | risk_guardrail | rag.answer@1 | yes | 100.0% | 0.635 |  |
| exp-005-business-impact | exp-005-pricing | business_impact | rag.answer@1 | yes | 100.0% | 0.640 |  |
| exp-005-insufficient-evidence | exp-005-pricing | insufficient_evidence | rag.answer@1 | yes | 100.0% | 0.609 |  |
| exp-006-rollout-decision | exp-006-loyalty | rollout_decision | rag.answer@1 | yes | 100.0% | 0.703 |  |
| exp-006-factual-retrieval | exp-006-loyalty | factual_retrieval | rag.answer@1 | yes | 100.0% | 0.673 |  |
| exp-006-result-interpretation | exp-006-loyalty | result_interpretation | rag.answer@1 | yes | 100.0% | 0.659 |  |
| exp-006-risk-guardrail | exp-006-loyalty | risk_guardrail | rag.answer@1 | yes | 100.0% | 0.634 |  |
| exp-006-business-impact | exp-006-loyalty | business_impact | rag.answer@1 | yes | 100.0% | 0.670 |  |
| exp-006-insufficient-evidence | exp-006-loyalty | insufficient_evidence | rag.answer@1 | yes | 100.0% | 0.641 |  |
| exp-007-rollout-decision | exp-007-crm-notifications | rollout_decision | rag.answer@1 | yes | 100.0% | 0.731 |  |
| exp-007-factual-retrieval | exp-007-crm-notifications | factual_retrieval | rag.answer@1 | yes | 100.0% | 0.697 |  |
| exp-007-result-interpretation | exp-007-crm-notifications | result_interpretation | rag.answer@1 | yes | 100.0% | 0.645 |  |
| exp-007-risk-guardrail | exp-007-crm-notifications | risk_guardrail | rag.answer@1 | yes | 100.0% | 0.632 |  |
| exp-007-business-impact | exp-007-crm-notifications | business_impact | rag.answer@1 | yes | 100.0% | 0.690 |  |
| exp-007-insufficient-evidence | exp-007-crm-notifications | insufficient_evidence | rag.answer@1 | yes | 100.0% | 0.647 |  |
| exp-008-rollout-decision | exp-008-recommendation-systems | rollout_decision | rag.answer@1 | yes | 100.0% | 0.684 |  |
| exp-008-factual-retrieval | exp-008-recommendation-systems | factual_retrieval | rag.answer@1 | yes | 100.0% | 0.672 |  |
| exp-008-result-interpretation | exp-008-recommendation-systems | result_interpretation | rag.answer@1 | yes | 100.0% | 0.629 |  |
| exp-008-risk-guardrail | exp-008-recommendation-systems | risk_guardrail | rag.answer@1 | yes | 100.0% | 0.591 |  |
| exp-008-business-impact | exp-008-recommendation-systems | business_impact | rag.answer@1 | yes | 100.0% | 0.632 |  |
| exp-008-insufficient-evidence | exp-008-recommendation-systems | insufficient_evidence | rag.answer@1 | yes | 100.0% | 0.620 |  |
| exp-009-rollout-decision | exp-009-search-filters | rollout_decision | rag.answer@1 | yes | 100.0% | 0.695 |  |
| exp-009-factual-retrieval | exp-009-search-filters | factual_retrieval | rag.answer@1 | yes | 100.0% | 0.676 |  |
| exp-009-result-interpretation | exp-009-search-filters | result_interpretation | rag.answer@1 | yes | 100.0% | 0.640 |  |
| exp-009-risk-guardrail | exp-009-search-filters | risk_guardrail | rag.answer@1 | yes | 100.0% | 0.608 |  |
| exp-009-business-impact | exp-009-search-filters | business_impact | rag.answer@1 | yes | 100.0% | 0.676 |  |
| exp-009-insufficient-evidence | exp-009-search-filters | insufficient_evidence | rag.answer@1 | yes | 100.0% | 0.633 |  |
| exp-010-rollout-decision | exp-010-premium-subscriptions | rollout_decision | rag.answer@1 | yes | 100.0% | 0.731 |  |
| exp-010-factual-retrieval | exp-010-premium-subscriptions | factual_retrieval | rag.answer@1 | yes | 100.0% | 0.692 |  |
| exp-010-result-interpretation | exp-010-premium-subscriptions | result_interpretation | rag.answer@1 | yes | 100.0% | 0.645 |  |
| exp-010-risk-guardrail | exp-010-premium-subscriptions | risk_guardrail | rag.answer@1 | yes | 100.0% | 0.622 |  |
| exp-010-business-impact | exp-010-premium-subscriptions | business_impact | rag.answer@1 | yes | 100.0% | 0.662 |  |
| exp-010-insufficient-evidence | exp-010-premium-subscriptions | insufficient_evidence | rag.answer@1 | yes | 100.0% | 0.660 |  |
| exp-001-legacy-rag-lookup | exp-001-payment-recommendation | legacy_rag_fallback | rag.answer@1 | yes | 100.0% | 0.686 |  |
| exp-004-legacy-rag-lookup | exp-004-checkout-ux | legacy_rag_fallback | rag.answer@1 | yes | 100.0% | 0.701 |  |

## Follow-Up Candidates

No questions fell below the current retrieval or citation thresholds.
