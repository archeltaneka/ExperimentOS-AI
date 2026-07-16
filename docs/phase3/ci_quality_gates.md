# CI Quality Gates

The `ai-quality-gate` job is the blocking Phase 3 CI layer for deterministic AI evaluation.

## Architecture

Flow:

1. fast verification jobs run first
2. database-backed verification completes
3. `ai-quality-gate` brings up its own PostgreSQL + pgvector service
4. the gate validates the CI environment and policy invariants
5. deterministic evaluation suites run in a fixed order
6. the centralized quality policy aggregates report artifacts
7. the PR-report projection reads the completed structured artifacts
8. artifacts upload with `if: ${{ always() }}`
9. a concise summary is written to `$GITHUB_STEP_SUMMARY`

GitHub Actions only orchestrates the runner, database, and artifact plumbing. The gate logic lives in:

- `scripts/validate_ci_environment.py`
- `scripts/run_ai_quality_gate.py`
- `packages/evals/ci_quality_gate.py`

Threshold evaluation remains centralized in:

- `config/evaluation/quality_policy.yaml`
- `packages/evals/run_quality_policy.py`
- `packages/evals/policy/`

## Required Suites

The blocking gate runs:

- custom RAG evaluation
- custom agent workflow evaluation
- `/ask` end-to-end evaluation
- prompt regression
- factuality evaluation
- centralized quality policy aggregation

It also runs additive offline-safe coverage:

- prompt registry validation
- prompt experiment definition validation
- offline prompt experiment sample
- RAGAS offline-safe metrics
- DeepEval offline deterministic metrics

Judge-backed RAGAS and DeepEval metrics remain optional. They are skipped honestly unless explicitly enabled outside normal CI.

## Offline Provider Configuration

The gate requires:

- `ASK_MODE=agent_workflow`
- `EMBEDDING_PROVIDER=fake`
- `LLM_PROVIDER=mock`
- `RAGAS_JUDGE_LLM_PROVIDER=none`
- `RAGAS_JUDGE_EMBEDDING_PROVIDER=none`
- `DEEPEVAL_JUDGE_PROVIDER=none`
- `PROMPT_EXPERIMENTS_ENABLED=false`
- `EXPERIMENTOS_LANGSMITH_ENABLED=false`
- `EXPERIMENTOS_PHOENIX_ENABLED=false`
- `EXPERIMENTOS_OTEL_ENABLED=false`
- `EXPERIMENTOS_OTEL_EXPORTER_TYPE=none`
- `OPENAI_API_KEY=` and `GOOGLE_API_KEY=`

`scripts/validate_ci_environment.py` fails early if a live provider or external observability export is configured.

## Database Setup

`ai-quality-gate` uses its own PostgreSQL + pgvector service container and does not rely on cross-job service sharing.

The job:

- waits for PostgreSQL readiness
- runs `uv run alembic upgrade head`
- seeds `tests/fixtures/ci/exp-001-payment-recommendation`

This preserves database-backed retrieval coverage while keeping the gate isolated and reproducible.

## Policy Enforcement

The gate does not recalculate thresholds in YAML.

Instead it:

1. generates report artifacts from existing evaluation commands
2. runs `python -m packages.evals.run_quality_policy`
3. reads the centralized policy result
4. fails the job on blocking policy failures

Current exit semantics:

- `0`: pass, or warning-only status when warnings are allowed
- `1`: blocking quality failure
- `2`: infrastructure or evaluator failure

`--warning-policy fail` or `--strict` can turn warning-only outcomes into non-zero exits when desired.

## Artifacts

The gate uploads:

- `evaluation.md` and `evaluation.json`
- `agent_evaluation.md` and `agent_evaluation.json`
- `agent_e2e_evaluation.md` and `agent_e2e_evaluation.json`
- `phase3/prompt_regression.md` and `.json`
- `phase3/factuality_report.md` and `.json`
- `phase3/ragas_report.md` and `.json`
- `phase3/deepeval_report.md` and `.json`
- `phase3/prompt_experiments/<experiment>.md` and `.json` when generated
- `phase3/quality_policy.md` and `.json`
- `phase3/ci_environment.json`
- `phase3/artifact_manifest.json`
- `phase3/ai_quality_gate.json`
- `phase3/github_summary.md`

Uploads always run after pass or fail. Missing optional artifacts warn; missing required artifacts fail the gate through the manifest or policy path.

## Summary Contents

The GitHub job summary includes:

- overall quality status
- policy version
- category statuses
- critical violations
- warnings
- skipped optional metrics
- artifact bundle name
- whether external judges were used
- whether live providers were configured
- whether the policy file changed in the revision

Infrastructure failures and quality failures use the same failed job status but are described differently in the summary.

## Threshold Change Review

The repository-owned policy remains authoritative. To reduce casual weakening:

- the job highlights when `config/evaluation/quality_policy.yaml` changed
- tests enforce critical zero-tolerance invariants for:
  - `fabricated_revenue_or_roi`
  - `fabricated_statistical_significance`
  - `contradiction_with_structured_experiment_data`

Threshold changes still require normal review and branch protection.

## Local Reproduction

```powershell
$env:APP_ENV = "ci"
$env:ASK_MODE = "agent_workflow"
$env:EMBEDDING_PROVIDER = "fake"
$env:LLM_PROVIDER = "mock"
$env:RAGAS_JUDGE_LLM_PROVIDER = "none"
$env:RAGAS_JUDGE_EMBEDDING_PROVIDER = "none"
$env:DEEPEVAL_JUDGE_PROVIDER = "none"
$env:PROMPT_EXPERIMENTS_ENABLED = "false"
$env:EXPERIMENTOS_LANGSMITH_ENABLED = "false"
$env:EXPERIMENTOS_PHOENIX_ENABLED = "false"
$env:EXPERIMENTOS_OTEL_ENABLED = "false"
$env:EXPERIMENTOS_OTEL_EXPORTER_TYPE = "none"
$env:LANGSMITH_TRACING = "false"
$env:LANGSMITH_API_KEY = ""
$env:OPENAI_API_KEY = ""
$env:GOOGLE_API_KEY = ""
$env:PYTHONHASHSEED = "0"
docker compose up -d postgres
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv sync --group dev --group eval --group observability --frozen
uv run alembic upgrade head
uv run python scripts/validate_ci_environment.py --output artifacts/ci/ai-quality/phase3/ci_environment.json
uv run python scripts/run_ai_quality_gate.py --artifact-root artifacts/ci/ai-quality --artifact-name ai-quality-gate-local --policy-changed false
```

For the milestone-wide strict review, use the repository-owned wrapper after the same database
setup:

```powershell
uv run python scripts/verify_phase3.py
```

`uv run python scripts/verify_phase3.py --offline-only` is a non-closeout diagnostic. It skips the
database-backed quality gate and can never recommend `ready_to_close`.

## Troubleshooting

- PostgreSQL readiness or migration failure: infrastructure failure, check the job log before the evaluation commands.
- Missing report artifact: the gate summary and manifest show the missing path; required reports fail the job.
- Malformed JSON report: `run_quality_policy` returns the infrastructure exit code and surfaces the broken source.
- Warning-only policy result: allowed by default; use `--warning-policy fail` to make warnings blocking.
- Optional judge metrics skipped: expected in normal CI; they are not treated as zero.

## Remaining Gaps

Still out of scope:

- inline source annotations without reliable mappings
- automatic baseline updates
- threshold auto-tuning
- live judge-model evaluation
- scheduled nightly reporting

## Pull Request Reporting

`pr_quality_report.json` is an ExperimentOS-owned projection of the policy, gate, manifest,
environment, and suite JSON artifacts. It does not evaluate thresholds. It surfaces bounded
findings, skipped metrics, compatible deltas, suite status, and offline execution details in the
job summary and, when allowed, one updateable PR comment.

The job captures the quality-gate exit code before always-run reporting steps and restores it last.
The authoritative `ai-quality-gate` check therefore still fails on policy and infrastructure
errors. A separate PR-only comment job has `pull-requests: write`; push runs do not. Read-only fork
tokens merely prevent comment publication and never suppress summaries or artifacts.
