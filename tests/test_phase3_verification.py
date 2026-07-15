from __future__ import annotations

from pathlib import Path

from packages.evals.phase3_verification.inventory import build_capability_inventory


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
        assert item.generated_reports
        assert item.documentation
        assert item.default_state in {"enabled", "disabled", "conditional"}
        assert item.external_service_requirement in {"none", "optional", "local_postgres"}


def test_inventory_implementation_and_documentation_paths_exist() -> None:
    for item in build_capability_inventory():
        for path in (*item.implementation_locations, *item.documentation):
            assert Path(path).exists(), (item.capability_id, path)
