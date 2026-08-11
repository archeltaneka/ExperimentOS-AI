"""Load the strict repository-local Phase 4 statistical reference dataset."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from .models import StatisticalReferenceDataset

DEFAULT_STATISTICAL_DATASET_PATH = Path("data/eval/phase4_statistical_baseline.json")


def load_statistical_reference_cases(path: Path) -> StatisticalReferenceDataset:
    """Parse one deterministic dataset and reject malformed or duplicate cases."""
    if not path.is_file():
        raise ValueError(f"statistical reference dataset not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(
            f"statistical reference dataset contains invalid JSON: {error.msg}"
        ) from error
    try:
        return StatisticalReferenceDataset.model_validate(payload)
    except ValidationError as error:
        duplicate = next(
            (
                item["msg"].removeprefix("Value error, ")
                for item in error.errors(include_url=False, include_input=False)
                if "duplicate statistical case_id:" in item["msg"]
            ),
            None,
        )
        if duplicate is not None:
            raise ValueError(duplicate) from error
        raise ValueError(f"statistical reference dataset is invalid: {error}") from error


__all__ = ["DEFAULT_STATISTICAL_DATASET_PATH", "load_statistical_reference_cases"]
