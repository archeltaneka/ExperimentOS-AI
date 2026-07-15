# Phase 3 Quality Policy

The Phase 3 quality policy is the repository-owned threshold layer that turns the current
evaluation outputs into a single ExperimentOS pass, warning, fail, or skipped decision.

## Architecture

- policy config: `config/evaluation/quality_policy.yaml`
- evaluator package: `packages/evals/policy/`
- CLI entrypoint: `packages.evals.run_quality_policy`
- primary CLI: `python -m packages.evals.run_quality_policy`
- default outputs:
  - `reports/phase3/quality_policy.md`
  - `reports/phase3/quality_policy.json`

The evaluator does not rerun evaluations. It reads existing report artifacts, normalizes them into
ExperimentOS metric IDs, applies the configured thresholds, aggregates category results, and emits
machine-readable and Markdown summaries.

## Covered Frameworks

The current policy consumes these report surfaces:

- custom RAG evaluation: `reports/evaluation.md`
- custom agent workflow evaluation: `reports/agent_evaluation.md`
- `/ask` end-to-end evaluation: `reports/agent_e2e_evaluation.md`
- RAGAS: `reports/phase3/ragas_report.json`
- DeepEval: `reports/phase3/deepeval_report.json`
- prompt regression: `reports/phase3/prompt_regression.json`
- factuality evaluation: `reports/phase3/factuality_report.json`

This keeps the policy ExperimentOS-owned while still reusing additive framework outputs where they
already exist.

## Normalization

Adapters translate report-specific fields into centralized metric IDs such as:

- `rag.retrieval_success_rate`
- `agent.routing_accuracy`
- `agent_e2e.default_agent_workflow_coverage`
- `ragas.id_based_context_precision`
- `deepeval.trace_completeness.average_score`
- `prompt_regression.summary.pass_rate`
- `factuality.findings.fabricated_revenue_or_roi`

RAGAS and DeepEval payloads stay inside adapters. The policy core only sees normalized
ExperimentOS metrics plus generic threshold metadata.

## Categories And Status

The policy reports category status for:

- Retrieval
- Answer Quality
- Workflow
- Prompt
- Factuality
- Reliability

Each category can end in:

- `pass`
- `warning`
- `fail`
- `skipped`

Overall status is the worst status across categories. Required blocking metrics drive `fail`.
Warning-only metrics remain advisory. Optional metrics can be skipped without failing the policy.

## Threshold Configuration

Thresholds are defined in YAML and can be changed without code edits. Each metric entry supports:

- `metric_id`
- `source`
- `category`
- `operator`
- `value`
- `severity`
- `required`
- `weight`
- `tolerance`
- `description`

Current blocking themes include:

- retrieval success and citation coverage
- agent routing, trace completeness, and recommendation coverage
- default `agent_workflow` coverage
- `legacy_rag` fallback compatibility
- prompt regression pass rate and zero regressions
- zero fabricated revenue, zero fabricated significance, zero structured contradictions
- zero abstention failures where insufficient evidence is expected

Current warning-only themes include:

- additive judge metrics when available
- latency thresholds for local evaluation runs

## Offline And CI Behavior

Offline mode remains the default operating mode for the policy because it only consumes existing
local reports. Optional judge-backed metrics from RAGAS and DeepEval are treated as advisory and
can remain skipped without causing a failure.

GitHub Actions now consumes the structured policy outputs through the repository-owned AI quality
gate scripts. The policy remains machine-readable and repository-owned; workflow YAML still does
not duplicate thresholds.

## CLI

Run the policy directly:

```powershell
uv run python -m packages.evals.run_quality_policy
```

Useful options:

- `--policy <path>` to load a different YAML policy
- `--report-dir <path>` to point at another report bundle
- `--warning-policy allow|fail` to decide whether warning-only outcomes should fail
- `--strict` as a short alias for `--warning-policy fail`
- `--warn-only` to preserve report status but always return success

## Adding New Metrics

When a new deterministic evaluation metric becomes available:

1. Extend the appropriate adapter in `packages/evals/policy/adapters.py`.
2. Normalize the metric to a repository-owned ExperimentOS metric ID.
3. Add a threshold entry in `config/evaluation/quality_policy.yaml`.
4. Add or update tests in `tests/test_quality_policy.py`.
5. Update this document if the category mapping or semantics changed.

Do not expose framework-native types outside adapters and do not scatter thresholds throughout the
codebase.

## Versioning

The YAML file carries the policy version. Bump it when threshold semantics or metric coverage
change in a way that should be visible to CI consumers or report readers.
