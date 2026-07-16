# Phase 3 Reliability Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run a deterministic, repository-owned Phase 3 reliability closeout that verifies the complete offline production-oriented system, fixes discovered integration defects, and generates authoritative Markdown and JSON evidence.

**Architecture:** Add a thin typed verification package and `scripts/verify_phase3.py` entry point that orchestrate existing repository CLIs and test suites without reimplementing their business logic. Strict mode is the only closeout path and requires local PostgreSQL plus pgvector; `--offline-only` is a deliberately capped diagnostic path. ExperimentOS models, policy evaluation, traces, and reports remain authoritative, while third-party evaluation and observability systems remain optional adapters or sinks.

**Tech Stack:** Python 3.12, dataclasses, argparse, subprocess, JSON, Markdown, pytest, Ruff, uv, FastAPI, SQLAlchemy, Alembic, PostgreSQL 16, pgvector, GitHub Actions, RAGAS, DeepEval, LangSmith, Phoenix, and OpenTelemetry.

## Global Constraints

- Default verification is strict, complete, deterministic, and database-backed.
- `--offline-only` skips database-dependent checks and can never recommend `ready_to_close`.
- Do not call live OpenAI, Gemini, LangSmith, Phoenix, or OTLP services.
- Fake embeddings, mock LLMs, disabled judges, disabled runtime prompt experiments, and disabled observability exports are mandatory for the verification child environment.
- Preserve `agent_workflow` as the default and preserve `legacy_rag` compatibility.
- Preserve the public `POST /ask` request and response contract.
- Preserve deterministic agents and keep them prompt-free.
- Keep ExperimentOS-owned models, traces, metrics, policies, and reports authoritative.
- Keep RAGAS and DeepEval as adapters, LangSmith and Phoenix as optional sinks, OpenTelemetry as a vendor-neutral export layer, and GitHub Actions as orchestration only.
- Do not lower quality thresholds, suppress failures, add new platforms, or expand Phase 3 scope.
- Required command failures, timeouts, missing or malformed reports, policy failures, factuality invariant failures, and database failures must propagate as non-zero exits.
- Curated reports must use repository-relative paths and must not contain secrets or developer-absolute paths.
- Generated operational artifacts belong under `artifacts/phase3/verification`; curated final reports belong under `reports/phase3`.
- The local PostgreSQL lifecycle remains explicit; the verifier must not start or stop Docker automatically.
- Use `uv` for dependency and command execution, Python 3.12, Ruff line length 100, and the existing bracketed commit style.

---

## File Map

### New files

- `packages/evals/dataset_manifest.py`: stable dataset identifiers, SHA-256 fingerprints, and repository-relative paths.
- `packages/evals/phase3_verification/__init__.py`: public closeout verification exports.
- `packages/evals/phase3_verification/models.py`: typed command, result, inventory, finding, and final-review models.
- `packages/evals/phase3_verification/inventory.py`: one authoritative inventory row per Phase 3 capability.
- `packages/evals/phase3_verification/runner.py`: safe child environment, command execution, stage orchestration, timeout and exit propagation.
- `packages/evals/phase3_verification/validation.py`: report schema, required artifact, policy, factuality, compatibility, and recommendation validation.
- `packages/evals/phase3_verification/reporting.py`: deterministic Markdown and JSON final report rendering.
- `scripts/verify_phase3.py`: strict-by-default command-line entry point and non-closeout `--offline-only` mode.
- `tests/test_phase3_dataset_integrity.py`: category/schema/fingerprint and duplicate integrity coverage.
- `tests/test_phase3_architecture.py`: ownership, prompt-free agent, API, mode, and experiment-surface contracts.
- `tests/test_phase3_verification.py`: focused final-layer unit and CLI behavior tests.
- `tests/conftest.py`: autouse external-network guard that still allows loopback PostgreSQL/tests.
- `docs/phase3/phase3_closeout.md`: objectives, delivered system, guarantees, boundaries, verification, CI, limitations, and Phase 4 direction.
- `reports/phase3/final_reliability_review.md`: freshly generated human-readable closeout evidence.
- `reports/phase3/final_reliability_review.json`: freshly generated machine-readable closeout evidence.

### Modified files

- `packages/evals/dataset.py`: reject unknown QA dataset categories, difficulties, and failure modes.
- `packages/evals/agent_dataset.py`: reject unknown agent categories, intents, agents, decisions, summaries, approvals, and failure modes.
- `packages/evals/evaluator.py`: carry `dataset_id` and `dataset_version` in custom evaluation results.
- `packages/evals/run.py`: fingerprint the selected dataset and pass its identity into the evaluator.
- `packages/evals/agent_evaluator.py`: carry agent dataset identity in the agent evaluation result.
- `packages/evals/run_agent.py`: fingerprint and propagate the selected agent dataset.
- `packages/evals/agent_e2e.py`: expose a stable identity for the code-defined end-to-end case set.
- `packages/evals/run_agent_e2e.py`: fingerprint and propagate the canonical end-to-end cases.
- `packages/evals/ci_quality_gate.py`: enforce the additional fabricated-experiment critical invariant.
- `packages/evals/policy/evaluator.py`: render repository-relative report and source paths.
- `config/evaluation/quality_policy.yaml`: explicitly enforce zero fabricated experiment results.
- `apps/api/main.py`: make missing provider settings select `mock` and `fake`, while retaining explicit `auto` behavior.
- `.env.example`: use safe `mock` and `fake` defaults and explain that live/auto providers are explicit choices.
- `.github/workflows/ci.yml`: pin GitHub actions and preserve all prerequisite failures in the authoritative AI gate.
- `tests/test_api_health.py`: prove missing provider settings remain offline even when API keys exist.
- `tests/test_evaluation_harness.py`: prove dataset identity appears in real evaluation JSON.
- `tests/test_agent_evaluation.py`: prove agent dataset identity appears in reports.
- `tests/test_agent_e2e_evaluation.py`: new coverage proving end-to-end reports identify their case-set version.
- `tests/test_ci_quality_gate.py`: prove all critical factuality thresholds are immutable.
- `tests/test_quality_policy.py`: prove portable paths and optional-metric skip behavior.
- `tests/test_github_actions_ci.py`: prove pinned actions, always-run reporting, prerequisite preservation, and safe PR behavior.
- `tests/test_repository_hygiene.py`: prevent the unused `httpx2` dependency and unsafe example defaults from returning.
- `pyproject.toml`: remove the unused duplicate `httpx2` development dependency.
- `uv.lock`: update only for the justified dependency removal.
- `README.md`: correct Phase 3 command, default, and production-readiness claims.
- `docs/phase3/reliability_baseline.md`: remove the stale statement that CI policy enforcement is absent.
- `docs/phase3/quality_policy.md`: document strict final verification and the expanded invariant set.
- `docs/phase3/github_actions.md`: document the authoritative prerequisite-aware gate and stable required checks.
- `docs/phase3/ci_quality_gate.md`: document failure propagation, artifacts, and strict local parity.
- `docs/phase3/pr_evaluation_reports.md`: state that PR comments are informational and fork-safe.
- `docs/phase3/prompt_registry.md`: confirm deterministic agents remain prompt-free and only `rag.answer` is experimentable.
- `docs/phase3/prompt_experiments.md`: distinguish offline assignment evidence from production causal impact.
- `docs/phase3/observability.md`: align default-disabled export and internal-authority claims.

---

### Task 1: Enforce Dataset Contracts and Emit Stable Dataset Versions

**Files:**
- Create: `packages/evals/dataset_manifest.py`
- Create: `tests/test_phase3_dataset_integrity.py`
- Modify: `packages/evals/dataset.py`
- Modify: `packages/evals/agent_dataset.py`
- Modify: `packages/evals/evaluator.py`
- Modify: `packages/evals/run.py`
- Modify: `packages/evals/agent_evaluator.py`
- Modify: `packages/evals/run_agent.py`
- Modify: `packages/evals/agent_e2e.py`
- Modify: `packages/evals/run_agent_e2e.py`
- Modify: `tests/test_evaluation_harness.py`
- Modify: `tests/test_agent_evaluation.py`
- Create: `tests/test_agent_e2e_evaluation.py`

**Interfaces:**
- Produces: `DatasetManifest(dataset_id: str, version: str, relative_path: str, case_count: int)`.
- Produces: `build_dataset_manifest(path: Path, *, dataset_id: str, case_count: int) -> DatasetManifest`.
- Produces: `build_payload_manifest(payload: bytes, *, dataset_id: str, relative_path: str, case_count: int) -> DatasetManifest`.
- Produces: `EvaluationRun.dataset_id: str` and `EvaluationRun.dataset_version: str`.
- Produces: `AgentEvaluationRun.dataset_id: str` and `AgentEvaluationRun.dataset_version: str`.
- Produces: `AgentE2ERun.dataset_id: str` and `AgentE2ERun.dataset_version: str`.
- Consumes: repository JSON datasets and the existing `asdict`-based report writers.

- [ ] **Step 1: Write failing fingerprint and contract tests**

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.evals.agent_dataset import load_agent_evaluation_dataset
from packages.evals.dataset import load_evaluation_dataset
from packages.evals.dataset_manifest import build_dataset_manifest


def test_dataset_manifest_is_content_addressed_and_repository_relative(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    dataset.write_text('[{"id":"case-1"}]\n', encoding="utf-8")

    manifest = build_dataset_manifest(dataset, dataset_id="qa.golden", case_count=1)

    assert manifest.dataset_id == "qa.golden"
    assert manifest.version.startswith("sha256:")
    assert len(manifest.version) == len("sha256:") + 64
    assert not Path(manifest.relative_path).is_absolute()
    assert manifest.case_count == 1


@pytest.mark.parametrize("field,value", [("category", "invented"), ("difficulty", "impossible")])
def test_qa_dataset_rejects_unknown_enums(tmp_path: Path, field: str, value: str) -> None:
    source = json.loads(Path("data/eval/qa_dataset.json").read_text(encoding="utf-8"))
    source[0][field] = value
    dataset = tmp_path / "qa.json"
    dataset.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(ValueError, match=field):
        load_evaluation_dataset(dataset)


def test_agent_dataset_rejects_unknown_required_agent(tmp_path: Path) -> None:
    source = json.loads(Path("data/eval/agent_dataset.json").read_text(encoding="utf-8"))
    source[0]["expected_required_agents"] = ["vendor_agent"]
    dataset = tmp_path / "agent.json"
    dataset.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(ValueError, match="expected_required_agents"):
        load_agent_evaluation_dataset(dataset)


def test_committed_datasets_preserve_declared_order_and_unique_ids() -> None:
    qa_raw = json.loads(Path("data/eval/qa_dataset.json").read_text(encoding="utf-8"))
    agent_raw = json.loads(Path("data/eval/agent_dataset.json").read_text(encoding="utf-8"))
    qa_ids = [case.id for case in load_evaluation_dataset()]
    agent_ids = [case.id for case in load_agent_evaluation_dataset()]
    assert qa_ids == [row["id"] for row in qa_raw]
    assert agent_ids == [row["id"] for row in agent_raw]
    assert len(qa_ids) == len(set(qa_ids))
    assert len(agent_ids) == len(set(agent_ids))
```

- [ ] **Step 2: Run the tests and verify the missing module and enum validation fail**

Run: `uv run pytest tests/test_phase3_dataset_integrity.py -q`

Expected: FAIL during collection because `packages.evals.dataset_manifest` does not exist.

- [ ] **Step 3: Add the manifest implementation and explicit allowed-value sets**

```python
# packages/evals/dataset_manifest.py
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DatasetManifest:
    dataset_id: str
    version: str
    relative_path: str
    case_count: int


def build_dataset_manifest(
    path: Path,
    *,
    dataset_id: str,
    case_count: int,
) -> DatasetManifest:
    payload = path.read_bytes()
    try:
        relative_path = path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        relative_path = path.name
    return build_payload_manifest(
        payload,
        dataset_id=dataset_id,
        relative_path=relative_path,
        case_count=case_count,
    )


def build_payload_manifest(
    payload: bytes,
    *,
    dataset_id: str,
    relative_path: str,
    case_count: int,
) -> DatasetManifest:
    return DatasetManifest(
        dataset_id=dataset_id,
        version=f"sha256:{hashlib.sha256(payload).hexdigest()}",
        relative_path=relative_path,
        case_count=case_count,
    )
```

In `packages/evals/dataset.py`, define and enforce the exact repository vocabulary after parsing each row:

```python
_VALID_CATEGORIES = {
    "business_impact",
    "factual_retrieval",
    "insufficient_evidence",
    "legacy_rag_fallback",
    "result_interpretation",
    "risk_guardrail",
    "rollout_decision",
}
_VALID_DIFFICULTIES = {"easy", "medium", "hard"}
_VALID_FAILURE_MODES = {None, "unsupported_significance_or_roi"}


def _require_known(value: str | None, *, field: str, allowed: set[str | None], index: int) -> None:
    if value not in allowed:
        rendered = ", ".join(sorted(item for item in allowed if item is not None))
        raise ValueError(
            f"evaluation dataset item {index} field {field!r} must be one of: {rendered}"
        )
```

Define the agent sets exactly as follows, then validate each scalar and every entry in
`expected_required_agents`; do not add permissive wildcard values:

```python
_VALID_CATEGORIES = {
    "approval_workflow",
    "business_impact",
    "insufficient_evidence",
    "lookup",
    "risk_guardrail",
    "rollout_decision",
}
_VALID_INTENTS = {
    "business_impact",
    "decision_support",
    "executive_summary",
    "experiment_lookup",
    "risk_assessment",
}
_VALID_REQUIRED_AGENTS = {
    "business_impact",
    "decision",
    "executive_summary",
    "experiment_analysis",
    "human_approval",
    "retrieval",
    "risk_assessment",
}
_VALID_DECISION_STATUSES = {None, "decided", "needs_more_data"}
_VALID_SUMMARY_STATUSES = {None, "generated", "partial_summary"}
_VALID_FAILURE_MODES = {None, "insufficient_business_evidence"}
```

- [ ] **Step 4: Run dataset integrity tests**

Run: `uv run pytest tests/test_phase3_dataset_integrity.py tests/test_evaluation_harness.py tests/test_agent_evaluation.py -q`

Expected: PASS with all committed datasets accepted and malformed/duplicate/unknown rows rejected.

- [ ] **Step 5: Write failing report-provenance assertions**

Add to the existing CLI/report tests:

```python
payload = json.loads(json_path.read_text(encoding="utf-8"))
assert payload["dataset_id"] == "qa.golden"
assert payload["dataset_version"].startswith("sha256:")
```

For agent evaluation assert `dataset_id == "agent.golden"`. For end-to-end evaluation assert
`dataset_id == "agent_e2e.default"` and `dataset_version` starts with `sha256:`.

- [ ] **Step 6: Run the provenance tests and verify they fail on missing JSON keys**

Run: `uv run pytest tests/test_evaluation_harness.py tests/test_agent_evaluation.py tests/test_agent_e2e_evaluation.py -q`

Expected: FAIL with `KeyError` or missing attribute assertions for dataset identity.

- [ ] **Step 7: Propagate immutable dataset identity through evaluation models**

Add defaulted fields to preserve direct test construction compatibility:

```python
@dataclass(frozen=True)
class EvaluationRun:
    samples: list[EvaluationSampleResult]
    summary: EvaluationSummary
    dataset_id: str = ""
    dataset_version: str = ""
    embedding_provider: str = ""
    embedding_model: str = ""
    llm_provider: str = ""
    llm_model: str = ""
```

Add matching constructor arguments to `OfflineEvaluator`, store them, and include them in
`evaluate()`. Apply the same defaulted-field and constructor pattern to
`AgentEvaluationRun`/`AgentWorkflowEvaluator`. In the QA and agent CLI builders, call
`build_dataset_manifest()` immediately after loading the selected dataset and pass the resulting
identifier/version into the evaluator. Use identifiers `qa.golden`, `agent.golden`, and
`qa.ci_smoke` when the selected path equals the corresponding committed default; use `qa.custom`
or `agent.custom` for any caller-supplied path while retaining its unique content fingerprint and
repository-relative path.

For `AgentE2EEvaluator`, canonicalize `build_default_agent_e2e_cases()` with
`json.dumps([asdict(case) for case in cases], sort_keys=True, separators=(",", ":"))`, pass those
UTF-8 bytes to `build_payload_manifest()` with dataset ID `agent_e2e.default` and relative path
`packages/evals/agent_e2e.py`, and add the manifest ID/version as defaulted `AgentE2ERun` fields.
This records the real code-defined case set without falsely claiming that E2E consumes the QA or
agent JSON datasets.

- [ ] **Step 8: Run evaluation provenance and CI comparison tests**

Run: `uv run pytest tests/test_evaluation_harness.py tests/test_agent_evaluation.py tests/test_agent_e2e_evaluation.py tests/test_ci_reporting.py -q`

Expected: PASS; real evaluation JSON now supplies the dataset version consumed by CI delta reporting.

- [ ] **Step 9: Commit the dataset contract and provenance work**

```powershell
git add packages/evals/dataset_manifest.py packages/evals/dataset.py packages/evals/agent_dataset.py packages/evals/evaluator.py packages/evals/run.py packages/evals/agent_evaluator.py packages/evals/run_agent.py packages/evals/agent_e2e.py packages/evals/run_agent_e2e.py tests/test_phase3_dataset_integrity.py tests/test_evaluation_harness.py tests/test_agent_evaluation.py tests/test_agent_e2e_evaluation.py
git commit -m "[Fix] Enforce Phase 3 dataset provenance"
```

---

### Task 2: Make Offline Providers the Safe Local Default

**Files:**
- Modify: `apps/api/main.py`
- Modify: `.env.example`
- Modify: `tests/test_api_health.py`
- Create: `tests/test_repository_hygiene.py`

**Interfaces:**
- Produces: `get_llm_client()` returns `MockLLMClient` when `LLM_PROVIDER` is absent.
- Produces: `get_embedding_provider_name()` returns `fake` when `EMBEDDING_PROVIDER` is absent.
- Preserves: explicit `LLM_PROVIDER=auto` and `EMBEDDING_PROVIDER=auto` behavior for users who deliberately select it.

- [ ] **Step 1: Write failing provider-safety tests**

```python
def test_missing_provider_settings_ignore_live_api_keys(monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    monkeypatch.setenv("GOOGLE_API_KEY", "must-not-be-used")

    from apps.api.main import get_embedding_provider_name, get_llm_client
    from packages.llm.client import MockLLMClient

    assert isinstance(get_llm_client(), MockLLMClient)
    assert get_embedding_provider_name() == "fake"


def test_env_example_uses_explicit_offline_defaults() -> None:
    example = Path(".env.example").read_text(encoding="utf-8")
    assert "EMBEDDING_PROVIDER=fake" in example
    assert "LLM_PROVIDER=mock" in example
    assert "EMBEDDING_PROVIDER=auto" not in example
    assert "LLM_PROVIDER=auto" not in example
```

- [ ] **Step 2: Run tests and verify current `auto` defaults fail**

Run: `uv run pytest tests/test_api_health.py tests/test_repository_hygiene.py -q`

Expected: FAIL because absent variables currently resolve to `auto` and `.env.example` advertises `auto`.

- [ ] **Step 3: Change only the implicit defaults**

In `get_llm_client()`, replace only
`os.environ.get("LLM_PROVIDER", "auto")` with
`os.environ.get("LLM_PROVIDER", "mock")`. In `get_embedding_provider_name()`, replace only
`os.environ.get("EMBEDDING_PROVIDER", "auto")` with
`os.environ.get("EMBEDDING_PROVIDER", "fake")`. Leave every explicit provider branch unchanged.

Set `.env.example` to:

```dotenv
EMBEDDING_PROVIDER=fake
LLM_PROVIDER=mock
```

Add adjacent comments that `auto` and live provider names are explicit opt-in choices and that observability exports, prompt experiments, and judge metrics remain disabled unless explicitly enabled.

- [ ] **Step 4: Run provider configuration coverage**

Run: `uv run pytest tests/test_api_health.py tests/test_env_config.py tests/test_repository_hygiene.py -q`

Expected: PASS, including existing tests that prove explicit `auto`, Gemini, OpenAI, Ollama, and Hugging Face selection still works.

- [ ] **Step 5: Commit the safe-default correction**

```powershell
git add apps/api/main.py .env.example tests/test_api_health.py tests/test_repository_hygiene.py
git commit -m "[Fix] Make offline providers the safe default"
```

---

### Task 3: Strengthen Factuality Invariants and Portable Policy Evidence

**Files:**
- Modify: `config/evaluation/quality_policy.yaml`
- Modify: `packages/evals/ci_quality_gate.py`
- Modify: `packages/evals/policy/evaluator.py`
- Modify: `tests/test_ci_quality_gate.py`
- Modify: `tests/test_quality_policy.py`

**Interfaces:**
- Produces: critical required policy metric `factuality.findings.fabricated_experiment_result <= 0`.
- Produces: `repository_relative_path(path: Path | str, *, root: Path | None = None) -> str`.
- Preserves: existing zero-tolerance revenue/ROI, statistical-significance, structured-decision, approval, citation, and abstention controls.

- [ ] **Step 1: Write failing invariant and portability tests**

```python
def test_policy_invariants_require_zero_fabricated_experiment_results() -> None:
    policy = load_quality_policy(Path("config/evaluation/quality_policy.yaml"))
    metric = next(
        item
        for item in policy.metrics
        if item.metric_id == "factuality.findings.fabricated_experiment_result"
    )
    assert metric.operator == "lte"
    assert metric.value == 0
    assert metric.severity == "critical"
    assert metric.required is True


def test_quality_policy_result_paths_are_repository_relative(tmp_path: Path) -> None:
    _write_base_reports(tmp_path)
    policy_path = _write_policy(tmp_path / "policy.yaml", _base_policy_yaml())
    result = PolicyEvaluator(
        policy=load_quality_policy(policy_path),
        report_dir=tmp_path,
    ).evaluate()
    assert not Path(result.report_dir).is_absolute()
    assert all(not Path(metric.source_path).is_absolute() for metric in result.metrics_evaluated)
```

Also extend the invariant mutation test so deleting, weakening, or changing the severity of `fabricated_experiment_result` raises `ValueError`.

- [ ] **Step 2: Run policy tests and verify the missing invariant and absolute paths fail**

Run: `uv run pytest tests/test_ci_quality_gate.py tests/test_quality_policy.py -q`

Expected: FAIL because the policy lacks the explicit metric and `PolicyEvaluator` serializes absolute temporary paths.

- [ ] **Step 3: Add the critical threshold and centralize portable path rendering**

Add to `config/evaluation/quality_policy.yaml` using the existing factuality source/category conventions:

```yaml
  - metric_id: factuality.findings.fabricated_experiment_result
    source: factuality
    category: Factuality
    operator: lte
    value: 0
    severity: critical
    required: true
    weight: 1.5
    description: Fabricated experiment result claims are never allowed.
```

Add the same tuple to `required_invariants` in `validate_policy_invariants()`.

Implement in `packages/evals/policy/evaluator.py`:

```python
def repository_relative_path(path: Path | str, *, root: Path | None = None) -> str:
    candidate = Path(path)
    base = (root or Path.cwd()).resolve()
    try:
        return candidate.resolve().relative_to(base).as_posix()
    except ValueError:
        return candidate.name
```

Use this function for `PolicyEvaluationResult.report_dir` and every `EvaluatedMetric.source_path`. Do not change metric comparison or missing-optional semantics.

- [ ] **Step 4: Run factuality and policy regression coverage**

Run: `uv run pytest tests/test_factuality.py tests/test_quality_policy.py tests/test_ci_quality_gate.py -q`

Expected: PASS, including detector false-positive, finding-diagnostic, report-table, severity, structured-decision, approval, and abstention tests.

- [ ] **Step 5: Commit the invariant and portable-report correction**

```powershell
git add config/evaluation/quality_policy.yaml packages/evals/ci_quality_gate.py packages/evals/policy/evaluator.py tests/test_ci_quality_gate.py tests/test_quality_policy.py
git commit -m "[Fix] Strengthen factuality closeout invariants"
```

---

### Task 4: Make the Authoritative CI Gate Preserve Prerequisite Failures

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/test_github_actions_ci.py`

**Interfaces:**
- Produces: `ai-quality-gate` always generates available reports but exits non-zero if any required prerequisite job failed or was cancelled.
- Preserves: quality-policy business rules in Python, artifact uploads under `if: always()`, informational PR comments, fork-safe permissions, and no `pull_request_target`.

- [ ] **Step 1: Write failing workflow-security and propagation assertions**

```python
def test_actions_are_pinned_to_full_commit_shas() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    for line in workflow.splitlines():
        stripped = line.strip()
        if stripped.startswith("uses: actions/"):
            reference = stripped.rsplit("@", 1)[1].split()[0]
            assert len(reference) == 40
            assert all(character in "0123456789abcdef" for character in reference)


def test_authoritative_gate_preserves_prerequisite_failures() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "prerequisite_exit_code" in workflow
    for job in ("format", "lint", "validate", "unit-tests", "offline-eval-smoke", "integration-db"):
        assert f"needs.{job}.result" in workflow
    assert "if: always()" in workflow
```

- [ ] **Step 2: Run the workflow tests and verify unpinned actions and missing propagation fail**

Run: `uv run pytest tests/test_github_actions_ci.py -q`

Expected: FAIL on version tags such as `actions/checkout@v7` and the absent prerequisite exit-code handling.

- [ ] **Step 3: Pin the existing action versions to reviewed commits**

Use these resolved commits while retaining a version comment:

```yaml
uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7
uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1 # v6
uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7
uses: actions/download-artifact@634f93cb2916e3fdff6788551b99b062d0335ce0 # v5
```

Leave the already-pinned `astral-sh/setup-uv` reference unchanged.

- [ ] **Step 4: Record prerequisite status without embedding quality thresholds in YAML**

Add an always-run step before the quality-gate execution:

```yaml
- name: Record prerequisite status
  id: prerequisites
  if: always()
  env:
    FORMAT_RESULT: ${{ needs.format.result }}
    LINT_RESULT: ${{ needs.lint.result }}
    VALIDATE_RESULT: ${{ needs.validate.result }}
    UNIT_RESULT: ${{ needs.unit-tests.result }}
    OFFLINE_EVAL_RESULT: ${{ needs.offline-eval-smoke.result }}
    INTEGRATION_RESULT: ${{ needs.integration-db.result }}
  shell: bash
  run: |
    prerequisite_exit_code=0
    for result in "$FORMAT_RESULT" "$LINT_RESULT" "$VALIDATE_RESULT" "$UNIT_RESULT" "$OFFLINE_EVAL_RESULT" "$INTEGRATION_RESULT"; do
      if [[ "$result" != "success" ]]; then
        prerequisite_exit_code=2
      fi
    done
    echo "prerequisite_exit_code=$prerequisite_exit_code" >> "$GITHUB_OUTPUT"
```

In the existing final exit-restoration step, preserve the current quality-gate and report-builder exit codes first, then exit with `${{ steps.prerequisites.outputs.prerequisite_exit_code }}`. This keeps report generation best-effort while preventing any upstream failure from appearing green.

- [ ] **Step 5: Run workflow tests**

Run: `uv run pytest tests/test_github_actions_ci.py tests/test_ci_quality_gate.py tests/test_ci_reporting.py -q`

Expected: PASS; YAML contains orchestration/status wiring only and repository Python remains the policy authority.

- [ ] **Step 6: Commit the CI reliability and pinning fix**

```powershell
git add .github/workflows/ci.yml tests/test_github_actions_ci.py
git commit -m "[Fix] Preserve CI prerequisite failures"
```

---

### Task 5: Define the Typed Final Verification Contract and Inventory

**Files:**
- Create: `packages/evals/phase3_verification/__init__.py`
- Create: `packages/evals/phase3_verification/models.py`
- Create: `packages/evals/phase3_verification/inventory.py`
- Create: `tests/test_phase3_architecture.py`
- Create: `tests/test_phase3_verification.py`

**Interfaces:**
- Produces: `VerificationMode = Literal["strict", "offline_only"]`.
- Produces: `VerificationCommand`, `CommandResult`, `CapabilityInventoryItem`, `ReviewFinding`, and `FinalReliabilityReview` frozen dataclasses.
- Produces: `build_capability_inventory() -> tuple[CapabilityInventoryItem, ...]`.
- Consumes later: runner, validators, and report renderers.

- [ ] **Step 1: Write failing model and inventory tests**

```python
def test_capability_inventory_covers_every_phase3_domain() -> None:
    inventory = build_capability_inventory()
    capability_ids = {item.capability_id for item in inventory}
    assert {
        "evaluation.custom_rag",
        "evaluation.custom_agent",
        "evaluation.end_to_end",
        "evaluation.ragas",
        "evaluation.deepeval",
        "evaluation.prompt_regression",
        "evaluation.factuality",
        "evaluation.quality_policy",
        "prompt.registry",
        "prompt.provenance",
        "prompt.experiments",
        "observability.internal",
        "observability.langsmith",
        "observability.phoenix",
        "observability.opentelemetry",
        "observability.composite",
        "ci.baseline",
        "ci.database",
        "ci.quality_gate",
        "ci.pr_reporting",
    } <= capability_ids


def test_inventory_rows_have_all_required_closeout_fields() -> None:
    for item in build_capability_inventory():
        assert item.implementation_locations
        assert item.configuration
        assert item.cli_commands
        assert item.tests
        assert item.documentation
        assert item.default_state in {"enabled", "disabled", "conditional"}
        assert item.external_service_requirement in {"none", "optional", "local_postgres"}
```

Create `tests/test_phase3_architecture.py` with these exact compatibility and ownership contracts:

```python
from __future__ import annotations

import ast
from pathlib import Path

from apps.api.ask_service import AskRequest, AskResponse, get_ask_mode
from packages.evals.prompt_experiments.validation import get_experimentable_prompt_ids

_BUSINESS_ROOTS = (
    Path("apps/api"),
    Path("packages/agents"),
    Path("packages/qa"),
    Path("packages/retrieval"),
)
_VENDOR_PREFIXES = ("ragas", "deepeval", "langsmith", "phoenix", "opentelemetry")


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_business_services_do_not_import_third_party_evaluation_or_sinks() -> None:
    for root in _BUSINESS_ROOTS:
        for path in root.glob("*.py"):
            imports = _imported_modules(path)
            assert not any(
                module.startswith(prefix)
                for module in imports
                for prefix in _VENDOR_PREFIXES
            ), path


def test_deterministic_agents_remain_prompt_and_llm_free() -> None:
    for path in Path("packages/agents").glob("*.py"):
        imports = _imported_modules(path)
        assert not any(module.startswith("packages.llm") for module in imports), path
        assert not any("prompt" in module for module in imports), path


def test_public_ask_contract_and_default_mode_are_stable(monkeypatch) -> None:
    monkeypatch.delenv("ASK_MODE", raising=False)
    assert tuple(AskRequest.model_fields) == ("question", "experiment_id", "top_k")
    assert tuple(AskResponse.model_fields) == (
        "answer",
        "citations",
        "retrieved_chunks",
        "retrieval_metrics",
        "llm_metrics",
        "prompt_metadata",
        "intent",
        "required_agents",
        "decision",
        "executive_summary",
        "agent_trace",
        "agent_metrics",
        "approval_status",
    )
    assert get_ask_mode() == "agent_workflow"


def test_only_rag_answer_is_experimentable() -> None:
    assert get_experimentable_prompt_ids() == frozenset({"rag.answer"})
```

- [ ] **Step 2: Run the focused test and verify imports fail**

Run: `uv run pytest tests/test_phase3_architecture.py tests/test_phase3_verification.py -q`

Expected: FAIL because the verification package does not exist.

- [ ] **Step 3: Add the exact immutable verification models**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

VerificationMode = Literal["strict", "offline_only"]
CommandStatus = Literal["pass", "fail", "skipped", "timeout"]
MilestoneRecommendation = Literal[
    "ready_to_close",
    "ready_with_documented_limitations",
    "not_ready",
]


@dataclass(frozen=True)
class VerificationCommand:
    command_id: str
    argv: tuple[str, ...]
    required: bool
    timeout_seconds: int
    report_paths: tuple[str, ...] = ()
    strict_only: bool = False


@dataclass(frozen=True)
class CommandResult:
    command_id: str
    argv: tuple[str, ...]
    status: CommandStatus
    exit_code: int | None
    duration_seconds: float
    stdout_tail: str
    stderr_tail: str
    report_paths: tuple[str, ...]


@dataclass(frozen=True)
class CapabilityInventoryItem:
    capability_id: str
    name: str
    implementation_locations: tuple[str, ...]
    configuration: tuple[str, ...]
    cli_commands: tuple[str, ...]
    tests: tuple[str, ...]
    generated_reports: tuple[str, ...]
    documentation: tuple[str, ...]
    optional_dependencies: tuple[str, ...]
    default_state: Literal["enabled", "disabled", "conditional"]
    external_service_requirement: Literal["none", "optional", "local_postgres"]
    known_limitations: tuple[str, ...]


@dataclass(frozen=True)
class ReviewFinding:
    finding_id: str
    area: str
    severity: Literal["info", "warning", "critical"]
    status: Literal["fixed", "open", "accepted"]
    summary: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class FinalReliabilityReview:
    schema_version: str
    generated_at_utc: str
    mode: VerificationMode
    closeout_eligible: bool
    recommendation: MilestoneRecommendation
    overall_status: Literal["pass", "fail"]
    commands: tuple[CommandResult, ...]
    capability_inventory: tuple[CapabilityInventoryItem, ...]
    findings: tuple[ReviewFinding, ...]
    dataset_versions: dict[str, str]
    policy_version: str
    provider_configuration: dict[str, str]
    factuality_invariants: dict[str, int]
    compatibility: dict[str, str]
    limitations: tuple[str, ...]
    unresolved_risks: tuple[str, ...]
    section_summaries: dict[str, str] = field(default_factory=dict)
```

- [ ] **Step 4: Populate the inventory with explicit repository evidence**

Create one row for every capability in the current Phase 3 list. Each row must cite real paths, actual CLI syntax, actual report filenames, actual optional groups, default state, external requirement, and a precise limitation. Group no unrelated capabilities into a generic row; RAGAS, DeepEval, LangSmith, Phoenix, OpenTelemetry, quality policy, PR reports, and database integration each require their own row.

- [ ] **Step 5: Run inventory tests and static checks**

Run: `uv run pytest tests/test_phase3_architecture.py tests/test_phase3_verification.py -q`

Expected: PASS for model construction and complete inventory fields.

Run: `uv run ruff check packages/evals/phase3_verification tests/test_phase3_verification.py`

Expected: `All checks passed!`

- [ ] **Step 6: Commit the verification contract and inventory**

```powershell
git add packages/evals/phase3_verification tests/test_phase3_architecture.py tests/test_phase3_verification.py
git commit -m "[New Feature] Add Phase 3 verification contract"
```

---

### Task 6: Implement Safe Command Execution and Strict/Diagnostic Stage Plans

**Files:**
- Create: `packages/evals/phase3_verification/runner.py`
- Create: `tests/conftest.py`
- Modify: `packages/evals/phase3_verification/__init__.py`
- Modify: `tests/test_phase3_verification.py`

**Interfaces:**
- Produces: `build_verification_environment(source: Mapping[str, str]) -> dict[str, str]`.
- Produces: `discover_synthetic_fixtures(root: Path, expected_ids: Collection[str]) -> tuple[Path, ...]`.
- Produces: `build_verification_commands(mode: VerificationMode, *, artifact_root: Path) -> tuple[VerificationCommand, ...]`.
- Produces: `run_command(command: VerificationCommand, *, env: Mapping[str, str], cwd: Path) -> CommandResult`.
- Produces: `run_verification_commands(...) -> tuple[CommandResult, ...]`.
- Consumes: `scripts/run_ai_quality_gate.py` for strict evaluation orchestration and existing CLIs for validation/dry runs.

- [ ] **Step 1: Write failing safe-environment and exit-propagation tests**

```python
def test_verification_environment_disables_all_external_paths() -> None:
    env = build_verification_environment(
        {
            "PATH": os.environ["PATH"],
            "OPENAI_API_KEY": "secret",
            "GEMINI_API_KEY": "secret",
            "LANGCHAIN_API_KEY": "secret",
            "EXPERIMENTOS_PHOENIX_API_KEY": "secret",
            "EXPERIMENTOS_OTEL_EXPORTER_ENDPOINT": "https://collector.example",
        }
    )
    assert env["EMBEDDING_PROVIDER"] == "fake"
    assert env["LLM_PROVIDER"] == "mock"
    assert env["RAGAS_JUDGE_LLM_PROVIDER"] == "none"
    assert env["RAGAS_JUDGE_EMBEDDING_PROVIDER"] == "none"
    assert env["DEEPEVAL_JUDGE_PROVIDER"] == "none"
    assert env["EXPERIMENTOS_LANGSMITH_ENABLED"] == "false"
    assert env["EXPERIMENTOS_PHOENIX_ENABLED"] == "false"
    assert env["EXPERIMENTOS_OTEL_ENABLED"] == "false"
    assert env["PROMPT_EXPERIMENTS_ENABLED"] == "false"
    assert env["PYTHONHASHSEED"] == "0"
    assert env["OPENAI_API_KEY"] == ""
    assert env["EXPERIMENTOS_OTEL_EXPORTER_ENDPOINT"] == ""


def test_run_command_preserves_child_exit_code(tmp_path: Path) -> None:
    command = VerificationCommand(
        command_id="intentional-failure",
        argv=(sys.executable, "-c", "raise SystemExit(7)"),
        required=True,
        timeout_seconds=5,
    )
    result = run_command(command, env=os.environ, cwd=tmp_path)
    assert result.status == "fail"
    assert result.exit_code == 7


def test_offline_only_plan_contains_no_database_or_closeout_gate(tmp_path: Path) -> None:
    commands = build_verification_commands("offline_only", artifact_root=tmp_path)
    assert all(not command.strict_only for command in commands)
    assert all("alembic" not in command.argv for command in commands)
    assert all("run_ai_quality_gate.py" not in command.argv for command in commands)


def test_fixture_discovery_requires_every_qa_experiment(tmp_path: Path) -> None:
    (tmp_path / "exp-001-payment-recommendation").mkdir()
    with pytest.raises(ValueError, match="exp-002-hotel-image-quality"):
        discover_synthetic_fixtures(
            tmp_path,
            {"exp-001-payment-recommendation", "exp-002-hotel-image-quality"},
        )


def test_test_suite_blocks_external_network() -> None:
    with socket.socket() as connection:
        with pytest.raises(RuntimeError, match="external network disabled"):
            connection.connect(("example.com", 443))
```

- [ ] **Step 2: Run focused runner tests and verify functions are absent**

Run: `uv run pytest tests/test_phase3_verification.py -q`

Expected: FAIL with import errors for runner functions.

- [ ] **Step 3: Implement the hardened child environment**

Copy the source environment, preserve `PATH`, `SYSTEMROOT`, `TEMP`, `TMP`, `DATABASE_URL`, and Python/uv process variables, then overwrite every provider/export/experiment variable with these exact values:

```python
_SAFE_ENVIRONMENT = {
    "ASK_MODE": "agent_workflow",
    "EMBEDDING_PROVIDER": "fake",
    "LLM_PROVIDER": "mock",
    "RAGAS_JUDGE_LLM_PROVIDER": "none",
    "RAGAS_JUDGE_EMBEDDING_PROVIDER": "none",
    "DEEPEVAL_JUDGE_PROVIDER": "none",
    "EXPERIMENTOS_LANGSMITH_ENABLED": "false",
    "LANGSMITH_TRACING": "false",
    "EXPERIMENTOS_PHOENIX_ENABLED": "false",
    "EXPERIMENTOS_OTEL_ENABLED": "false",
    "EXPERIMENTOS_OTEL_EXPORTER_TYPE": "none",
    "PROMPT_EXPERIMENTS_ENABLED": "false",
    "OPENAI_API_KEY": "",
    "GEMINI_API_KEY": "",
    "LANGCHAIN_API_KEY": "",
    "LANGSMITH_API_KEY": "",
    "EXPERIMENTOS_PHOENIX_API_KEY": "",
    "LANGSMITH_ENDPOINT": "",
    "EXPERIMENTOS_PHOENIX_ENDPOINT": "",
    "EXPERIMENTOS_OTEL_EXPORTER_ENDPOINT": "",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "",
    "PYTHONHASHSEED": "0",
}
```

Before overwriting, reject explicitly configured live provider/export settings with a message naming the conflicting variable. Empty values and the exact safe values above are allowed. This catches unsafe caller configuration instead of silently concealing it.

- [ ] **Step 4: Implement subprocess execution without a shell**

Use `subprocess.run(list(command.argv), cwd=cwd, env=dict(env), text=True, capture_output=True, timeout=command.timeout_seconds, check=False)`. Record `time.monotonic()` duration, cap each output tail to 8,000 characters, map exit 0 to `pass`, non-zero to `fail`, and `TimeoutExpired` to `timeout` with no exit code. Never interpolate user values into a shell command.

- [ ] **Step 5: Define exact strict and diagnostic stage plans**

The strict plan must contain, in order:

1. `uv lock --check`.
2. `uv run ruff format --check .` and `uv run ruff check .`.
3. prompt registry validation.
4. prompt experiment validation.
5. `packages.observability.cli status --provider all`, `validate --provider all`, and
   `dry-run --provider langsmith|phoenix|opentelemetry`, plus the existing NoOp and in-memory
   exporter tests.
6. focused configuration/dataset/prompt/observability/API/CI/factuality/verification tests.
7. `uv run alembic upgrade head`.
8. validate that `data/synthetic/experiments` contains exactly the experiment IDs referenced by
   the QA dataset, then ingest all ten deterministic synthetic fixture directories with
   `--embedding-provider fake` in stable path order, twice.
9. focused database migration/ingestion/retrieval/API/workflow tests.
10. `uv run python scripts/run_ai_quality_gate.py --artifact-root
    <artifact_root>/quality_gate --dataset data/eval/qa_dataset.json --agent-dataset
    data/eval/agent_dataset.json`.
11. `packages.evals.run_ci_report build` with `--strict --format all`, followed by `render
    --format pr-comment` and `validate`, writing under `<artifact_root>/ci`.
12. final report validation.

Construct the CI report commands with these exact argument sequences:

```python
(
    "uv", "run", "python", "-m", "packages.evals.run_ci_report", "build",
    "--report-dir", str(artifact_root / "quality_gate"),
    "--quality-policy-report",
    str(artifact_root / "quality_gate/phase3/quality_policy.json"),
    "--output", str(artifact_root / "ci/pr_quality_report.json"),
    "--format", "all", "--strict",
)
(
    "uv", "run", "python", "-m", "packages.evals.run_ci_report", "render",
    "--input", str(artifact_root / "ci/pr_quality_report.json"),
    "--format", "pr-comment",
    "--output", str(artifact_root / "ci/pr_comment.md"),
)
(
    "uv", "run", "python", "-m", "packages.evals.run_ci_report", "validate",
    "--input", str(artifact_root / "ci/pr_quality_report.json"),
)
```

The focused non-database pytest command is:

```python
(
    "uv", "run", "pytest", "-q",
    "tests/test_phase3_dataset_integrity.py",
    "tests/test_phase3_architecture.py",
    "tests/test_env_config.py",
    "tests/test_api_health.py",
    "tests/test_api_ask.py",
    "tests/test_agent_workflow.py",
    "tests/test_evaluation_harness.py",
    "tests/test_agent_evaluation.py",
    "tests/test_agent_e2e_evaluation.py",
    "tests/test_ragas_evaluation.py",
    "tests/test_deepeval_evaluation.py",
    "tests/test_prompt_registry.py",
    "tests/test_prompt_registry_cli.py",
    "tests/test_prompt_regression.py",
    "tests/test_prompt_experiment_validation.py",
    "tests/test_prompt_experiment_runner.py",
    "tests/test_prompt_experiment_cli.py",
    "tests/test_factuality.py",
    "tests/test_quality_policy.py",
    "tests/test_observability_config.py",
    "tests/test_observability_cli.py",
    "tests/test_observability_langsmith.py",
    "tests/test_observability_phoenix.py",
    "tests/test_observability_opentelemetry.py",
    "tests/test_observability_composite.py",
    "tests/test_observability_redaction.py",
    "tests/test_observability_integration.py",
    "tests/test_ci_quality_gate.py",
    "tests/test_ci_reporting.py",
    "tests/test_github_actions_ci.py",
    "tests/test_repository_hygiene.py",
    "tests/test_phase3_verification.py",
)
```

The strict-only database pytest command is:

```python
(
    "uv", "run", "pytest", "-q",
    "tests/test_alembic_config.py",
    "tests/test_db_models.py",
    "tests/test_ingestion_load_experiment.py",
    "tests/test_retrieval_service.py",
    "tests/test_retrieval_agent.py",
    "tests/test_api_ask_db_integration.py",
)
```

The diagnostic plan must contain stages 1 through 6 plus offline-safe factuality,
prompt-regression, prompt-experiment, and report-schema checks that require neither PostgreSQL nor
external services. Mark every skipped database/evaluation stage explicitly in the final review;
do not substitute fake passes.

- [ ] **Step 6: Add a loopback-only autouse network guard and run timeout coverage**

Create `tests/conftest.py` with an autouse fixture that patches `socket.socket.connect`. Allow Unix
socket paths and tuple hosts `127.0.0.1`, `::1`, and `localhost`; raise
`RuntimeError("external network disabled during tests: <host>")` before DNS resolution for every
other host. This lets database and local in-memory/server tests operate while making accidental
OpenAI, Gemini, LangSmith, Phoenix, OTLP, and package-service calls fail visibly. Add a timeout test
using a Python child that waits longer than a 1-second timeout.

```python
from __future__ import annotations

import socket
from collections.abc import Generator

import pytest

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


@pytest.fixture(autouse=True)
def prevent_external_network(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    original_connect = socket.socket.connect
    original_getaddrinfo = socket.getaddrinfo

    def guarded_connect(connection: socket.socket, address: object) -> object:
        if isinstance(address, str):
            return original_connect(connection, address)
        if isinstance(address, tuple) and address:
            host = str(address[0]).lower()
            if host in _LOOPBACK_HOSTS:
                return original_connect(connection, address)
            raise RuntimeError(f"external network disabled during tests: {host}")
        return original_connect(connection, address)

    def guarded_getaddrinfo(host: str | bytes | None, *args: object, **kwargs: object) -> object:
        normalized = host.decode() if isinstance(host, bytes) else host
        if normalized is not None and normalized.lower() not in _LOOPBACK_HOSTS:
            raise RuntimeError(f"external network disabled during tests: {normalized}")
        return original_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    yield
```

Run: `uv run pytest tests/test_phase3_verification.py -q`

Expected: PASS for success, child failure, timeout, strict/offline command selection, environment conflict, and no-network behavior.

- [ ] **Step 7: Commit the safe runner**

```powershell
git add packages/evals/phase3_verification/runner.py packages/evals/phase3_verification/__init__.py tests/conftest.py tests/test_phase3_verification.py
git commit -m "[New Feature] Add strict Phase 3 verification runner"
```

---

### Task 7: Validate Required Reports and Derive the Milestone Recommendation

**Files:**
- Create: `packages/evals/phase3_verification/validation.py`
- Modify: `packages/evals/phase3_verification/__init__.py`
- Modify: `tests/test_phase3_verification.py`

**Interfaces:**
- Produces: `load_json_object(path: Path) -> dict[str, object]`.
- Produces: `validate_required_reports(report_root: Path) -> dict[str, dict[str, object]]`.
- Produces: `validate_final_review_files(json_path: Path, markdown_path: Path) -> None`.
- Produces: `extract_factuality_invariants(payload: Mapping[str, object]) -> dict[str, int]`.
- Produces: `derive_recommendation(*, mode, command_results, policy_payload, factuality_invariants, unresolved_critical_findings) -> MilestoneRecommendation`.
- Consumes: existing evaluation, factuality, experiment, and policy JSON schemas.

- [ ] **Step 1: Write failing missing, malformed, policy, factuality, and optional-skip tests**

```python
def _passing_result() -> CommandResult:
    return CommandResult(
        command_id="passing",
        argv=("python", "-V"),
        status="pass",
        exit_code=0,
        duration_seconds=0.1,
        stdout_tail="",
        stderr_tail="",
        report_paths=(),
    )


def _zero_factuality_invariants() -> dict[str, int]:
    return {
        "fabricated_revenue_or_roi": 0,
        "fabricated_statistical_significance": 0,
        "fabricated_experiment_result": 0,
        "structured_decision_contradiction": 0,
        "approval_state_contradiction": 0,
    }


def test_required_report_validation_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(VerificationError, match="missing required report"):
        validate_required_reports(tmp_path)


def test_required_report_validation_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "evaluation.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(VerificationError, match="valid JSON"):
        load_json_object(path)


def test_policy_failure_forces_not_ready() -> None:
    recommendation = derive_recommendation(
        mode="strict",
        command_results=(_passing_result(),),
        policy_payload={"overall_status": "fail"},
        factuality_invariants=_zero_factuality_invariants(),
        unresolved_critical_findings=0,
    )
    assert recommendation == "not_ready"


def test_factuality_violation_forces_not_ready() -> None:
    invariants = _zero_factuality_invariants()
    invariants["fabricated_revenue_or_roi"] = 1
    assert derive_recommendation(
        mode="strict",
        command_results=(_passing_result(),),
        policy_payload={"overall_status": "pass"},
        factuality_invariants=invariants,
        unresolved_critical_findings=0,
    ) == "not_ready"


def test_optional_metric_skip_does_not_block_strict_closeout() -> None:
    assert derive_recommendation(
        mode="strict",
        command_results=(_passing_result(),),
        policy_payload={"overall_status": "pass", "skipped_metrics": [{"required": False}]},
        factuality_invariants=_zero_factuality_invariants(),
        unresolved_critical_findings=0,
    ) == "ready_to_close"


def test_offline_only_is_never_ready_to_close() -> None:
    assert derive_recommendation(
        mode="offline_only",
        command_results=(_passing_result(),),
        policy_payload={"overall_status": "pass"},
        factuality_invariants=_zero_factuality_invariants(),
        unresolved_critical_findings=0,
    ) == "ready_with_documented_limitations"
```

- [ ] **Step 2: Run validation tests and verify imports fail**

Run: `uv run pytest tests/test_phase3_verification.py -q`

Expected: FAIL because validation functions are not implemented.

- [ ] **Step 3: Implement explicit required-report schemas**

Require these strict-mode files below the configured artifact root:

```python
_REQUIRED_QUALITY_GATE_REPORT_KEYS = {
    "quality_gate/evaluation.json": ("samples", "summary", "dataset_version"),
    "quality_gate/agent_evaluation.json": ("samples", "summary", "dataset_version"),
    "quality_gate/agent_e2e_evaluation.json": (
        "samples",
        "summary",
        "dataset_id",
        "dataset_version",
    ),
    "quality_gate/phase3/ragas_report.json": ("metric_results", "case_results"),
    "quality_gate/phase3/deepeval_report.json": ("metric_results", "case_results"),
    "quality_gate/phase3/prompt_regression.json": ("summary", "case_results"),
    "quality_gate/phase3/factuality_report.json": (
        "case_results",
        "findings_by_category",
        "findings_detail",
        "policy_result",
    ),
    "quality_gate/phase3/quality_policy.json": ("policy_version", "overall_status"),
    "quality_gate/phase3/prompt_experiments/rag-answer-abstention-v1-v2.json": (
        "experiment_id",
        "dataset_id",
        "recommendation",
        "production_traffic_involved",
    ),
    "quality_gate/phase3/ai_quality_gate.json": ("status", "manifest", "command_results"),
    "ci/pr_quality_report.json": ("overall_status", "suites", "execution"),
}
_REQUIRED_MARKDOWN_REPORTS = (
    "quality_gate/evaluation.md",
    "quality_gate/agent_evaluation.md",
    "quality_gate/agent_e2e_evaluation.md",
    "quality_gate/phase3/ragas_report.md",
    "quality_gate/phase3/deepeval_report.md",
    "quality_gate/phase3/prompt_regression.md",
    "quality_gate/phase3/factuality_report.md",
    "quality_gate/phase3/quality_policy.md",
    "quality_gate/phase3/prompt_experiments/rag-answer-abstention-v1-v2.md",
    "quality_gate/phase3/github_summary.md",
    "ci/pr_quality_report.md",
    "ci/pr_comment.md",
)
```

These keys match the existing authoritative report models and committed sample reports. Treat a
present report with the wrong shape exactly like a failed required command.

Also require prompt experiment `production_traffic_involved` to be `false`, reject recommendations
that claim automatic promotion, and require its limitations to state that offline evidence does not
establish production causal impact.

Do not validate by accepting any JSON object. Define a mapping from relative report path to required top-level key tuple and report all missing keys in one `VerificationError` message.

- [ ] **Step 4: Implement factuality extraction and recommendation precedence**

Extract integer counts for:

```python
_CRITICAL_FACTUALITY_KEYS = (
    "fabricated_revenue_or_roi",
    "fabricated_statistical_significance",
    "fabricated_experiment_result",
    "structured_decision_contradiction",
    "approval_state_contradiction",
)
```

Before treating absent finding categories as zero, require the factuality report's
`checks_executed` to contain `numerical_grounding`, `financial_guardrails`,
`statistical_validation`, `abstention_correctness`, and `structured_consistency`, and require
`policy_result.status == "pass"`. A missing critical detector or skipped deterministic check is a
validation failure, not a zero finding count.

The last two counts come from finding-level details/structured field identifiers when the current report groups them under `contradiction_with_structured_experiment_data`. Recommendation precedence is:

1. any required command failure/timeout, missing/malformed report, policy `fail`, positive critical factuality count, or open critical finding => `not_ready`;
2. otherwise `offline_only` => `ready_with_documented_limitations`;
3. otherwise strict mode with accepted warning limitations => `ready_with_documented_limitations`;
4. otherwise => `ready_to_close`.

Optional metrics with `required: false` and status `skipped` are recorded but do not count as failures.

Add `main(argv: Sequence[str] | None = None) -> int` and an `if __name__ == "__main__"`
guard to `validation.py`. Its two positional arguments are the final JSON and Markdown paths;
it calls `validate_final_review_files`, prints `Phase 3 final reports are valid.`, and returns 2 with
a concise error when either report is missing, malformed, inconsistent, absolute-path-bearing, or
secret-bearing.

- [ ] **Step 5: Run all final-layer validation tests**

Run: `uv run pytest tests/test_phase3_verification.py -q`

Expected: PASS for missing report, malformed report, policy failure, each factuality invariant, optional metric skip, and offline recommendation cap.

- [ ] **Step 6: Commit report validation and recommendation logic**

```powershell
git add packages/evals/phase3_verification/validation.py packages/evals/phase3_verification/__init__.py tests/test_phase3_verification.py
git commit -m "[New Feature] Validate Phase 3 closeout evidence"
```

---

### Task 8: Render Authoritative Final Markdown and JSON Reports

**Files:**
- Create: `packages/evals/phase3_verification/reporting.py`
- Modify: `packages/evals/phase3_verification/__init__.py`
- Modify: `tests/test_phase3_verification.py`

**Interfaces:**
- Produces: `final_review_to_dict(review: FinalReliabilityReview) -> dict[str, object]`.
- Produces: `render_final_review_markdown(review: FinalReliabilityReview) -> str`.
- Produces: `write_final_review(review, *, markdown_path: Path, json_path: Path) -> None`.
- Consumes: typed inventory, command results, findings, compatibility status, policy/factuality evidence, and limitations.

- [ ] **Step 1: Write failing deterministic report-generation tests**

```python
def _sample_final_review(
    *,
    mode: VerificationMode = "strict",
    recommendation: MilestoneRecommendation = "ready_to_close",
    overall_status: Literal["pass", "fail"] = "pass",
) -> FinalReliabilityReview:
    return FinalReliabilityReview(
        schema_version="phase3-final-review-v1",
        generated_at_utc="2026-07-15T00:00:00Z",
        mode=mode,
        closeout_eligible=mode == "strict",
        recommendation=recommendation,
        overall_status=overall_status,
        commands=(_passing_result(),),
        capability_inventory=build_capability_inventory(),
        findings=(),
        dataset_versions={"qa.golden": "sha256:" + "a" * 64},
        policy_version="phase3-v1",
        provider_configuration={"embedding": "fake", "llm": "mock", "judges": "none"},
        factuality_invariants=_zero_factuality_invariants(),
        compatibility={
            "ask_mode_default": "agent_workflow",
            "legacy_rag": "pass",
            "post_ask_contract": "pass",
            "deterministic_agents": "pass",
        },
        limitations=("External sinks were verified with dry-runs and in-memory exporters.",),
        unresolved_risks=(),
        section_summaries={"architecture": "Ownership boundaries verified."},
    )


def test_final_report_generation_writes_markdown_and_json(tmp_path: Path) -> None:
    review = _sample_final_review(mode="strict")
    markdown_path = tmp_path / "final.md"
    json_path = tmp_path / "final.json"

    write_final_review(review, markdown_path=markdown_path, json_path=json_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert payload["recommendation"] == "ready_to_close"
    assert payload["capability_inventory"]
    for heading in (
        "Capability Inventory",
        "Architecture Review",
        "Commands Run",
        "Test Results",
        "Database Verification",
        "Evaluation Results",
        "Factuality Invariants",
        "Quality Policy",
        "Observability",
        "CI and PR Reporting",
        "API Compatibility",
        "Security and Privacy",
        "Known Limitations",
        "Unresolved Risks",
        "Milestone Recommendation",
    ):
        assert f"## {heading}" in markdown
    assert str(tmp_path.resolve()) not in markdown
```

- [ ] **Step 2: Run the report test and verify missing renderer imports fail**

Run: `uv run pytest tests/test_phase3_verification.py -q`

Expected: FAIL because report rendering functions do not exist.

- [ ] **Step 3: Implement deterministic JSON serialization**

Use `dataclasses.asdict(review)`, preserve tuple order, sort only map keys at JSON serialization, write UTF-8 with a trailing newline, and never include raw environment values or full child output. `stdout_tail` and `stderr_tail` are evidence fields already capped by the runner and must pass through a secret-redaction helper before serialization.

- [ ] **Step 4: Implement the complete Markdown structure**

Render the inventory as a table containing implementation, configuration, command, tests, reports, docs, optional dependencies, defaults, external requirements, and limitations. Render every command with status, exit code, duration, and expected report paths. Render all 18 user-requested handoff domains either as a dedicated heading or as a clearly labeled subsection; do not claim production deployment or production scale.

End with exactly one of:

```markdown
## Milestone Recommendation

`ready_to_close`
```

```markdown
## Milestone Recommendation

`ready_with_documented_limitations`
```

```markdown
## Milestone Recommendation

`not_ready`
```

- [ ] **Step 5: Run report generation, redaction, and determinism tests**

Add assertions that API keys, bearer tokens, full prompts, and retrieved chunk payloads supplied in a synthetic child-output tail become `[REDACTED]`. Generate twice from the same input and assert byte-identical output after fixing `generated_at_utc` in the fixture.

Run: `uv run pytest tests/test_phase3_verification.py -q`

Expected: PASS for summary generation, final report generation, redaction, required headings, and stable JSON.

- [ ] **Step 6: Commit final report rendering**

```powershell
git add packages/evals/phase3_verification/reporting.py packages/evals/phase3_verification/__init__.py tests/test_phase3_verification.py
git commit -m "[New Feature] Generate Phase 3 reliability reports"
```

---

### Task 9: Add the Strict-by-Default Verification CLI

**Files:**
- Create: `scripts/verify_phase3.py`
- Modify: `packages/evals/phase3_verification/runner.py`
- Modify: `tests/test_phase3_verification.py`

**Interfaces:**
- Produces: CLI `uv run python scripts/verify_phase3.py`.
- Produces: diagnostic CLI `uv run python scripts/verify_phase3.py --offline-only`.
- Produces: `main(argv: Sequence[str] | None = None) -> int` for direct tests.
- Writes: operational artifacts under `artifacts/phase3/verification` and curated reports under `reports/phase3`.

- [ ] **Step 1: Write failing CLI mode and summary tests**

```python
def test_cli_defaults_to_strict(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_run(*, mode, artifact_root, report_root, repository_root):
        captured["mode"] = mode
        return _sample_final_review(mode="strict")

    monkeypatch.setattr(verify_phase3, "run_phase3_verification", fake_run)
    exit_code = verify_phase3.main(
        ["--artifact-root", str(tmp_path / "artifacts"), "--report-root", str(tmp_path)]
    )
    assert exit_code == 0
    assert captured["mode"] == "strict"


def test_cli_offline_only_prints_non_closeout_label(monkeypatch, capsys, tmp_path: Path) -> None:
    monkeypatch.setattr(
        verify_phase3,
        "run_phase3_verification",
        lambda **kwargs: _sample_final_review(
            mode="offline_only",
            recommendation="ready_with_documented_limitations",
        ),
    )
    assert verify_phase3.main(["--offline-only", "--report-root", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "NON-CLOSEOUT DIAGNOSTIC" in output
    assert "ready_to_close" not in output


def test_cli_returns_nonzero_when_required_stage_fails(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        verify_phase3,
        "run_phase3_verification",
        lambda **kwargs: _sample_final_review(
            recommendation="not_ready",
            overall_status="fail",
        ),
    )
    assert verify_phase3.main(["--report-root", str(tmp_path)]) != 0
```

- [ ] **Step 2: Run CLI tests and verify the script import fails**

Run: `uv run pytest tests/test_phase3_verification.py -q`

Expected: FAIL because `scripts.verify_phase3` does not exist.

- [ ] **Step 3: Implement argparse with strict default and explicit diagnostic flag**

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the deterministic Phase 3 end-to-end reliability closeout."
    )
    parser.add_argument(
        "--offline-only",
        action="store_true",
        help=(
            "Run a non-closeout diagnostic that skips PostgreSQL-dependent checks; "
            "this mode can never recommend ready_to_close."
        ),
    )
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("artifacts/phase3/verification"),
    )
    parser.add_argument("--report-root", type=Path, default=Path("reports/phase3"))
    return parser
```

Strict startup must mark configuration failure before executing database/evaluation stages if
`DATABASE_URL` is absent. The error must print the repository's Docker Compose and PowerShell setup
commands and must not start Docker itself. It must still write `not_ready` Markdown and JSON final
reports containing that configuration evidence.

- [ ] **Step 4: Wire orchestration, report generation, and exit semantics**

Implement `run_phase3_verification()` in the runner: validate source configuration, build the hardened environment, execute all stages while continuing when safe to collect evidence, validate produced reports, derive the recommendation, write both final reports, and return `FinalReliabilityReview`. Return CLI exit 0 only when no required stage failed and recommendation is not `not_ready`. An offline diagnostic may return 0 with `ready_with_documented_limitations`, but its console banner and report must state it is not closeout evidence.

- [ ] **Step 5: Run final-layer tests**

Run: `uv run pytest tests/test_phase3_verification.py -q`

Expected: PASS for strict default, diagnostic cap, missing database setting, exit propagation, missing/malformed reports, policy/factuality failures, no-network enforcement, and report generation.

- [ ] **Step 6: Check real help output and diagnostic execution**

Run: `uv run python scripts/verify_phase3.py --help`

Expected: exit 0; help explicitly says default mode is strict and `--offline-only` is non-closeout.

Run: `uv run python scripts/verify_phase3.py --offline-only`

Expected: exit 0 only if all diagnostic checks pass; console and JSON report set `closeout_eligible` to false and recommendation no higher than `ready_with_documented_limitations`.

- [ ] **Step 7: Commit the final verification entry point**

```powershell
git add scripts/verify_phase3.py packages/evals/phase3_verification/runner.py tests/test_phase3_verification.py
git commit -m "[New Feature] Add Phase 3 closeout command"
```

---

### Task 10: Remove the Confirmed Duplicate Dependency

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `tests/test_repository_hygiene.py`

**Interfaces:**
- Removes: unused development-only `httpx2` distribution.
- Preserves: normal `httpx` dependency and every existing optional Phase 3 group/version constraint.

- [ ] **Step 1: Add a failing dependency-hygiene assertion**

```python
def test_duplicate_httpx2_dependency_is_absent() -> None:
    project = Path("pyproject.toml").read_text(encoding="utf-8")
    assert '"httpx2' not in project
```

- [ ] **Step 2: Run the test and verify the existing dev dependency fails it**

Run: `uv run pytest tests/test_repository_hygiene.py -q`

Expected: FAIL because `pyproject.toml` contains `httpx2>=2.0.0`.

- [ ] **Step 3: Remove only `httpx2` and regenerate the lockfile**

Delete the single `httpx2>=2.0.0` entry from the development dependency group.

Run: `uv lock`

Expected: exit 0; lockfile changes remove `httpx2` and its now-unreferenced transitive packages only.

- [ ] **Step 4: Validate dependency consistency and optional imports**

Run: `uv lock --check`

Expected: exit 0.

Run: `uv tree --all-groups --depth 2`

Expected: exit 0; output contains `httpx` but no `httpx2`, and existing RAGAS, DeepEval, LangSmith, Phoenix, and OpenTelemetry constraints resolve.

Run: `uv run pytest tests/test_package_imports.py tests/test_observability_config.py tests/test_ragas_evaluation.py tests/test_deepeval_evaluation.py tests/test_repository_hygiene.py -q`

Expected: PASS; missing optional dependencies still fail only when their adapters are enabled.

- [ ] **Step 5: Commit the dependency cleanup**

```powershell
git add pyproject.toml uv.lock tests/test_repository_hygiene.py
git commit -m "[Fix] Remove unused duplicate HTTP dependency"
```

---

### Task 11: Correct Phase 3 Documentation and Create the Closeout Document

**Files:**
- Create: `docs/phase3/phase3_closeout.md`
- Modify: `README.md`
- Modify: `docs/phase3/reliability_baseline.md`
- Modify: `docs/phase3/quality_policy.md`
- Modify: `docs/phase3/github_actions.md`
- Modify: `docs/phase3/ci_quality_gate.md`
- Modify: `docs/phase3/pr_evaluation_reports.md`
- Modify: `docs/phase3/prompt_registry.md`
- Modify: `docs/phase3/prompt_experiments.md`
- Modify: `docs/phase3/observability.md`
- Modify: `tests/test_repository_hygiene.py`

**Interfaces:**
- Produces: reproducible strict setup/verification instructions and honest production-readiness boundaries.
- Produces: stable required-check guidance for `format`, `lint`, tests/database integration, and `ai-quality-gate`.
- Preserves: PR comments as informational and not merge-authoritative.

- [ ] **Step 1: Write failing documentation contract assertions**

```python
def test_phase3_closeout_docs_describe_strict_and_diagnostic_modes() -> None:
    closeout = Path("docs/phase3/phase3_closeout.md").read_text(encoding="utf-8")
    assert "uv run python scripts/verify_phase3.py" in closeout
    assert "--offline-only" in closeout
    assert "non-closeout diagnostic" in closeout.lower()
    assert "production-oriented portfolio system" in closeout
    assert "not proof of production deployment at scale" in closeout


def test_baseline_no_longer_claims_ci_enforcement_is_missing() -> None:
    baseline = Path("docs/phase3/reliability_baseline.md").read_text(encoding="utf-8")
    assert "CI enforcement is not implemented" not in baseline


def test_branch_protection_docs_keep_pr_reporting_informational() -> None:
    docs = Path("docs/phase3/github_actions.md").read_text(encoding="utf-8")
    assert "AI quality gate" in docs
    assert "PR reporting" in docs
    assert "not required" in docs
```

- [ ] **Step 2: Run documentation tests and verify the missing/stale content fails**

Run: `uv run pytest tests/test_repository_hygiene.py -q`

Expected: FAIL because the closeout document does not exist and the reliability baseline contains a stale CI claim.

- [ ] **Step 3: Write the closeout document with exact required sections**

Create `docs/phase3/phase3_closeout.md` with these headings and concrete repository evidence:

```markdown
# Phase 3 Closeout

## Original Objectives
## Delivered Capabilities
## Architectural Decisions
## Quality Guarantees
## Local Strict Verification
## Offline-Only Diagnostic
## CI Behavior and Required Checks
## Production Readiness Boundaries
## Known Limitations
## Deferred Work
## Recommended Phase 4 Direction
```

In `Delivered Capabilities`, map the reviewed Phase 3 issue sequence #53 through #67 to the
corresponding implementation, tests, reports, and documentation. Identify issue #68 as this
cross-capability reliability review, without stating that the GitHub issue is closed.

The strict setup block must include `docker compose up -d postgres`, the port-5433 `DATABASE_URL`,
`uv run python scripts/generate_synthetic_experiments.py` when the ignored deterministic corpus is
absent, `uv run alembic upgrade head`, and `uv run python scripts/verify_phase3.py`. Warn that the
generator deletes and recreates `data/synthetic/experiments`, so it must not be run over local data
the user wants to preserve. State that external judges and sinks are optional, internal reports
remain authoritative, no prompt is automatically promoted, A/B results are offline evidence only,
deterministic agents remain prompt-free, `rag.answer` is the only experimentable surface, and
public API/default/fallback behavior is preserved.

- [ ] **Step 4: Correct all command/default/CI documentation drift**

Update every listed document against the actual `--help` output and workflow. Remove the baseline statement that enforcement is absent. Document safe mock/fake defaults, strict policy exit behavior, always-uploaded artifacts, prerequisite failure preservation, informational/fork-safe comments, stable required checks, disabled exports, in-memory/dry-run observability, and the production-oriented-not-production-scale boundary. Avoid copying threshold numbers into workflow documentation when the policy YAML is the authority; link to the policy path instead.

Record that clean migration verifies extension creation against the repository's pgvector image.
Testing a server where the extension package is physically absent is not performed because it would
require a second non-project database image; the Alembic failure remains explicit and is a documented
local setup boundary rather than a passing claim.

- [ ] **Step 5: Verify every documented Phase 3 command's help output**

Run each exact command from the docs with `--help`:

```powershell
uv run python -m packages.evals.run --help
uv run python -m packages.evals.run_agent --help
uv run python -m packages.evals.run_agent_e2e --help
uv run python -m packages.evals.run_ragas --help
uv run python -m packages.evals.run_deepeval --help
uv run python -m packages.evals.run_prompt_regression --help
uv run python -m packages.evals.run_factuality --help
uv run python -m packages.evals.run_quality_policy --help
uv run python -m packages.evals.run_prompt_experiment --help
uv run python -m packages.llm.prompt_registry_cli --help
uv run python -m packages.observability.cli --help
uv run python -m packages.evals.run_ci_report --help
uv run python scripts/verify_phase3.py --help
```

Expected: every command exits 0 and its real options match the documentation.

- [ ] **Step 6: Run documentation contracts and lint**

Run: `uv run pytest tests/test_repository_hygiene.py tests/test_github_actions_ci.py -q`

Expected: PASS.

Run: `uv run ruff check .`

Expected: `All checks passed!`

- [ ] **Step 7: Commit closeout documentation**

```powershell
git add README.md docs/phase3 tests/test_repository_hygiene.py
git commit -m "[Improvement] Document Phase 3 reliability closeout"
```

---

### Task 12: Run Clean Database, API, Evaluation, Observability, and Strict Closeout Verification

**Files:**
- Generate: `reports/phase3/final_reliability_review.md`
- Generate: `reports/phase3/final_reliability_review.json`
- Update only if evidence requires: scoped implementation/tests/docs from Tasks 1-11

**Interfaces:**
- Consumes: the complete verification entry point and a local PostgreSQL 16 plus pgvector service.
- Produces: fresh strict closeout evidence and a final recommendation derived from actual results.

- [ ] **Step 1: Inspect the worktree before generating evidence**

Run: `git status --short`

Expected: only intentional Task 1-11 changes and generated artifacts are present; do not alter unrelated user files.

- [ ] **Step 2: Start and inspect the repository database service**

Run: `docker compose up -d postgres`

Expected: exit 0.

Run: `docker compose ps postgres`

Expected: the Postgres 16/pgvector service is healthy and exposes host port 5433.

- [ ] **Step 3: Create an isolated empty verification database and migrate it to head**

```powershell
docker compose exec -T postgres psql -U experimentos -d postgres -c "DROP DATABASE IF EXISTS experimentos_phase3_verify WITH (FORCE);"
docker compose exec -T postgres psql -U experimentos -d postgres -c "CREATE DATABASE experimentos_phase3_verify;"
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos_phase3_verify"
$env:ASK_MODE = "agent_workflow"
$env:EMBEDDING_PROVIDER = "fake"
$env:LLM_PROVIDER = "mock"
$env:RAGAS_JUDGE_LLM_PROVIDER = "none"
$env:RAGAS_JUDGE_EMBEDDING_PROVIDER = "none"
$env:DEEPEVAL_JUDGE_PROVIDER = "none"
$env:EXPERIMENTOS_LANGSMITH_ENABLED = "false"
$env:EXPERIMENTOS_PHOENIX_ENABLED = "false"
$env:EXPERIMENTOS_OTEL_ENABLED = "false"
$env:PROMPT_EXPERIMENTS_ENABLED = "false"
uv run alembic upgrade head
```

Expected: both database commands and Alembic exit 0 with a newly empty, dedicated database at
head and pgvector available. Never drop or recreate the default `experimentos` database or a
caller-provided database.

- [ ] **Step 4: Run formatting, linting, and the full relevant test suite with visible progress**

Run: `uv run ruff format --check .`

Expected: exit 0.

Run: `uv run ruff check .`

Expected: `All checks passed!`

Run: `uv run pytest -vv --durations=25`

Expected: all required tests pass; database tests execute rather than skip. If the suite stalls, rerun the last visible test alone under `superpowers:systematic-debugging` and fix only the root cause.

- [ ] **Step 5: Run focused clean-database ingestion, retrieval, API, and workflow verification**

Run the repository's migration tests, deterministic fixture ingestion twice, retrieval tests, `POST /ask` integration tests for both modes, approval/error/insufficient-evidence cases, and agent workflow tests using the exact focused commands emitted by `build_verification_commands("strict", ...)`.

Expected: repeated ingestion is idempotent, fake deterministic vectors retrieve fixtures, `agent_workflow` is the default, `legacy_rag` remains functional, public response fields do not expose experiment context or third-party IDs, and database cleanup leaves no developer-state dependency.

- [ ] **Step 6: Run observability verification without network exports**

Run the NoOp, LangSmith dry-run, Phoenix dry-run, OpenTelemetry in-memory trace/metric, composite-provider, redaction, sampling, correlation, failure-isolation, and trace-coverage tests selected by the strict command.

Expected: one internal logical hierarchy and one OpenTelemetry initialization authority; no duplicate graph spans, full prompts/chunks, hidden reasoning, network calls, or provider-coupled public fields.

- [ ] **Step 7: Run the strict closeout command**

Run: `uv run python scripts/verify_phase3.py`

Expected: exit 0 only if configuration, prompts, datasets, focused tests, database checks, all offline evaluations, factuality invariants, quality policy, observability, compatibility, CI validation, and report validation pass. The console summary prints command exit codes, durations, skipped optional metrics, policy version, dataset versions, provider configuration, and final recommendation.

- [ ] **Step 8: Independently validate the generated final reports**

Run: `uv run python -m packages.evals.phase3_verification.validation reports/phase3/final_reliability_review.json reports/phase3/final_reliability_review.md`

Expected: exit 0; both reports are well formed, repository-relative, secret-free, and mutually consistent.

- [ ] **Step 9: Inspect the evidence before accepting its recommendation**

Run: `Get-Content reports/phase3/final_reliability_review.md`

Expected: all required sections are populated from fresh command evidence. Accept `ready_to_close` only when every strict required check passed and no critical unresolved finding remains. Otherwise preserve the derived `ready_with_documented_limitations` or `not_ready` result and document the exact evidence.

- [ ] **Step 10: Commit the fresh final reports**

```powershell
git add reports/phase3/final_reliability_review.md reports/phase3/final_reliability_review.json
git commit -m "[Improvement] Record Phase 3 reliability evidence"
```

---

### Task 13: Final Review, GitHub Publication, and Issue Traceability

**Files:**
- Review: every changed file from Tasks 1-12
- No new implementation files unless verification exposes a scoped defect

**Interfaces:**
- Consumes: fresh strict evidence, committed implementation, and issue-linked branch `feature/issue-68-phase3-reliability-review`.
- Produces: review-ready Git history and GitHub branch evidence linked to issue #68.

- [ ] **Step 1: Run the verification-before-completion checklist**

Invoke `superpowers:verification-before-completion`, then rerun its required fresh commands. Do not use prior command output as completion evidence.

- [ ] **Step 2: Review the complete diff for scope, secrets, paths, and compatibility**

Run: `git diff main...HEAD --check`

Expected: no whitespace errors.

Run: `git diff main...HEAD --stat`

Expected: only Phase 3 reliability implementation, tests, configuration, CI, dependency, documentation, and reports.

Run: `rg -n "OPENAI_API_KEY=.+|GEMINI_API_KEY=.+|LANGSMITH_API_KEY=.+|EXPERIMENTOS_PHOENIX_API_KEY=.+|C:\\\\Users\\\\|pull_request_target|shell=True" . --glob '!uv.lock' --glob '!.git/**'`

Expected: no committed secret values, developer-absolute paths, unsafe workflow trigger, or shell subprocess execution.

- [ ] **Step 3: Confirm the branch remains linked to issue #68**

Run: `gh issue develop --list 68`

Expected: output includes `feature/issue-68-phase3-reliability-review`.

- [ ] **Step 4: Push the reviewed branch**

Run: `git push --set-upstream origin feature/issue-68-phase3-reliability-review`

Expected: exit 0 and the remote branch updates with all reviewed commits.

- [ ] **Step 5: Request code review before merge or issue closure**

Invoke `superpowers:requesting-code-review` against the final diff. Address only concrete review findings with the test-first workflow, rerun strict verification after any code/config/report change, and regenerate final evidence if outputs change.

- [ ] **Step 6: Prepare the final 18-part handoff**

The final response must print, in this order:

1. files changed;
2. Phase 3 capability inventory;
3. architectural inconsistencies found;
4. defects fixed;
5. configuration and security findings;
6. commands run;
7. test results;
8. database verification results;
9. evaluation results;
10. factuality invariant results;
11. quality-policy result;
12. observability verification;
13. CI and PR-reporting verification;
14. API compatibility status;
15. documentation changes;
16. remaining limitations;
17. final milestone recommendation;
18. recommended Phase 4 direction.

Every success claim must cite the fresh strict report or command output. Do not close issue #68 automatically unless the user separately authorizes issue closure after reviewing the evidence.
