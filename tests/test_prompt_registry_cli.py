from __future__ import annotations


def test_prompt_registry_cli_list_outputs_prompt_ids_and_active_versions(capsys) -> None:
    from packages.llm.prompt_registry_cli import main

    main(["list"])

    output = capsys.readouterr().out

    assert "rag.answer" in output
    assert "rag.decision" in output
    assert "rag.summary" in output
    assert "active_version=1" in output


def test_prompt_registry_cli_show_outputs_metadata_without_full_prompt_text_by_default(
    capsys,
) -> None:
    from packages.llm.prompt_registry_cli import main

    main(["show", "rag.answer", "--version", "1"])

    output = capsys.readouterr().out

    assert "prompt_id: rag.answer" in output
    assert "version: 1" in output
    assert "output_contract:" in output
    assert "system_template:" not in output
    assert "user_template:" not in output


def test_prompt_registry_cli_validate_reports_success(capsys) -> None:
    from packages.llm.prompt_registry_cli import main

    main(["validate"])

    output = capsys.readouterr().out

    assert "Prompt registry is valid." in output
