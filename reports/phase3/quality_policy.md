# Phase 3 Quality Policy Report

- Policy version: 2026-07-13
- Report directory: `C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports`
- Overall status: pass
- Recommendation: Quality policy thresholds are satisfied for the available offline artifacts.

## Categories

| Category | Status | Pass | Warning | Fail | Skipped |
| --- | --- | ---: | ---: | ---: | ---: |
| Retrieval | pass | 5 | 0 | 0 | 0 |
| Answer Quality | pass | 1 | 0 | 0 | 6 |
| Workflow | pass | 16 | 0 | 0 | 0 |
| Prompt | pass | 6 | 0 | 0 | 0 |
| Factuality | pass | 8 | 0 | 0 | 0 |
| Reliability | pass | 6 | 0 | 0 | 0 |

## Metrics Evaluated

- `rag.retrieval_success_rate`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\evaluation.md`
- `rag.average_citation_coverage`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\evaluation.md`
- `ragas.id_based_context_precision`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\ragas_report.json`
- `ragas.id_based_context_recall`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\ragas_report.json`
- `deepeval.citation_coverage.average_score`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\deepeval_report.json`
- `deepeval.response_field_completeness.average_score`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\deepeval_report.json`
- `ragas.answer_relevancy`: status=skipped, observed=None, threshold=gte 0.5, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\ragas_report.json`
- `ragas.faithfulness`: status=skipped, observed=None, threshold=gte 0.5, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\ragas_report.json`
- `deepeval.answer_relevancy.average_score`: status=skipped, observed=None, threshold=gte 0.5, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\deepeval_report.json`
- `deepeval.faithfulness.average_score`: status=skipped, observed=None, threshold=gte 0.5, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\deepeval_report.json`
- `deepeval.hallucination.average_score`: status=skipped, observed=None, threshold=gte 0.5, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\deepeval_report.json`
- `deepeval.contextual_relevancy.average_score`: status=skipped, observed=None, threshold=gte 0.5, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\deepeval_report.json`
- `agent.workflow_success_rate`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\agent_evaluation.md`
- `agent.routing_accuracy`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\agent_evaluation.md`
- `agent.trace_completeness`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\agent_evaluation.md`
- `agent.recommendation_coverage`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\agent_evaluation.md`
- `agent_e2e.default_agent_workflow_coverage`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\agent_e2e_evaluation.md`
- `agent_e2e.legacy_fallback_coverage`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\agent_e2e_evaluation.md`
- `agent_e2e.routing_accuracy`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\agent_e2e_evaluation.md`
- `agent_e2e.decision_coverage`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\agent_e2e_evaluation.md`
- `agent_e2e.executive_summary_coverage`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\agent_e2e_evaluation.md`
- `agent_e2e.approval_status_coverage`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\agent_e2e_evaluation.md`
- `deepeval.routing_accuracy.average_score`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\deepeval_report.json`
- `deepeval.decision_status_match.average_score`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\deepeval_report.json`
- `deepeval.approval_status_match.average_score`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\deepeval_report.json`
- `deepeval.summary_status_match.average_score`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\deepeval_report.json`
- `deepeval.trace_completeness.average_score`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\deepeval_report.json`
- `deepeval.fallback_compatibility.average_score`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\deepeval_report.json`
- `prompt_regression.summary.pass_rate`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\prompt_regression.json`
- `prompt_regression.summary.regressions`: status=pass, observed=0, threshold=lte 0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\prompt_regression.json`
- `prompt_regression.summary.failures`: status=pass, observed=0, threshold=lte 0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\prompt_regression.json`
- `prompt_regression.metric.prompt_rendering_success.candidate`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\prompt_regression.json`
- `prompt_regression.metric.legacy_fallback_compatibility.candidate`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\prompt_regression.json`
- `prompt_regression.metric.citation_coverage.candidate`: status=pass, observed=1.0, threshold=gte 1.0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\prompt_regression.json`
- `factuality.policy_status`: status=pass, observed=pass, threshold=eq pass, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\factuality_report.json`
- `factuality.findings.fabricated_revenue_or_roi`: status=pass, observed=0.0, threshold=lte 0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\factuality_report.json`
- `factuality.findings.fabricated_statistical_significance`: status=pass, observed=0.0, threshold=lte 0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\factuality_report.json`
- `factuality.findings.contradiction_with_structured_experiment_data`: status=pass, observed=0.0, threshold=lte 0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\factuality_report.json`
- `factuality.findings.citation_missing`: status=pass, observed=0.0, threshold=lte 0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\factuality_report.json`
- `factuality.findings.citation_does_not_support_claim`: status=pass, observed=0.0, threshold=lte 0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\factuality_report.json`
- `factuality.findings.answer_generated_when_abstention_was_expected`: status=pass, observed=0.0, threshold=lte 0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\factuality_report.json`
- `factuality.case_status.fail`: status=pass, observed=0.0, threshold=lte 0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\phase3\factuality_report.json`
- `rag.average_retrieval_latency_ms`: status=pass, observed=49.4, threshold=lte 3000, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\evaluation.md`
- `agent.average_workflow_latency_ms`: status=pass, observed=2.3, threshold=lte 3000, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\agent_evaluation.md`
- `agent_e2e.average_workflow_latency_ms`: status=pass, observed=8.7, threshold=lte 3000, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\agent_e2e_evaluation.md`
- `agent.fail_count`: status=pass, observed=0, threshold=lte 0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\agent_evaluation.md`
- `agent.total_tool_failures`: status=pass, observed=0, threshold=lte 0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\agent_evaluation.md`
- `agent_e2e.fail_count`: status=pass, observed=0, threshold=lte 0, source=`C:\Users\Archel\Documents\Personal Projects\ExperimentOS-AI\reports\agent_e2e_evaluation.md`

## Violations

No blocking policy violations were recorded.

## Warnings

No warning-only deviations were recorded.

## Skipped Metrics

- `ragas.answer_relevancy`: judge llm provider `none` does not enable RAGAS judge metrics
- `ragas.faithfulness`: judge llm provider `none` does not enable RAGAS judge metrics
- `deepeval.answer_relevancy.average_score`: Judge metrics are disabled in offline mode to avoid implicit live provider calls.
- `deepeval.faithfulness.average_score`: Judge metrics are disabled in offline mode to avoid implicit live provider calls.
- `deepeval.hallucination.average_score`: Judge metrics are disabled in offline mode to avoid implicit live provider calls.
- `deepeval.contextual_relevancy.average_score`: Judge metrics are disabled in offline mode to avoid implicit live provider calls.

## Rationale

- All required quality policy metrics satisfied their thresholds.
- 6 metrics were skipped or unavailable.
