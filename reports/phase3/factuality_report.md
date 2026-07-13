# Factuality Evaluation Report

## Summary

- Generated at: 2026-07-13T00:30:11.340410Z
- Target: all
- Mode: offline
- Dataset identifiers: data\eval\qa_dataset.json, data\eval\agent_dataset.json
- Judge provider/model: none / none
- Checks executed: citation_presence, citation_support, numerical_grounding, financial_guardrails, statistical_validation, abstention_correctness, structured_consistency, evidence_coverage
- Checks skipped: claim_extraction, judge:deepeval:faithfulness, judge:deepeval:hallucination, judge:deepeval:contextual_relevancy, judge:deepeval:answer_relevancy
- Overall policy result: warning

## Findings By Category

| Category | Count |
| --- | ---: |
| answer_generated_when_abstention_was_expected | 10 |

## Findings By Severity

| Severity | Count |
| --- | ---: |
| high | 10 |

## Case Outcomes

| Case | Surface | Category | Citation Coverage | Unparsed Claims | Findings | Prompt |
| --- | --- | --- | ---: | --- | ---: | --- |
| exp-001-rollout-decision | legacy_rag | rollout_decision | 1.00 | yes | 0 | rag.answer@1 |
| exp-001-factual-retrieval | legacy_rag | factual_retrieval | 1.00 | yes | 0 | rag.answer@1 |
| exp-001-result-interpretation | legacy_rag | result_interpretation | 1.00 | yes | 0 | rag.answer@1 |
| exp-001-risk-guardrail | legacy_rag | risk_guardrail | 1.00 | yes | 0 | rag.answer@1 |
| exp-001-business-impact | legacy_rag | business_impact | 1.00 | yes | 0 | rag.answer@1 |
| exp-001-insufficient-evidence | legacy_rag | insufficient_evidence | 1.00 | yes | 1 | rag.answer@1 |
| exp-002-rollout-decision | legacy_rag | rollout_decision | 1.00 | yes | 0 | rag.answer@1 |
| exp-002-factual-retrieval | legacy_rag | factual_retrieval | 1.00 | yes | 0 | rag.answer@1 |
| exp-002-result-interpretation | legacy_rag | result_interpretation | 1.00 | yes | 0 | rag.answer@1 |
| exp-002-risk-guardrail | legacy_rag | risk_guardrail | 1.00 | yes | 0 | rag.answer@1 |
| exp-002-business-impact | legacy_rag | business_impact | 1.00 | yes | 0 | rag.answer@1 |
| exp-002-insufficient-evidence | legacy_rag | insufficient_evidence | 1.00 | yes | 1 | rag.answer@1 |
| exp-003-rollout-decision | legacy_rag | rollout_decision | 1.00 | yes | 0 | rag.answer@1 |
| exp-003-factual-retrieval | legacy_rag | factual_retrieval | 1.00 | yes | 0 | rag.answer@1 |
| exp-003-result-interpretation | legacy_rag | result_interpretation | 1.00 | yes | 0 | rag.answer@1 |
| exp-003-risk-guardrail | legacy_rag | risk_guardrail | 1.00 | yes | 0 | rag.answer@1 |
| exp-003-business-impact | legacy_rag | business_impact | 1.00 | yes | 0 | rag.answer@1 |
| exp-003-insufficient-evidence | legacy_rag | insufficient_evidence | 1.00 | yes | 1 | rag.answer@1 |
| exp-004-rollout-decision | legacy_rag | rollout_decision | 1.00 | yes | 0 | rag.answer@1 |
| exp-004-factual-retrieval | legacy_rag | factual_retrieval | 1.00 | yes | 0 | rag.answer@1 |
| exp-004-result-interpretation | legacy_rag | result_interpretation | 1.00 | yes | 0 | rag.answer@1 |
| exp-004-risk-guardrail | legacy_rag | risk_guardrail | 1.00 | yes | 0 | rag.answer@1 |
| exp-004-business-impact | legacy_rag | business_impact | 1.00 | yes | 0 | rag.answer@1 |
| exp-004-insufficient-evidence | legacy_rag | insufficient_evidence | 1.00 | yes | 1 | rag.answer@1 |
| exp-005-rollout-decision | legacy_rag | rollout_decision | 1.00 | yes | 0 | rag.answer@1 |
| exp-005-factual-retrieval | legacy_rag | factual_retrieval | 1.00 | yes | 0 | rag.answer@1 |
| exp-005-result-interpretation | legacy_rag | result_interpretation | 1.00 | yes | 0 | rag.answer@1 |
| exp-005-risk-guardrail | legacy_rag | risk_guardrail | 1.00 | yes | 0 | rag.answer@1 |
| exp-005-business-impact | legacy_rag | business_impact | 1.00 | yes | 0 | rag.answer@1 |
| exp-005-insufficient-evidence | legacy_rag | insufficient_evidence | 1.00 | yes | 1 | rag.answer@1 |
| exp-006-rollout-decision | legacy_rag | rollout_decision | 1.00 | yes | 0 | rag.answer@1 |
| exp-006-factual-retrieval | legacy_rag | factual_retrieval | 1.00 | yes | 0 | rag.answer@1 |
| exp-006-result-interpretation | legacy_rag | result_interpretation | 1.00 | yes | 0 | rag.answer@1 |
| exp-006-risk-guardrail | legacy_rag | risk_guardrail | 1.00 | yes | 0 | rag.answer@1 |
| exp-006-business-impact | legacy_rag | business_impact | 1.00 | yes | 0 | rag.answer@1 |
| exp-006-insufficient-evidence | legacy_rag | insufficient_evidence | 1.00 | yes | 1 | rag.answer@1 |
| exp-007-rollout-decision | legacy_rag | rollout_decision | 1.00 | yes | 0 | rag.answer@1 |
| exp-007-factual-retrieval | legacy_rag | factual_retrieval | 1.00 | yes | 0 | rag.answer@1 |
| exp-007-result-interpretation | legacy_rag | result_interpretation | 1.00 | yes | 0 | rag.answer@1 |
| exp-007-risk-guardrail | legacy_rag | risk_guardrail | 1.00 | yes | 0 | rag.answer@1 |
| exp-007-business-impact | legacy_rag | business_impact | 1.00 | yes | 0 | rag.answer@1 |
| exp-007-insufficient-evidence | legacy_rag | insufficient_evidence | 1.00 | yes | 1 | rag.answer@1 |
| exp-008-rollout-decision | legacy_rag | rollout_decision | 1.00 | yes | 0 | rag.answer@1 |
| exp-008-factual-retrieval | legacy_rag | factual_retrieval | 1.00 | yes | 0 | rag.answer@1 |
| exp-008-result-interpretation | legacy_rag | result_interpretation | 1.00 | yes | 0 | rag.answer@1 |
| exp-008-risk-guardrail | legacy_rag | risk_guardrail | 1.00 | yes | 0 | rag.answer@1 |
| exp-008-business-impact | legacy_rag | business_impact | 1.00 | yes | 0 | rag.answer@1 |
| exp-008-insufficient-evidence | legacy_rag | insufficient_evidence | 1.00 | yes | 1 | rag.answer@1 |
| exp-009-rollout-decision | legacy_rag | rollout_decision | 1.00 | yes | 0 | rag.answer@1 |
| exp-009-factual-retrieval | legacy_rag | factual_retrieval | 1.00 | yes | 0 | rag.answer@1 |
| exp-009-result-interpretation | legacy_rag | result_interpretation | 1.00 | yes | 0 | rag.answer@1 |
| exp-009-risk-guardrail | legacy_rag | risk_guardrail | 1.00 | yes | 0 | rag.answer@1 |
| exp-009-business-impact | legacy_rag | business_impact | 1.00 | yes | 0 | rag.answer@1 |
| exp-009-insufficient-evidence | legacy_rag | insufficient_evidence | 1.00 | yes | 1 | rag.answer@1 |
| exp-010-rollout-decision | legacy_rag | rollout_decision | 1.00 | yes | 0 | rag.answer@1 |
| exp-010-factual-retrieval | legacy_rag | factual_retrieval | 1.00 | yes | 0 | rag.answer@1 |
| exp-010-result-interpretation | legacy_rag | result_interpretation | 1.00 | yes | 0 | rag.answer@1 |
| exp-010-risk-guardrail | legacy_rag | risk_guardrail | 1.00 | yes | 0 | rag.answer@1 |
| exp-010-business-impact | legacy_rag | business_impact | 1.00 | yes | 0 | rag.answer@1 |
| exp-010-insufficient-evidence | legacy_rag | insufficient_evidence | 1.00 | yes | 1 | rag.answer@1 |
| exp-001-legacy-rag-lookup | legacy_rag | legacy_rag_fallback | 1.00 | yes | 0 | rag.answer@1 |
| exp-004-legacy-rag-lookup | legacy_rag | legacy_rag_fallback | 1.00 | yes | 0 | rag.answer@1 |
| lookup-payment | agent_workflow | lookup | 1.00 | no | 0 |  |
| decision-loyalty-rollout | agent_workflow | rollout_decision | 1.00 | no | 0 |  |
| decision-pricing-do-not-rollout | agent_workflow | rollout_decision | 1.00 | no | 0 |  |
| summary-checkout-pending | agent_workflow | approval_workflow | 1.00 | no | 0 |  |
| summary-loyalty-revision-requested | agent_workflow | approval_workflow | 1.00 | no | 0 |  |
| risk-search-filters | agent_workflow | risk_guardrail | 1.00 | no | 0 |  |
| impact-search-ranking | agent_workflow | business_impact | 1.00 | no | 0 |  |
| decision-premium-needs-more-data | agent_workflow | insufficient_evidence | 1.00 | no | 0 |  |

## Finding Details

### Finding 1

- Case: exp-001-insufficient-evidence
- Surface: legacy_rag
- Category: answer_generated_when_abstention_was_expected
- Severity: high
- Detector: deterministic.abstention
- Exact Flagged Claim: Mock evaluation answer generated from retrieved context.
- Normalized Claim: mock evaluation answer generated from retrieved context.
- Expected Evidence: none
- Available Evidence: # Adaptive Payment Method Recommendation | ## Experiment Design

Users were assigned to control and treatment at the user level. Control retained the existing product experience, while treatment received the proposed change. The analysis population included 68 control users and 78 treatment users. Assignment was intended to be even, but the final counts reflect production imperfections. Events were collected across web, mobile web, iOS, and Android. The event stream records country, platform, segment, event name, conversion flag, revenue where applicable, and a tracking-quality indicator. The experiment was evaluated using an intent-to-treat approach so that users remained in their assigned variant even if they did not engage deeply with the feature.
- Source IDs: Adaptive Payment Method Recommendation | Adaptive Payment Method Recommendation | Adaptive Payment Method Recommendation | Adaptive Payment Method Recommendation | Adaptive Payment Method Recommendation
- Structured Field IDs: none
- Explanation: This case expected a needs-more-data or insufficient-evidence outcome, but the answer remained assertive.
- Classification: true_positive
- Remediation Status: strengthen_abstention_behavior

### Finding 2

- Case: exp-002-insufficient-evidence
- Surface: legacy_rag
- Category: answer_generated_when_abstention_was_expected
- Severity: high
- Detector: deterministic.abstention
- Exact Flagged Claim: Mock evaluation answer generated from retrieved context.
- Normalized Claim: mock evaluation answer generated from retrieved context.
- Expected Evidence: none
- Available Evidence: ## Risks

The main risk is that the treatment effect may not generalize when exposed to broader traffic. Higher quality imagery can slow weaker devices and harm low-bandwidth users. There is also risk in over-reading aggregate lift when one country, platform, or segment contributes disproportionately. Tracking issues can create false confidence if they align with the treatment experience. Finally, product teams may be tempted to ship from the headline metric alone, but each report is written to require a business decision that balances upside, guardrails, and data quality. | ## Recommendation

The recommendation is: Roll out while enforcing image byte-size budgets and CDN pre-warming. The business decision recorded in metadata is: Roll out globally except markets with pending image CDN latency regressions. This recommendation reflects both the metric movement and the imperfections observed during the run. For future ExperimentOS milestones, this report should be useful as a retrieval target because it contains explicit reasoning, named metrics, known caveats, and a decision that is more nuanced than simply winning or losing.
- Source IDs: Hotel Gallery Image Quality Boost | Hotel Gallery Image Quality Boost | Hotel Gallery Image Quality Boost | Hotel Gallery Image Quality Boost | Hotel Gallery Image Quality Boost
- Structured Field IDs: none
- Explanation: This case expected a needs-more-data or insufficient-evidence outcome, but the answer remained assertive.
- Classification: true_positive
- Remediation Status: strengthen_abstention_behavior

### Finding 3

- Case: exp-003-insufficient-evidence
- Surface: legacy_rag
- Category: answer_generated_when_abstention_was_expected
- Severity: high
- Detector: deterministic.abstention
- Exact Flagged Claim: Mock evaluation answer generated from retrieved context.
- Normalized Claim: mock evaluation answer generated from retrieved context.
- Expected Evidence: none
- Available Evidence: # Intent-Aware Search Ranking | ## Experiment Design

Users were assigned to control and treatment at the user level. Control retained the existing product experience, while treatment received the proposed change. The analysis population included 80 control users and 70 treatment users. Assignment was intended to be even, but the final counts reflect production imperfections. Events were collected across web, mobile web, iOS, and Android. The event stream records country, platform, segment, event name, conversion flag, revenue where applicable, and a tracking-quality indicator. The experiment was evaluated using an intent-to-treat approach so that users remained in their assigned variant even if they did not engage deeply with the feature.
- Source IDs: Intent-Aware Search Ranking | Intent-Aware Search Ranking | Intent-Aware Search Ranking | Intent-Aware Search Ranking | Intent-Aware Search Ranking
- Structured Field IDs: none
- Explanation: This case expected a needs-more-data or insufficient-evidence outcome, but the answer remained assertive.
- Classification: true_positive
- Remediation Status: strengthen_abstention_behavior

### Finding 4

- Case: exp-004-insufficient-evidence
- Surface: legacy_rag
- Category: answer_generated_when_abstention_was_expected
- Severity: high
- Detector: deterministic.abstention
- Exact Flagged Claim: Mock evaluation answer generated from retrieved context.
- Normalized Claim: mock evaluation answer generated from retrieved context.
- Expected Evidence: none
- Available Evidence: # One-Page Checkout UX | ## Results

Control recorded 0.5840 on checkout_completion_rate, while treatment recorded 0.6380. The absolute movement was 0.0540, and the supporting metrics were directionally consistent with the business read. The result was not interpreted mechanically from a single p-value. Instead, the team considered the size of the effect, product risk, operational cost, and segment behaviour. Metric rows in `metrics.csv` include sample size, the primary metric, and secondary diagnostics for both variants. Event rows in `events.csv` allow future retrieval tests to connect aggregate conclusions back to realistic user-level evidence.
- Source IDs: One-Page Checkout UX | One-Page Checkout UX | One-Page Checkout UX | One-Page Checkout UX | One-Page Checkout UX
- Structured Field IDs: none
- Explanation: This case expected a needs-more-data or insufficient-evidence outcome, but the answer remained assertive.
- Classification: true_positive
- Remediation Status: strengthen_abstention_behavior

### Finding 5

- Case: exp-005-insufficient-evidence
- Surface: legacy_rag
- Category: answer_generated_when_abstention_was_expected
- Severity: high
- Detector: deterministic.abstention
- Exact Flagged Claim: Mock evaluation answer generated from retrieved context.
- Normalized Claim: mock evaluation answer generated from retrieved context.
- Expected Evidence: none
- Available Evidence: ## Recommendation

The recommendation is: Stop current variant and retest with clearer savings copy but no deeper discounts. The business decision recorded in metadata is: Do not roll out; conversion gain did not offset margin dilution. This recommendation reflects both the metric movement and the imperfections observed during the run. For future ExperimentOS milestones, this report should be useful as a retrieval target because it contains explicit reasoning, named metrics, known caveats, and a decision that is more nuanced than simply winning or losing. | ## Experiment Design

Users were assigned to control and treatment at the user level. Control retained the existing product experience, while treatment received the proposed change. The analysis population included 76 control users and 74 treatment users. Assignment was intended to be even, but the final counts reflect production imperfections. Events were collected across web, mobile web, iOS, and Android. The event stream records country, platform, segment, event name, conversion flag, revenue where applicable, and a tracking-quality indicator. The experiment was evaluated using an intent-to-treat approach so that users remained in their assigned variant even if they did not engage deeply with the feature.
- Source IDs: Transparent Discount Price Framing | Transparent Discount Price Framing | Transparent Discount Price Framing | Transparent Discount Price Framing | Transparent Discount Price Framing
- Structured Field IDs: none
- Explanation: This case expected a needs-more-data or insufficient-evidence outcome, but the answer remained assertive.
- Classification: true_positive
- Remediation Status: strengthen_abstention_behavior

### Finding 6

- Case: exp-006-insufficient-evidence
- Surface: legacy_rag
- Category: answer_generated_when_abstention_was_expected
- Severity: high
- Detector: deterministic.abstention
- Exact Flagged Claim: Mock evaluation answer generated from retrieved context.
- Normalized Claim: mock evaluation answer generated from retrieved context.
- Expected Evidence: none
- Available Evidence: ## Limitations

This experiment has limitations that should be preserved in the synthetic data because they are common in production testing. Notable imperfections were: Sample ratio mismatch from delayed exclusion of dormant loyalty accounts.; Novelty effect in the first three days increased progress-panel clicks.. These issues do not make the dataset unusable, but they change how confident a decision maker should be. The sample is intentionally small for repository practicality, so the reports describe realistic directional decisions rather than definitive statistical proof. Some country and platform segments are sparse, and several metrics are proxies for longer-term outcomes that would normally require follow-up measurement. | ## Risks

The main risk is that the treatment effect may not generalize when exposed to broader traffic. Too many loyalty prompts can make transactional surfaces feel promotional. There is also risk in over-reading aggregate lift when one country, platform, or segment contributes disproportionately. Tracking issues can create false confidence if they align with the treatment experience. Finally, product teams may be tempted to ship from the headline metric alone, but each report is written to require a business decision that balances upside, guardrails, and data quality.
- Source IDs: Loyalty Tier Progress Nudges | Loyalty Tier Progress Nudges | Loyalty Tier Progress Nudges | Loyalty Tier Progress Nudges | Loyalty Tier Progress Nudges
- Structured Field IDs: none
- Explanation: This case expected a needs-more-data or insufficient-evidence outcome, but the answer remained assertive.
- Classification: true_positive
- Remediation Status: strengthen_abstention_behavior

### Finding 7

- Case: exp-007-insufficient-evidence
- Surface: legacy_rag
- Category: answer_generated_when_abstention_was_expected
- Severity: high
- Detector: deterministic.abstention
- Exact Flagged Claim: Mock evaluation answer generated from retrieved context.
- Normalized Claim: mock evaluation answer generated from retrieved context.
- Expected Evidence: none
- Available Evidence: ## Results

Control recorded 0.0730 on reactivation_purchase_rate, while treatment recorded 0.0910. The absolute movement was 0.0180, and the supporting metrics were directionally consistent with the business read. The result was not interpreted mechanically from a single p-value. Instead, the team considered the size of the effect, product risk, operational cost, and segment behaviour. Metric rows in `metrics.csv` include sample size, the primary metric, and secondary diagnostics for both variants. Event rows in `events.csv` allow future retrieval tests to connect aggregate conclusions back to realistic user-level evidence. | ## Experiment Design

Users were assigned to control and treatment at the user level. Control retained the existing product experience, while treatment received the proposed change. The analysis population included 73 control users and 77 treatment users. Assignment was intended to be even, but the final counts reflect production imperfections. Events were collected across web, mobile web, iOS, and Android. The event stream records country, platform, segment, event name, conversion flag, revenue where applicable, and a tracking-quality indicator. The experiment was evaluated using an intent-to-treat approach so that users remained in their assigned variant even if they did not engage deeply with the feature.
- Source IDs: CRM Back-in-Stock Notification Timing | CRM Back-in-Stock Notification Timing | CRM Back-in-Stock Notification Timing | CRM Back-in-Stock Notification Timing | CRM Back-in-Stock Notification Timing
- Structured Field IDs: none
- Explanation: This case expected a needs-more-data or insufficient-evidence outcome, but the answer remained assertive.
- Classification: true_positive
- Remediation Status: strengthen_abstention_behavior

### Finding 8

- Case: exp-008-insufficient-evidence
- Surface: legacy_rag
- Category: answer_generated_when_abstention_was_expected
- Severity: high
- Detector: deterministic.abstention
- Exact Flagged Claim: Mock evaluation answer generated from retrieved context.
- Normalized Claim: mock evaluation answer generated from retrieved context.
- Expected Evidence: none
- Available Evidence: ## Experiment Design

Users were assigned to control and treatment at the user level. Control retained the existing product experience, while treatment received the proposed change. The analysis population included 79 control users and 79 treatment users. Assignment was intended to be even, but the final counts reflect production imperfections. Events were collected across web, mobile web, iOS, and Android. The event stream records country, platform, segment, event name, conversion flag, revenue where applicable, and a tracking-quality indicator. The experiment was evaluated using an intent-to-treat approach so that users remained in their assigned variant even if they did not engage deeply with the feature. | # Personalized Similar-Item Recommendations
- Source IDs: Personalized Similar-Item Recommendations | Personalized Similar-Item Recommendations | Personalized Similar-Item Recommendations | Personalized Similar-Item Recommendations | Personalized Similar-Item Recommendations
- Structured Field IDs: none
- Explanation: This case expected a needs-more-data or insufficient-evidence outcome, but the answer remained assertive.
- Classification: true_positive
- Remediation Status: strengthen_abstention_behavior

### Finding 9

- Case: exp-009-insufficient-evidence
- Surface: legacy_rag
- Category: answer_generated_when_abstention_was_expected
- Severity: high
- Detector: deterministic.abstention
- Exact Flagged Claim: Mock evaluation answer generated from retrieved context.
- Normalized Claim: mock evaluation answer generated from retrieved context.
- Expected Evidence: none
- Available Evidence: # Dynamic Search Filter Shortcuts | ## Background

Dynamic Search Filter Shortcuts was designed for the ExperimentOS synthetic corpus as a realistic example of a product experimentation decision. The product area was search filters, and the team needed evidence that would be useful for a future ingestion and retrieval pipeline, not a perfect classroom test. The baseline experience already had meaningful traffic and some known operational constraints, so the experiment deliberately includes realistic noise. The owner was Noah Brown from Search Experience. Traffic ran from 2026-06-03 through 2026-06-17, long enough to observe weekday and weekend behaviour but short enough that market conditions could still influence the result. The dataset includes user-level events, aggregate metrics, metadata, and this decision report.
- Source IDs: Dynamic Search Filter Shortcuts | Dynamic Search Filter Shortcuts | Dynamic Search Filter Shortcuts | Dynamic Search Filter Shortcuts | Dynamic Search Filter Shortcuts
- Structured Field IDs: none
- Explanation: This case expected a needs-more-data or insufficient-evidence outcome, but the answer remained assertive.
- Classification: true_positive
- Remediation Status: strengthen_abstention_behavior

### Finding 10

- Case: exp-010-insufficient-evidence
- Surface: legacy_rag
- Category: answer_generated_when_abstention_was_expected
- Severity: high
- Detector: deterministic.abstention
- Exact Flagged Claim: Mock evaluation answer generated from retrieved context.
- Normalized Claim: mock evaluation answer generated from retrieved context.
- Expected Evidence: none
- Available Evidence: ## Experiment Design

Users were assigned to control and treatment at the user level. Control retained the existing product experience, while treatment received the proposed change. The analysis population included 77 control users and 73 treatment users. Assignment was intended to be even, but the final counts reflect production imperfections. Events were collected across web, mobile web, iOS, and Android. The event stream records country, platform, segment, event name, conversion flag, revenue where applicable, and a tracking-quality indicator. The experiment was evaluated using an intent-to-treat approach so that users remained in their assigned variant even if they did not engage deeply with the feature. | ## Future Work

Future work should include a larger follow-up test or monitored rollout, depending on the decision status. The next analysis should check whether the primary metric movement persists after novelty effects fade, whether country-specific behaviour remains stable, and whether any tracking caveats have been fixed. Future ingestion work can parse this report, link it to metadata and CSV evidence, and produce embeddings or chunks that support questions such as why the decision was made, which imperfections mattered, and what follow-up work was recommended.
- Source IDs: Premium Subscription Trial Offer | Premium Subscription Trial Offer | Premium Subscription Trial Offer | Premium Subscription Trial Offer | Premium Subscription Trial Offer
- Structured Field IDs: none
- Explanation: This case expected a needs-more-data or insufficient-evidence outcome, but the answer remained assertive.
- Classification: true_positive
- Remediation Status: strengthen_abstention_behavior

## Policy Reasons

- Some cases could not be parsed conservatively into explicit claims.

## Judge Metrics

| Framework | Metric | Case | Score | Status | Reason |
| --- | --- | --- | ---: | --- | --- |
| deepeval | faithfulness | exp-001-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-001-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-001-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-001-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-001-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-001-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-001-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-001-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-001-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-001-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-001-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-001-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-001-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-001-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-001-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-001-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-001-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-001-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-001-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-001-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-001-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-001-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-001-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-001-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-002-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-002-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-002-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-002-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-002-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-002-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-002-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-002-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-002-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-002-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-002-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-002-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-002-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-002-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-002-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-002-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-002-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-002-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-002-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-002-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-002-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-002-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-002-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-002-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-003-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-003-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-003-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-003-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-003-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-003-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-003-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-003-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-003-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-003-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-003-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-003-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-003-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-003-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-003-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-003-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-003-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-003-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-003-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-003-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-003-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-003-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-003-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-003-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-004-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-004-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-004-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-004-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-004-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-004-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-004-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-004-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-004-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-004-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-004-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-004-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-004-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-004-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-004-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-004-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-004-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-004-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-004-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-004-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-004-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-004-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-004-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-004-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-005-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-005-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-005-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-005-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-005-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-005-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-005-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-005-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-005-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-005-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-005-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-005-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-005-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-005-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-005-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-005-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-005-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-005-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-005-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-005-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-005-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-005-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-005-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-005-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-006-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-006-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-006-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-006-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-006-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-006-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-006-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-006-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-006-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-006-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-006-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-006-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-006-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-006-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-006-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-006-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-006-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-006-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-006-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-006-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-006-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-006-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-006-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-006-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-007-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-007-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-007-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-007-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-007-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-007-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-007-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-007-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-007-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-007-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-007-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-007-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-007-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-007-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-007-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-007-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-007-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-007-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-007-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-007-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-007-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-007-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-007-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-007-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-008-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-008-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-008-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-008-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-008-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-008-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-008-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-008-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-008-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-008-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-008-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-008-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-008-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-008-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-008-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-008-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-008-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-008-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-008-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-008-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-008-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-008-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-008-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-008-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-009-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-009-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-009-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-009-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-009-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-009-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-009-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-009-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-009-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-009-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-009-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-009-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-009-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-009-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-009-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-009-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-009-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-009-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-009-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-009-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-009-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-009-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-009-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-009-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-010-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-010-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-010-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-010-rollout-decision |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-010-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-010-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-010-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-010-factual-retrieval |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-010-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-010-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-010-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-010-result-interpretation |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-010-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-010-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-010-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-010-risk-guardrail |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-010-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-010-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-010-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-010-business-impact |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-010-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-010-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-010-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-010-insufficient-evidence |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-001-legacy-rag-lookup |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-001-legacy-rag-lookup |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-001-legacy-rag-lookup |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-001-legacy-rag-lookup |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | exp-004-legacy-rag-lookup |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | exp-004-legacy-rag-lookup |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | exp-004-legacy-rag-lookup |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | exp-004-legacy-rag-lookup |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | lookup-payment |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | lookup-payment |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | lookup-payment |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | lookup-payment |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | decision-loyalty-rollout |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | decision-loyalty-rollout |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | decision-loyalty-rollout |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | decision-loyalty-rollout |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | decision-pricing-do-not-rollout |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | decision-pricing-do-not-rollout |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | decision-pricing-do-not-rollout |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | decision-pricing-do-not-rollout |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | summary-checkout-pending |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | summary-checkout-pending |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | summary-checkout-pending |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | summary-checkout-pending |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | summary-loyalty-revision-requested |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | summary-loyalty-revision-requested |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | summary-loyalty-revision-requested |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | summary-loyalty-revision-requested |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | risk-search-filters |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | risk-search-filters |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | risk-search-filters |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | risk-search-filters |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | impact-search-ranking |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | impact-search-ranking |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | impact-search-ranking |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | impact-search-ranking |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | faithfulness | decision-premium-needs-more-data |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | hallucination | decision-premium-needs-more-data |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | contextual_relevancy | decision-premium-needs-more-data |  | skipped | Judge metrics are disabled in offline mode. |
| deepeval | answer_relevancy | decision-premium-needs-more-data |  | skipped | Judge metrics are disabled in offline mode. |

## Limitations

- Deterministic checks are conservative and do not prove universal factual correctness.
- Numerical and workflow assertions remain deterministic; judge metrics are optional.
- Offline mode never invokes a live provider.
