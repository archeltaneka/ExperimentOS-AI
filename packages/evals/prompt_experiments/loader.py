from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packages.evals.prompt_experiments.models import PromptExperimentDefinition

DEFAULT_PROMPT_EXPERIMENT_CONFIG_DIR = Path("config/prompt_experiments")


def load_prompt_experiment_definition(
    experiment_id: str,
    *,
    config_dir: Path | None = None,
) -> PromptExperimentDefinition:
    base_dir = config_dir or DEFAULT_PROMPT_EXPERIMENT_CONFIG_DIR
    for path in _definition_paths(base_dir):
        payload = _load_mapping(path)
        if str(payload.get("experiment_id", "")).strip() != experiment_id:
            continue
        return PromptExperimentDefinition(
            experiment_id=str(payload["experiment_id"]).strip(),
            name=str(payload["name"]).strip(),
            description=str(payload["description"]).strip(),
            prompt_id=str(payload["prompt_id"]).strip(),
            control_version=str(payload["control_version"]).strip(),
            treatment_versions=tuple(str(value).strip() for value in payload["treatment_versions"]),
            hypothesis=str(payload["hypothesis"]).strip(),
            primary_metric=str(payload["primary_metric"]).strip(),
            secondary_metrics=tuple(
                str(value).strip() for value in payload.get("secondary_metrics", [])
            ),
            guardrail_metrics=tuple(
                str(value).strip() for value in payload.get("guardrail_metrics", [])
            ),
            dataset_id=str(payload["dataset_id"]).strip(),
            assignment_strategy=str(payload["assignment_strategy"]).strip(),
            allocation={
                str(key).strip(): float(value) for key, value in dict(payload["allocation"]).items()
            },
            randomization_unit=str(payload["randomization_unit"]).strip(),
            seed=str(payload["seed"]).strip(),
            status=str(payload["status"]).strip(),
            allow_deprecated_versions=bool(payload.get("allow_deprecated_versions", False)),
            metadata=dict(payload.get("metadata", {})),
        )
    raise ValueError(f"unknown prompt experiment definition: {experiment_id}")


def _definition_paths(config_dir: Path) -> tuple[Path, ...]:
    if not config_dir.exists():
        return ()
    return tuple(
        sorted(
            path
            for path in config_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".json", ".yaml", ".yml"}
        )
    )


def _load_mapping(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"unable to read prompt experiment definition: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"prompt experiment definition is not valid JSON/YAML: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"prompt experiment definition must be an object: {path}")
    return payload
