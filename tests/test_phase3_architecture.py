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
                module.startswith(prefix) for module in imports for prefix in _VENDOR_PREFIXES
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
