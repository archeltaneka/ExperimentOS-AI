from __future__ import annotations

import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv


def load_environment(dotenv_path: str | Path | None = None) -> bool:
    resolved_path = str(dotenv_path) if dotenv_path is not None else find_dotenv(usecwd=True)
    return load_dotenv(dotenv_path=resolved_path or None, override=True)


def resolve_setting(
    explicit_value: str | None,
    *,
    env_var: str,
    default: str,
    lowercase: bool = False,
) -> str:
    value = explicit_value
    if value is None:
        value = os.environ.get(env_var)
    if value is None:
        load_environment()
        value = os.environ.get(env_var, default)
    resolved = value.strip() if isinstance(value, str) else default
    if not resolved:
        resolved = default
    return resolved.lower() if lowercase else resolved


def get_ollama_base_url() -> str | None:
    load_environment()
    value = os.environ.get("OLLAMA_BASE_URL", "").strip()
    return value or None
