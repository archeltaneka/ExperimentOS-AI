## Factuality And Hallucination Checks

ExperimentOS AI now includes a repository-owned factuality layer for evaluation and reporting.
It is designed to reduce unsupported-claim risk across `legacy_rag` and default
`agent_workflow` surfaces without claiming that hallucination detection is solved.

### Hallucination Taxonomy

The current taxonomy records findings in these categories:

- `unsupported_factual_claim`
- `unsupported_numerical_claim`
- `fabricated_revenue_or_roi`
- `fabricated_statistical_significance`
- `fabricated_experiment_result`
- `citation_missing`
- `citation_does_not_support_claim`
- `contradiction_with_retrieved_context`
- `contradiction_with_structured_experiment_data`
- `overconfident_answer_with_insufficient_evidence`
- `answer_generated_when_abstention_was_expected`

Every finding records:

- category
- severity
- claim
- evidence
- source IDs
- detector
- confidence
- explanation
- metadata

Severity levels are `low`, `medium`, `high`, and `critical`.

### Deterministic Checks

The offline-first path runs deterministic checks only. These remain authoritative for exact
workflow assertions, structured contradictions, arithmetic-style numerical grounding, and
citation presence.

Current deterministic checks cover:

- citation presence against expected citation minimums
- citation identifier validity against retrieved evidence
- numerical grounding for structured experiment and workflow values
- revenue and ROI guardrails when business-impact inputs are absent or contradictory
- statistical-claim validation for significance and p-values
- abstention correctness for insufficient-evidence cases
- structured consistency across decision, approval, and executive-summary outputs
- conservative evidence coverage for recommendation-style prose

Numerical and workflow checks are deterministic on purpose. The repository does not use judge
models to validate arithmetic, recommendation state, or approval state when those values already
exist in machine-readable form.

### Judge-Based Checks

Judge mode is explicit. Offline mode remains the default and does not call a live provider.

The current factuality runner reuses the existing DeepEval adapter surface for optional metrics:

- `faithfulness`
- `hallucination`
- `contextual_relevancy`
- `answer_relevancy`

If judge mode is selected without a configured provider or model, the metrics are skipped with a
recorded reason. If DeepEval bindings are unavailable, the metrics are also skipped with a clear
reason. Existing RAGAS and DeepEval reports remain available independently through their original
entrypoints.

### Conservative Claim Extraction

Claim extraction is intentionally simple and testable:

- it prefers structured workflow fields over free-text parsing
- it extracts only short rule-based sentences from final answers and summary fields
- it separates numerical and non-numerical checks
- it records unparsed non-specific prose instead of silently treating it as grounded

This version does not attempt a full NLP or entailment pipeline.

### Policy And Configuration

The factuality policy is configured in `config/evaluation/factuality.json`.

Current thresholds include:

- zero critical violations allowed
- zero unsupported numerical claims allowed
- zero fabricated financial claims allowed
- zero fabricated statistical claims allowed
- minimum citation coverage of `1.0`
- zero unresolved medium-severity findings allowed
- optional judge thresholds per metric

The policy result is one of:

- `pass`
- `fail`
- `warning`
- `skipped`

The deterministic policy is consumed by the centralized quality policy and enforced by the CI
`ai-quality-gate`. It does not block or rewrite production responses at runtime.

### CLI And Reports

Direct entrypoint:

```powershell
uv run python -m packages.evals.run_factuality
```

CLI wrapper:

```powershell
uv run python -m packages.evals.cli factuality
```

Useful options:

- `--mode offline`
- `--mode judge`
- `--target legacy_rag`
- `--target agent_workflow`
- `--case-id <id>`
- `--category <category>`
- `--report-dir <dir>`
- `--fail-on-violation`

Default outputs:

- `reports/phase3/factuality_report.md`
- `reports/phase3/factuality_report.json`

Reports include:

- dataset identifiers
- checks executed and skipped
- findings by category and severity
- per-case citation coverage
- prompt provenance where available
- judge provider and model when used
- policy result
- explicit limitations

### Adding A Detector

1. Add the detector logic in `packages/evals/factuality/deterministic.py` or a future dedicated
   detector module.
2. Emit repository-owned `FactualityFinding` objects rather than third-party result objects.
3. Add focused tests in `tests/test_factuality.py`.
4. Update this document if the taxonomy or policy semantics change.

### Adding A Test Case

For detector-level coverage, add a focused unit case in `tests/test_factuality.py`.

For broader workflow coverage, prefer reusing:

- `data/eval/qa_dataset.json`
- `data/eval/agent_dataset.json`
- existing legacy QA and agent workflow evaluation outputs

### Known Limitations

- The deterministic layer is conservative and cannot prove semantic support universally.
- Legacy `legacy_rag` citations remain document-level, so support checks there are narrower than
  the quote-based agent-workflow evidence surface.
- Offline mode detects many unsupported numerical, financial, statistical, and workflow
  contradictions, but it does not guarantee prose-level truthfulness in every case.
- Judge metrics can help with broader faithfulness signals, but they are optional and not used as
  authoritative replacements for deterministic checks.

Hallucination detection reduces risk. It does not prove universal factual correctness.
