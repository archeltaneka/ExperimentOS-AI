from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

from packages.observability.base import BaseObservabilityProvider, BufferedSpanRecord
from packages.observability.models import ObservabilitySettings
from packages.observability.redaction import redact_payload


class LangSmithObservabilityProvider(BaseObservabilityProvider):
    def __init__(
        self,
        *,
        settings: ObservabilitySettings,
        client: object | None = None,
        run_tree_factory: Callable[..., Any] | None = None,
    ) -> None:
        super().__init__(settings)
        self._client = client
        self._run_tree_factory = run_tree_factory
        if self._client is None or self._run_tree_factory is None:
            self._load_defaults()

    def _load_defaults(self) -> None:
        langsmith_module = importlib.import_module("langsmith")
        run_trees_module = importlib.import_module("langsmith.run_trees")
        if self._client is None:
            client_kwargs: dict[str, object] = {"api_key": self.settings.api_key}
            if self.settings.endpoint:
                client_kwargs["api_url"] = self.settings.endpoint
            self._client = langsmith_module.Client(**client_kwargs)
        if self._run_tree_factory is None:
            self._run_tree_factory = run_trees_module.RunTree

    def _emit_root(self, record: BufferedSpanRecord) -> None:
        self._emit_record(record)

    def _emit_record(self, record: BufferedSpanRecord, parent: object | None = None) -> object:
        payload = {
            "name": record.name,
            "run_type": record.run_type,
            "inputs": _sanitize_inputs(record, self.settings),
            "tags": _merged_tags(record, self.settings),
            "extra": {"metadata": dict(record.metadata)},
        }
        if parent is None:
            payload["client"] = self._client
            payload["project_name"] = self.settings.project
            tree = self._run_tree_factory(**payload)
        else:
            tree = parent.create_child(**payload)
        tree.post()
        for child in record.children:
            self._emit_record(child, tree)
        tree.end(
            outputs=_sanitize_outputs(record, self.settings),
            error=_error_message(record),
        )
        tree.patch()
        return tree


def _sanitize_inputs(
    record: BufferedSpanRecord,
    settings: ObservabilitySettings,
) -> dict[str, object]:
    return dict(redact_payload(record.inputs, settings=settings))


def _sanitize_outputs(
    record: BufferedSpanRecord,
    settings: ObservabilitySettings,
) -> dict[str, object]:
    return dict(redact_payload(record.outputs, settings=settings, is_output=True))


def _merged_tags(
    record: BufferedSpanRecord,
    settings: ObservabilitySettings,
) -> list[str]:
    merged = list(settings.tags)
    for tag in record.tags:
        normalized = str(tag).strip()
        if normalized and normalized not in merged:
            merged.append(normalized)
    return merged


def _error_message(record: BufferedSpanRecord) -> str | None:
    if record.error is None:
        return None
    error_type = str(record.error.get("type", "Error")).strip()
    message = str(record.error.get("message", "")).strip()
    return f"{error_type}: {message}".strip(": ")
