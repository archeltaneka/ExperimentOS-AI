# Issue #106 verification record

Date: 2026-09-18. Branch: `106-advanced-causal-conformance`, linked to issue #106.
Implementation base: `788120b6a469ac28d2072d411f6a6ffafb9b4447`.
This record describes the pre-publication verification checkpoint. Publication
was subsequently authorized by the user; no merge or branch-protection change
is part of that authorization.

## Implementation inventory

| Files | Purpose |
| --- | --- |
| `packages/evals/statistical/advanced/{models,registry,checks}.py` | Typed capability metadata, nine-capability deterministic registry, ownership, numerical replay, compatibility gate |
| `advanced/{fixtures,references/*}.py` | Shared existing DGP builders and controlled public-boundary failure scenarios |
| `advanced/{harness,audit,result_checks,comparisons,privacy}.py` | Fresh public executions, observed fit/score audits, capability checks, bounded comparisons and privacy projections |
| `data/eval/phase4_advanced_conformance.json` | 50 ordered advanced reference cases with explicit expected behavior and justified tolerances |
| `packages/evals/statistical/{models,dataset,evaluator,reporting}.py` | Existing Phase 4 contracts, loading, routing, and derived Markdown extension |
| `packages/evals/run_statistical_baseline.py` | Existing canonical command, including required-optional mode |
| `packages/evals/policy/adapters.py`, `config/evaluation/quality_policy.yaml` | Central policy dimensions and critical rules; policy version `2026-09-18` |
| `packages/experiments/analysis/causal/advanced/{conformance,models}.py` | Shared canonical fingerprints, safe execution metadata, owned result digest field |
| Existing DML/HTE result and service files | Public configuration digest, telemetry provenance, refusal-preserving fingerprint failures |
| Existing EconML/DoWhy dependency, adapter and observability files | Absent versus installed-broken classification, digest/provenance emission |
| `tests/test_advanced*.py` | Common, method-specific, negative mutation, dependency, privacy, artifact, and integration checks |
| Existing fixture modules and telemetry/baseline tests | Reuse promoted fixtures; preserve pre-existing gate expectations separately from the advanced additions |
| `.github/workflows/ci.yml`, `tests/test_github_actions_ci.py` | Core coverage and one required-optional Python 3.13 job, using the existing entry point |
| `docs/phase4/advanced_causal_conformance.md`, statistical baseline guide | Architecture, registry, statistical applicability, status, privacy, policy, artifacts, CI, and limits |

The architecture, all capability-specific requirements, tolerance strategy,
fingerprint design, uncertainty/status semantics, and telemetry policy are
documented in [advanced causal conformance](advanced_causal_conformance.md).

## Verification commands

All conformance execution is offline. Optional packages were installed only during
environment setup using the existing frozen dependency groups:

```sh
UV_PROJECT_ENVIRONMENT=/tmp/issue-106-optional UV_CACHE_DIR=/tmp/issue-106-cache uv sync --python 3.13 --group dev --group econml --group dowhy --frozen
```

Setup exited 0: Python 3.13.15, EconML 0.17.0, DoWhy 0.14; 157 packages installed.
Core Python is 3.12.14. Neither EconML nor DoWhy is installed in the core environment.

### Core focused regression

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/test_advanced*.py tests/test_statistical_baseline*.py tests/test_dml*.py tests/test_hte*.py tests/test_econml*.py tests/test_dowhy*.py tests/test_quality_policy.py tests/test_github_actions_ci.py --tb=short
```

Final result: **282 passed, 36 skipped, 1 warning in 49.04s**, exit 0.
The skips are optional-adapter installed-path tests in the core environment.
Controlled absent/broken dependency tests still execute.

### Installed optional adapters

```sh
MPLCONFIGDIR=/tmp/issue-106-mpl PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/issue-106-optional/bin/python -m pytest -q tests/test_advanced*.py tests/test_econml*.py tests/test_dowhy*.py --tb=short
```

Final result: **161 passed, 404 upstream warnings in 14.16s**, exit 0; no skips.

### Phase 3 and existing statistical regressions

```sh
DATABASE_URL='' PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/test_phase3*.py tests/test_observability*.py tests/test_quality_policy.py tests/test_prompt_regression.py tests/test_factuality.py tests/test_evaluation_harness.py tests/test_ragas_evaluation.py tests/test_deepeval_evaluation.py tests/test_ci_quality_gate.py tests/test_github_actions_ci.py tests/test_randomized*.py tests/test_cuped*.py tests/test_sequential*.py tests/test_bayesian*.py tests/test_did*.py tests/test_propensity*.py tests/test_ipw*.py tests/test_observational*.py --tb=short
```

Final result: **780 passed, 2 warnings in 48.17s**, exit 0. The sandboxed run stalled
in existing async tests and was interrupted; this command passed outside the
sandbox with explicit approval. Database-backed tests were not selected.
Plugin autoload was disabled to avoid a preinstalled pytest rerun plugin opening
a local socket; no conformance check was disabled.

### Canonical Phase 4 command, core

```sh
DATABASE_URL='' OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 UV_CACHE_DIR=/tmp/issue-106-cache uv run python -m packages.evals.cli statistical-baseline --json-output /tmp/issue-106-core/statistical_baseline.json --output /tmp/issue-106-core/statistical_baseline.md
```

Exit 0. **142 cases, 0 failed**; overall `pass`, centralized policy `warning`
because advisories remain visible. The original 92 cases are retained alongside
50 advanced cases. Expected optional absence does not block repository DML/HTE.

### Canonical Phase 4 command, required optional adapters

```sh
DATABASE_URL='' MPLCONFIGDIR=/tmp/issue-106-mpl OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 UV_PROJECT_ENVIRONMENT=/tmp/issue-106-optional UV_CACHE_DIR=/tmp/issue-106-cache uv run --no-sync python -m packages.evals.cli statistical-baseline --require-optional econml --require-optional dowhy --json-output /tmp/issue-106-optional-reports/statistical_baseline.json --output /tmp/issue-106-optional-reports/statistical_baseline.md
```

Exit 0: **142 cases, 0 failed**, overall `pass`, centralized policy `warning`.
There are 115 passing and 26 advisory case verdicts plus one existing skipped
case; invalid/abstained execution statuses are counted independently. These flags prevent
an accidentally absent optional adapter from silently skipping the installed job.

### Phase 3 offline evaluation

```sh
DATABASE_URL='' OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 UV_CACHE_DIR=/tmp/issue-106-cache uv run python -m packages.evals.run_prompt_regression --prompt-id rag.answer --baseline-version 1 --candidate-version 1 --offline --dataset data/eval/qa_dataset.json --embedding-provider fake --llm-provider mock --output /tmp/issue-106-phase3/prompt_regression_full.md --json-output /tmp/issue-106-phase3/prompt_regression_full.json
```

Exit 0. Authoritative summary: **63 cases, 63 unchanged, 0 regressions,
0 failures, passed=true**.

```sh
UV_CACHE_DIR=/tmp/issue-106-cache uv run python -m packages.evals.run_factuality --dataset data/eval/ci_smoke_dataset.json --agent-dataset data/eval/agent_dataset.json --target agent_workflow --mode offline --embedding-provider fake --llm-provider mock --output /tmp/issue-106-phase3/factuality_report.md --json-output /tmp/issue-106-phase3/factuality_report.json
```

Exit 0; output `pass`.

Additional diagnostic run: the prompt-regression command with
`--dataset data/eval/ci_smoke_dataset.json` exited 0 but its JSON had **1 failed
legacy-fallback case out of 2**. The existing fallback builder asks a fixed
question absent from that one-question smoke dataset; the full reference dataset
contains it and passes. The fallback builder and smoke dataset were not changed
by #106. This is not represented as a passing evaluation merely because the
command returned zero. An earlier run without an explicit empty `DATABASE_URL`
stalled and was interrupted; subsequent prompt runs explicitly selected the
repository's no-database offline path.

### Static and environment checks

```sh
UV_CACHE_DIR=/tmp/issue-106-cache uv run ruff check .
UV_CACHE_DIR=/tmp/issue-106-cache uv run ruff format --check .
UV_CACHE_DIR=/tmp/issue-106-cache uv run mypy
UV_CACHE_DIR=/tmp/issue-106-cache uv pip check
UV_CACHE_DIR=/tmp/issue-106-cache uv pip check --python /tmp/issue-106-optional/bin/python
git diff --check
```

All exited 0: Ruff clean; 496 files already formatted; mypy found no issues in
124 configured analysis source files; core 184 packages and optional 157 packages
compatible; no whitespace errors. The existing mypy scope was not weakened.

## Review and backward compatibility

An independent read-only review identified false-pass risks and they were fixed
with observed failing negative controls followed by passing verification:

- foreign objects in private model attributes;
- unknown diagnostic strings leaking through artifacts;
- arbitrary strings/objects nested beneath allowed telemetry keys;
- same-fold training masked by plausible aggregate fit reports;
- fingerprint failures replacing normalized invalid-input refusals;
- injected inference failures mislabeled as real execution;
- second-run telemetry not inspected;
- optional absence masking malformed success;
- self-consistent but incorrect returned target population;
- missing compatibility evidence being treated as agreement.

Request audits allow documented validator canonicalization of unordered
declarations, not changes to causal semantics. Actual nuisance observations remain
ephemeral inside the harness; only pass/fail evidence reaches artifacts.

Existing randomized/observational gates and tolerances remain intact. Original
92-case expectations are still asserted on their original subset; separate tests
exercise advanced additions. This does not add estimators, refuters, workflow
integration, hosted tracking, benchmarks, or business-impact calculations.

## Remaining limitations

- The additional existing Phase 3 one-question prompt smoke mismatch above is
  outside #106; full Phase 3 references and regressions are the passing evidence.
- Hosted GitHub Actions was not triggered; local commands and workflow contract
  tests verify the wiring. No database or live-LLM suite was run.
- Upstream Starlette, LangChain, and DoWhy/pandas deprecation warnings remain.
- Conformance is bounded to the supported contracts and fixtures, not proof of
  universal estimator correctness or causal validity. It observes adapter
  fit/predict boundaries, not arbitrary hidden behavior inside third-party code.
- Missing fingerprints from deliberately malformed, validation-bypassed objects
  do not fabricate provenance; normalized refusals survive and provenance gates
  remain blocking if such objects enter a conformance success path.
