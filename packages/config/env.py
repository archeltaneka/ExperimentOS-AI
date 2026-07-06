from __future__ import annotations

from pathlib import Path

from dotenv import find_dotenv, load_dotenv


def load_environment(dotenv_path: str | Path | None = None) -> bool:
    resolved_path = str(dotenv_path) if dotenv_path is not None else find_dotenv(usecwd=True)
    return load_dotenv(dotenv_path=resolved_path or None)
