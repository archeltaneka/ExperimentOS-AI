"""Load the strict repository-local Phase 4 statistical reference dataset."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from .models import StatisticalReferenceDataset

DEFAULT_STATISTICAL_DATASET_PATH = Path("data/eval/phase4_statistical_baseline.json")
DEFAULT_OBSERVATIONAL_DATASET_PATH = Path("data/eval/phase4_observational_reliability.json")
_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


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
        dataset = StatisticalReferenceDataset.model_validate(payload)
        default_path = (_REPOSITORY_ROOT / DEFAULT_STATISTICAL_DATASET_PATH).resolve()
        if path.resolve() == default_path:
            companion_path = path.resolve().with_name(DEFAULT_OBSERVATIONAL_DATASET_PATH.name)
            observational = _load_companion(companion_path)
            advanced = _load_companion(path.resolve().with_name("phase4_advanced_conformance.json"))
            if observational.fixture_provenance != dataset.fixture_provenance:
                raise ValueError("observational fixture provenance must match the baseline")
            dataset = dataset.model_copy(
                update={
                    "cases": tuple(
                        sorted(
                            (*dataset.cases, *observational.cases, *advanced.cases),
                            key=lambda case: case.case_id,
                        )
                    )
                }
            )
        return StatisticalReferenceDataset.model_validate(dataset.model_dump(mode="python"))
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


def _load_companion(path: Path) -> StatisticalReferenceDataset:
    if not path.is_file():
        raise ValueError(f"observational reference dataset not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return StatisticalReferenceDataset.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as error:
        raise ValueError(f"observational reference dataset is invalid: {error}") from error


__all__ = [
    "DEFAULT_OBSERVATIONAL_DATASET_PATH",
    "DEFAULT_STATISTICAL_DATASET_PATH",
    "load_statistical_reference_cases",
]
