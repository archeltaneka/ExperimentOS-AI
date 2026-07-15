# Phase 3 Closeout

## Original Objectives

Phase 3 added deterministic LLMOps and AI-reliability controls around the existing RAG and
agent-workflow product surfaces. The objective was one coherent, production-oriented portfolio
system with repository-owned evaluation, prompt lifecycle, observability, and CI policy—not proof
of production deployment at scale.

Issue #68 is the cross-capability reliability review. This document records its closeout evidence;
it does not state that the GitHub issue itself is closed.

## Delivered Capabilities

| Issue | Capability | Implementation and evidence |
| --- | --- | --- |
| #53 Phase 3 planning and reliability baseline | Baseline orchestration | `packages/evals/baseline.py`, `packages/evals/run_baseline.py`, `tests/test_phase3_baseline.py`, and `reliability_baseline.md` |
| #54 Evaluation dataset expansion | Versioned QA and agent contracts | `data/eval/qa_dataset.json`, `data/eval/agent_dataset.json`, dataset loaders, manifests, and dataset-integrity tests |
| #55 RAGAS evaluation integration | Optional RAGAS adapter | `packages/evals/ragas_adapter.py`, `packages/evals/run_ragas.py`, `tests/test_ragas_evaluation.py`, and `reliability_baseline.md` |
| #56 DeepEval evaluation integration | Optional DeepEval adapter | `packages/evals/deepeval_adapter.py`, `packages/evals/run_deepeval.py`, `tests/test_deepeval_evaluation.py`, and `reliability_baseline.md` |
| #57 Prompt registry foundation | Immutable prompt versions and provenance | `packages/llm/prompt_registry.py`, registry CLI/tests, and `prompt_registry.md` |
| #58 Prompt regression testing | Frozen-retrieval comparison | `packages/evals/prompt_regression.py`, its CLI/tests, and `prompt_regression.md` |
| #59 Hallucination and factuality checks | Deterministic zero-tolerance invariants | `packages/evals/factuality/`, factuality tests/reports, and `factuality_and_hallucination.md` |
| #60 LangSmith tracing integration | Optional sink adapter | `packages/observability/langsmith.py`, provider tests, dry-run CLI, and `langsmith_observability.md` |
| #61 Phoenix observability integration | Optional Phoenix/OpenInference-compatible sink | `packages/observability/phoenix.py`, provider tests, dry-run CLI, and `phoenix_observability.md` |
| #62 OpenTelemetry instrumentation | Vendor-neutral trace and metric export | `packages/observability/opentelemetry.py`, in-memory exporter tests, and `opentelemetry.md` |
| #63 Prompt A/B testing framework | Deterministic offline prompt experiments | `packages/evals/prompt_experiments/`, experiment CLI/tests/reports, and `prompt_experiments.md` |
| #64 Evaluation threshold policy | Centralized authoritative policy | `config/evaluation/quality_policy.yaml`, `packages/evals/policy/`, policy tests/reports, and `quality_policy.md` |
| #65 GitHub Actions CI baseline | Offline and database CI tiers | `.github/workflows/ci.yml`, workflow contract tests, and `github_actions.md` |
| #66 CI quality gates for AI evaluation | Strict AI gate and artifacts | `scripts/run_ai_quality_gate.py`, gate tests/reports, and `ci_quality_gates.md` |
| #67 Pull request evaluation reports | Bounded informational reports | `packages/evals/run_ci_report.py`, reporting tests/artifacts, and `pr_evaluation_reports.md` |
| #68 Phase 3 end-to-end reliability review | Strict closeout orchestration and final reports | `scripts/verify_phase3.py`, `packages/evals/phase3_verification/`, final-layer tests, and this closeout document |

The generated capability inventory in `reports/phase3/final_reliability_review.md` records each
capability's implementation, configuration, CLI, tests, reports, docs, optional dependencies,
default state, external requirements, and limitations.

## Architectural Decisions

- ExperimentOS-owned models and JSON reports are authoritative for evaluation results, traces,
  metrics, prompt provenance, and quality-policy decisions.
- RAGAS and DeepEval adapt repository-owned cases; their types do not enter core services.
- LangSmith and Phoenix are optional sinks. OpenTelemetry is the vendor-neutral export layer.
- GitHub Actions orchestrates repository commands; thresholds remain in
  `config/evaluation/quality_policy.yaml` rather than workflow YAML.
- `agent_workflow` remains the default and deterministic agents remain prompt-free.
- `legacy_rag` remains compatible and is the prompt-backed RAG surface.
- `rag.answer` is the only initially experimentable prompt surface.
- Prompt experiment context is internal, no prompt is promoted automatically, and offline A/B
  evidence does not establish production causal impact.
- `POST /ask` retains its public request and response contract. External run identifiers and
  internal experiment controls are not public API fields.

## Quality Guarantees

The default verification environment uses fake embeddings, mock generation, no external judges,
disabled prompt experiments, disabled observability exports, and a fixed hash seed. The test suite
blocks non-loopback sockets. Missing optional dependencies fail clearly only when their integration
is explicitly enabled.

Strict policy retains zero tolerance for fabricated revenue or ROI, fabricated statistical
significance, fabricated experiment results, structured decision contradictions, and approval-state
contradictions. Missing detectors or malformed/missing reports fail verification; skipped optional
judge metrics are recorded and are not converted to zero.

## Local Strict Verification

Install dependencies and start the repository's PostgreSQL 16 plus pgvector service:

```powershell
uv sync --all-groups --frozen
docker compose up -d postgres
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run alembic upgrade head
uv run python scripts/verify_phase3.py
```

If the ignored deterministic corpus is absent, regenerate it before strict verification:

```powershell
uv run python scripts/generate_synthetic_experiments.py
```

The generator deletes and recreates `data/synthetic/experiments`. Do not run it over local data you
want to preserve. Strict verification requires every QA experiment fixture, migrates the configured
database, ingests each fixture twice to check repeatability, runs database/API/workflow tests, runs
the complete offline AI quality gate, builds and validates CI reports, validates all required
artifacts, and writes:

- `reports/phase3/final_reliability_review.md`
- `reports/phase3/final_reliability_review.json`

The command exits non-zero for command, configuration, migration, report, policy, or factuality
failures. It never starts Docker and never weakens thresholds.

## Offline-Only Diagnostic

Use the explicit non-closeout diagnostic when PostgreSQL is unavailable:

```powershell
uv run python scripts/verify_phase3.py --offline-only
```

This mode validates configuration, formatting, lint, prompts, datasets, observability dry-runs,
focused tests, prompt regression, factuality, and a sample offline prompt experiment. It skips the
database-backed gate and can never recommend `ready_to_close`.

## CI Behavior and Required Checks

CI makes fake/mock providers explicit, runs no live judges or exports, preserves prerequisite and
quality-gate failure codes, and uploads partial reports with `if: always()`. The policy YAML is the
only threshold authority. Job summaries and bounded PR comments summarize ExperimentOS reports;
comments are informational, fork-safe, updateable, and not merge-authoritative.

Stable checks recommended as required on `main` are:

- `format`
- `lint`
- `unit`
- `integration-db`
- `ai-quality-gate`

PR reporting (`pr-quality-comment`) is not required for merge eligibility.

## Production Readiness Boundaries

This is a production-oriented portfolio system, not proof of production deployment at scale.
Strict local and CI evidence establishes deterministic integration behavior and policy enforcement.
It does not establish live-vendor availability, production capacity, multi-service propagation,
operational alerting, or behavior under real traffic.

The clean migration path verifies extension creation against the repository's pgvector image. A
server where the pgvector extension package is physically absent is not part of default verification
because that requires a second, non-project database image; Alembic still fails explicitly in that
environment.

## Known Limitations

- Live OpenAI, LangSmith, Phoenix, and OTLP connectivity is not exercised by default.
- Optional judge-backed semantic metrics are opt-in and supplementary.
- Vendor dry-runs and in-memory exporters do not prove collector or hosted-service availability.
- Prompt experiments use offline deterministic assignment and do not measure production causality.
- There is no automatic answer repair, prompt optimization/promotion, scheduled evaluation, or
  production alerting.

## Deferred Work

Cloud deployment, Kubernetes, dashboards, scheduled jobs, automatic prompt optimization,
multi-armed bandits, new agents, public API expansion, and live traffic experiments remain outside
Phase 3.

## Recommended Phase 4 Direction

Treat deployment-specific operational validation as the next boundary: load and soak testing,
collector/service availability checks, alerting objectives, and deployment runbooks. Preserve the
Phase 3 ownership model and add those controls only when a real deployment target exists.
