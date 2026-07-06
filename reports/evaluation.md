# Evaluation Harness Report

## Providers

- Embedding provider: ollama
- Embedding model: nomic-embed-text
- LLM provider: ollama
- LLM model: qwen2.5:7b

## Summary

- Questions evaluated: 40
- Retrieval success rate: 100.0%
- Average citation coverage: 100.0%
- Average retrieval latency: 739.7 ms
- Average LLM latency: 4681.7 ms
- Average similarity: 0.669
- Token usage: 45048 total (41532 input, 3516 output)
- Estimated cost: $0.000000

## Category Coverage

| Category | Questions | Retrieval Success | Avg Citation Coverage |
| --- | ---: | ---: | ---: |
| caveat | 10 | 100.0% | 100.0% |
| decision | 10 | 100.0% | 100.0% |
| metric | 10 | 100.0% | 100.0% |
| risk | 10 | 100.0% | 100.0% |

## Sample Results

| ID | Experiment | Category | Retrieval | Citation Coverage | Avg Similarity | Error |
| --- | --- | --- | ---: | ---: | ---: | --- |
| exp-001-decision | exp-001-payment-recommendation | decision | yes | 100.0% | 0.668 |  |
| exp-001-primary-metric | exp-001-payment-recommendation | metric | yes | 100.0% | 0.706 |  |
| exp-001-caveat | exp-001-payment-recommendation | caveat | yes | 100.0% | 0.662 |  |
| exp-001-risk | exp-001-payment-recommendation | risk | yes | 100.0% | 0.655 |  |
| exp-002-decision | exp-002-hotel-image-quality | decision | yes | 100.0% | 0.718 |  |
| exp-002-primary-metric | exp-002-hotel-image-quality | metric | yes | 100.0% | 0.707 |  |
| exp-002-caveat | exp-002-hotel-image-quality | caveat | yes | 100.0% | 0.722 |  |
| exp-002-risk | exp-002-hotel-image-quality | risk | yes | 100.0% | 0.693 |  |
| exp-003-decision | exp-003-search-ranking | decision | yes | 100.0% | 0.716 |  |
| exp-003-primary-metric | exp-003-search-ranking | metric | yes | 100.0% | 0.679 |  |
| exp-003-caveat | exp-003-search-ranking | caveat | yes | 100.0% | 0.647 |  |
| exp-003-risk | exp-003-search-ranking | risk | yes | 100.0% | 0.664 |  |
| exp-004-decision | exp-004-checkout-ux | decision | yes | 100.0% | 0.629 |  |
| exp-004-primary-metric | exp-004-checkout-ux | metric | yes | 100.0% | 0.716 |  |
| exp-004-caveat | exp-004-checkout-ux | caveat | yes | 100.0% | 0.684 |  |
| exp-004-risk | exp-004-checkout-ux | risk | yes | 100.0% | 0.627 |  |
| exp-005-decision | exp-005-pricing | decision | yes | 100.0% | 0.653 |  |
| exp-005-primary-metric | exp-005-pricing | metric | yes | 100.0% | 0.628 |  |
| exp-005-caveat | exp-005-pricing | caveat | yes | 100.0% | 0.611 |  |
| exp-005-risk | exp-005-pricing | risk | yes | 100.0% | 0.679 |  |
| exp-006-decision | exp-006-loyalty | decision | yes | 100.0% | 0.729 |  |
| exp-006-primary-metric | exp-006-loyalty | metric | yes | 100.0% | 0.690 |  |
| exp-006-caveat | exp-006-loyalty | caveat | yes | 100.0% | 0.676 |  |
| exp-006-risk | exp-006-loyalty | risk | yes | 100.0% | 0.632 |  |
| exp-007-decision | exp-007-crm-notifications | decision | yes | 100.0% | 0.666 |  |
| exp-007-primary-metric | exp-007-crm-notifications | metric | yes | 100.0% | 0.672 |  |
| exp-007-caveat | exp-007-crm-notifications | caveat | yes | 100.0% | 0.691 |  |
| exp-007-risk | exp-007-crm-notifications | risk | yes | 100.0% | 0.691 |  |
| exp-008-decision | exp-008-recommendation-systems | decision | yes | 100.0% | 0.681 |  |
| exp-008-primary-metric | exp-008-recommendation-systems | metric | yes | 100.0% | 0.669 |  |
| exp-008-caveat | exp-008-recommendation-systems | caveat | yes | 100.0% | 0.594 |  |
| exp-008-risk | exp-008-recommendation-systems | risk | yes | 100.0% | 0.603 |  |
| exp-009-decision | exp-009-search-filters | decision | yes | 100.0% | 0.699 |  |
| exp-009-primary-metric | exp-009-search-filters | metric | yes | 100.0% | 0.663 |  |
| exp-009-caveat | exp-009-search-filters | caveat | yes | 100.0% | 0.633 |  |
| exp-009-risk | exp-009-search-filters | risk | yes | 100.0% | 0.657 |  |
| exp-010-decision | exp-010-premium-subscriptions | decision | yes | 100.0% | 0.639 |  |
| exp-010-primary-metric | exp-010-premium-subscriptions | metric | yes | 100.0% | 0.674 |  |
| exp-010-caveat | exp-010-premium-subscriptions | caveat | yes | 100.0% | 0.652 |  |
| exp-010-risk | exp-010-premium-subscriptions | risk | yes | 100.0% | 0.668 |  |

## Follow-Up Candidates

No questions fell below the current retrieval or citation thresholds.
