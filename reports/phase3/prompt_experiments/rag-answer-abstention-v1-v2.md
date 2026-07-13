# Prompt Experiment Report

- Experiment ID: rag-answer-abstention-v1-v2
- Prompt ID: rag.answer
- Control version: 1
- Treatment versions: 2
- Dataset: qa_dataset
- Assignment strategy: fixed
- Recommendation: inconclusive
- Production traffic involved: no

## Variants

| Variant | Prompt Version | Sample Size | Factuality Pass Rate | Citation Coverage | Regression Pass Rate |
| --- | --- | ---: | ---: | ---: | ---: |
| control | 1 | 62 | 0.000 | 1.000 | 1.000 |
| treatment_2 | 2 | 62 | 0.000 | 1.000 | 0.000 |

## Recommendation

- The primary metric was unchanged on the evaluation dataset.

## Limitations

- Offline evaluation results do not establish production causal impact.
- Runtime assignment remains disabled by default.
- Judge metrics are supplementary and optional.
