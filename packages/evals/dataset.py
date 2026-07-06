from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_DATASET_PATH = Path(__file__).with_name("datasets") / "harness_v1.json"


@dataclass(frozen=True)
class EvaluationQuestion:
    id: str
    experiment_id: str
    question: str
    expected_documents: tuple[str, ...]
    expected_keywords: tuple[str, ...]
    category: str
    difficulty: str
    reference_answer: str


def load_evaluation_dataset(path: Path = DEFAULT_DATASET_PATH) -> list[EvaluationQuestion]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"unable to read evaluation dataset: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"evaluation dataset is not valid JSON: {path}") from exc

    if not isinstance(raw, list):
        raise ValueError("evaluation dataset must be a JSON list")

    questions = [_question_from_mapping(item, index=index) for index, item in enumerate(raw)]
    question_ids = [question.id for question in questions]
    if len(question_ids) != len(set(question_ids)):
        raise ValueError("evaluation dataset contains duplicate question ids")
    return questions


def _question_from_mapping(item: Any, *, index: int) -> EvaluationQuestion:
    if not isinstance(item, dict):
        raise ValueError(f"evaluation dataset item {index} must be an object")

    required = {
        "id",
        "experiment_id",
        "question",
        "expected_documents",
        "expected_keywords",
        "category",
        "difficulty",
        "reference_answer",
    }
    missing = sorted(required - set(item))
    if missing:
        raise ValueError(f"evaluation dataset item {index} is missing: {', '.join(missing)}")

    return EvaluationQuestion(
        id=_required_string(item, "id", index=index),
        experiment_id=_required_string(item, "experiment_id", index=index),
        question=_required_string(item, "question", index=index),
        expected_documents=_required_string_tuple(item, "expected_documents", index=index),
        expected_keywords=_required_string_tuple(item, "expected_keywords", index=index),
        category=_required_string(item, "category", index=index),
        difficulty=_required_string(item, "difficulty", index=index),
        reference_answer=_required_string(item, "reference_answer", index=index),
    )


def _required_string(item: dict[str, Any], key: str, *, index: int) -> str:
    value = item[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"evaluation dataset item {index} field {key!r} must be a string")
    return value.strip()


def _required_string_tuple(item: dict[str, Any], key: str, *, index: int) -> tuple[str, ...]:
    value = item[key]
    if not isinstance(value, list) or not value:
        raise ValueError(f"evaluation dataset item {index} field {key!r} must be a non-empty list")
    strings: list[str] = []
    for offset, entry in enumerate(value):
        if not isinstance(entry, str) or not entry.strip():
            raise ValueError(
                f"evaluation dataset item {index} field {key!r} entry {offset} "
                "must be a string"
            )
        strings.append(entry.strip())
    return tuple(strings)
