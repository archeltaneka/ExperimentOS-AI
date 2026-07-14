## Phase 3 Reliability Baseline

Phase 3 now includes a repository-owned factuality evaluation layer plus optional LangSmith,
Phoenix, and OpenTelemetry observability adapters in addition to the existing RAG, agent
workflow, prompt regression, prompt experiments, RAGAS, DeepEval, and centralized quality policy
surfaces.

### Quality Policy

- implementation status: available
- entrypoint: `packages.evals.run_quality_policy`
- shared CLI surface: `packages.evals.cli quality-policy`
- config path: `config/evaluation/quality_policy.yaml`
- default outputs:
  - `reports/phase3/quality_policy.md`
  - `reports/phase3/quality_policy.json`
- covered frameworks:
  - custom RAG evaluation
  - custom agent workflow evaluation
  - `/ask` end-to-end evaluation
  - RAGAS
  - DeepEval
  - prompt regression
  - factuality evaluation
- category coverage:
  - Retrieval
  - Answer Quality
  - Workflow
  - Prompt
  - Factuality
  - Reliability
- current blocking thresholds include:
  - retrieval success and citation coverage
  - offline RAGAS id-based precision and recall
  - default `agent_workflow` coverage
  - `legacy_rag` fallback coverage
  - agent routing, trace completeness, and decision or approval coverage
  - prompt regression pass rate with zero regressions
  - zero fabricated revenue or ROI
  - zero fabricated statistical significance
  - zero structured contradictions
  - zero abstention failures when insufficient evidence is expected
- warning-only thresholds include:
  - latency
  - optional judge-backed RAGAS metrics
  - optional judge-backed DeepEval metrics

Remaining quality policy gaps:

- GitHub Actions enforcement now runs through `ai-quality-gate`
- baseline runs still rely on additive report artifacts for full policy coverage
- no PR annotation, deployment blocking beyond repository CI, or threshold auto-tuning exists
- the authoritative status is the latest quality-policy artifact, not this static document

### CI Quality Gate

- implementation status: enabled on `pull_request`, pushes to `main`, and manual dispatch
- job name: `ai-quality-gate`
- policy owner: `config/evaluation/quality_policy.yaml`
- environment mode: offline and deterministic only
- required suites:
  - custom RAG
  - custom agent workflow
  - `/ask` end-to-end
  - prompt regression
  - factuality
  - quality-policy aggregation
- additive offline suites:
  - prompt experiment sample
  - RAGAS offline-safe metrics
  - DeepEval offline deterministic metrics
- artifact publication: always
- branch-protection relationship: CI gate is designed to support blocking protection on `main`
- remaining gap before PR reporting: no automated PR comment or inline annotation yet

### Prompt Experiment Framework

- implementation status: available for offline `rag.answer` comparisons
- default runtime status: disabled
- production traffic status: no public traffic experimentation
- assignment mode: deterministic and reproducible only
- exposure policy: recorded only when a prompt is actually rendered
- evaluation reuse:
  - prompt registry
  - prompt regression
  - factuality checks
  - RAGAS and DeepEval through the existing comparison stack
- observability status:
  - safe experiment metadata is attached to ExperimentOS-owned spans
  - assignment-key hashes are excluded from trace and metric attributes
- current report outputs:
  - `reports/phase3/prompt_experiments/<experiment_id>.md`
  - `reports/phase3/prompt_experiments/<experiment_id>.json`

Remaining prompt experiment gaps:

- runtime assignment is intentionally not wired into public traffic
- offline CLI defaults use deterministic fixture retrieval rather than a database-backed corpus
- no automatic prompt promotion exists
- no CI quality gate consumes the experiment recommendation yet

### Observability Status

- integration status: LangSmith, Phoenix, and OpenTelemetry available behind the shared provider
  interface
- runtime requirement: optional dependency group plus explicit enablement
- default mode: disabled
- authoritative traces: ExperimentOS-owned state, metrics, and reports remain primary
- provider architecture: NoOp, LangSmith, OpenTelemetry, Phoenix compatibility path, or Composite
- OpenTelemetry role: vendor-neutral propagation plus trace and metric export
- Phoenix reuse status: Phoenix OTLP export now shares the OpenTelemetry provider when both are
  enabled
- traces enabled: yes when explicitly enabled
- metrics enabled: yes when explicitly enabled
- propagation support: W3C Trace Context for FastAPI when enabled
- exporter support:
  - none
  - console
  - in-memory
  - OTLP HTTP
- instrumented surfaces:
  - `/ask`
  - `agent_workflow`
  - `legacy_rag`
  - retrieval
  - prompt provenance for prompt-backed flows
  - evaluation entrypoints
- hierarchy coverage:
  - request root
  - workflow or legacy roots
  - deterministic agent node exports
  - response serialization
- redaction coverage:
  - secrets
  - tokens
  - cookies
  - database URLs
  - prompt bodies by default
  - response bodies by default
  - retrieved document chunks by default
- sampling support: OpenTelemetry provider-owned tracing plus preserved ExperimentOS correlation ids
- correlation support: `experimentos_trace_id` is attached to exported traces
- cardinality controls: request ids, trace ids, prompt text, and raw user text are excluded from
  metric dimensions
- Phoenix mode: manual ExperimentOS spans only, with no LangChain or LangGraph auto-instrumentor
- LangSmith coexistence: independent sink, same internal logical spans, same ExperimentOS
  correlation metadata

Remaining observability gaps:

- production alerting is not implemented
- distributed tracing across multiple services is still out of scope
- CI threshold policies remain separate from tracing
- Phoenix datasets, experiments, annotations, and hosted evaluations remain out of scope
- no log export is implemented

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
- quality policy thresholds are repository-owned now, but CI enforcement is not implemented yet

This keeps the repository honest about what the current checks can and cannot prove.
