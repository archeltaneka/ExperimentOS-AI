## Phase 3 Reliability Baseline

Phase 3 now includes a repository-owned factuality evaluation layer in addition to the existing
RAG, agent workflow, prompt regression, RAGAS, and DeepEval surfaces.

### Factuality Evaluation

- entrypoint: `packages.evals.run_factuality`
- CLI wrapper: `packages.evals.cli`
- default outputs:
  - `reports/phase3/factuality_report.md`
  - `reports/phase3/factuality_report.json`
- default mode: `offline`
- default target: `all`
- evaluated surfaces:
  - `legacy_rag` answers
  - deterministic `agent_workflow` state outputs including final answer resolution,
    `decision.rationale`, and `executive_summary.summary`

Current factuality coverage includes:

- unsupported factual and numerical claims
- fabricated revenue or ROI
- fabricated statistical significance
- fabricated experiment results
- citation presence and citation identifier failures
- contradictions with structured workflow state
- overconfident insufficient-evidence responses
- abstention failures

Current deterministic checks are conservative and remain authoritative for:

- citation presence
- structured contradictions
- recommendation and approval consistency
- grounded numerical checks
- business-impact guardrails
- significance and p-value guardrails

Optional judge checks are available only when explicitly enabled. The factuality runner currently
reuses the existing DeepEval adapter for:

- `faithfulness`
- `hallucination`
- `contextual_relevancy`
- `answer_relevancy`

Judge mode is not part of the default baseline command and is not required for local offline runs.

### Readiness Notes

The factuality layer improves Phase 3 readiness for later quality gates, but several gaps remain:

- production responses are not blocked yet
- no automatic answer repair or regeneration exists
- no human fact-check review UI exists
- CI thresholds are not enforced yet

This keeps the repository honest about what the current checks can and cannot prove.
