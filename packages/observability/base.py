from __future__ import annotations

import hashlib
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime

from packages.observability.models import ObservabilitySettings, ProviderSettings

_CURRENT_SPAN: ContextVar[BufferedSpan | None] = ContextVar(
    "observability_current_span",
    default=None,
)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class BufferedSpanRecord:
    name: str
    run_type: str
    trace_id: str | None = None
    parent: BufferedSpanRecord | None = None
    inputs: dict[str, object] = field(default_factory=dict)
    outputs: dict[str, object] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    error: dict[str, object] | None = None
    status: str = "pending"
    started_at: str = field(default_factory=_utc_now_iso)
    ended_at: str | None = None
    children: list[BufferedSpanRecord] = field(default_factory=list)


class BufferedSpan:
    def __init__(self, provider: BaseObservabilityProvider, record: BufferedSpanRecord) -> None:
        self.provider = provider
        self.record = record

    @contextmanager
    def activate(self):
        token = _CURRENT_SPAN.set(self)
        try:
            yield self
        finally:
            _CURRENT_SPAN.reset(token)

    def start_child(
        self,
        name: str,
        *,
        run_type: str = "chain",
        inputs: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
        tags: tuple[str, ...] | list[str] = (),
    ) -> BufferedSpan:
        return self.provider.start_span(
            name,
            run_type=run_type,
            inputs=inputs,
            metadata=metadata,
            tags=tags,
            parent=self,
        )

    def add_metadata(self, metadata: dict[str, object]) -> None:
        self.record.metadata.update(metadata)

    def add_tags(self, tags: tuple[str, ...] | list[str]) -> None:
        for tag in tags:
            normalized = str(tag).strip()
            if normalized and normalized not in self.record.tags:
                self.record.tags.append(normalized)

    def record_output(self, output: dict[str, object] | None) -> None:
        if output:
            self.record.outputs.update(output)

    def record_error(
        self,
        error: BaseException | str,
        *,
        details: dict[str, object] | None = None,
    ) -> None:
        message = str(error)
        error_type = error.__class__.__name__ if isinstance(error, BaseException) else "Error"
        self.record.error = {
            "type": error_type,
            "message": message,
            **(details or {}),
        }
        self.record.status = "error"

    def finish(
        self,
        *,
        outputs: dict[str, object] | None = None,
    ) -> None:
        if outputs:
            self.record.outputs.update(outputs)
        if self.record.status == "pending":
            self.record.status = "completed"
        self.record.ended_at = _utc_now_iso()
        if self.record.parent is None:
            self.provider._finish_root(self.record)


class BaseObservabilityProvider:
    def __init__(self, settings: ObservabilitySettings | ProviderSettings) -> None:
        self.settings = settings
        self._failure_count = 0

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def increment_failure(self) -> None:
        self._failure_count += 1

    def current_span(self) -> BufferedSpan | None:
        return _CURRENT_SPAN.get()

    def start_root_span(
        self,
        name: str,
        *,
        trace_id: str | None = None,
        run_type: str = "chain",
        inputs: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
        tags: tuple[str, ...] | list[str] = (),
    ) -> BufferedSpan:
        record = BufferedSpanRecord(
            name=name,
            run_type=run_type,
            trace_id=trace_id,
            inputs=dict(inputs or {}),
            metadata=dict(metadata or {}),
            tags=list(tags),
        )
        if trace_id and "experimentos_trace_id" not in record.metadata:
            record.metadata["experimentos_trace_id"] = trace_id
        return BufferedSpan(self, record)

    def start_span(
        self,
        name: str,
        *,
        run_type: str = "chain",
        inputs: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
        tags: tuple[str, ...] | list[str] = (),
        parent: BufferedSpan | None = None,
    ) -> BufferedSpan:
        resolved_parent = parent or self.current_span()
        parent_record = resolved_parent.record if resolved_parent is not None else None
        trace_id = parent_record.trace_id if parent_record is not None else None
        record = BufferedSpanRecord(
            name=name,
            run_type=run_type,
            trace_id=trace_id,
            parent=parent_record,
            inputs=dict(inputs or {}),
            metadata=dict(metadata or {}),
            tags=list(tags),
        )
        if parent_record is not None:
            parent_record.children.append(record)
        return BufferedSpan(self, record)

    def build_langgraph_config(
        self,
        *,
        metadata: dict[str, object] | None = None,
        tags: tuple[str, ...] | list[str] = (),
    ) -> dict[str, object] | None:
        if not self.settings.enabled:
            return None
        current = self.current_span()
        current_metadata = dict(current.record.metadata) if current is not None else {}
        if current is not None and current.record.trace_id:
            current_metadata.setdefault("experimentos_trace_id", current.record.trace_id)
        current_metadata.update(metadata or {})
        merged_tags = [*self.settings.tags]
        for tag in tags:
            normalized = str(tag).strip()
            if normalized and normalized not in merged_tags:
                merged_tags.append(normalized)
        return {
            "metadata": current_metadata,
            "tags": merged_tags,
        }

    def _finish_root(self, record: BufferedSpanRecord) -> None:
        if not self._should_emit(record):
            return
        try:
            self._emit_root(record)
        except Exception:
            self.increment_failure()
            if self.settings.strict:
                raise

    def _should_emit(self, record: BufferedSpanRecord) -> bool:
        if not self.settings.enabled:
            return False
        if record.error is not None and self.settings.always_trace_errors:
            return True
        return _sample_trace(record.trace_id, self.settings.sampling_rate)

    def _emit_root(self, record: BufferedSpanRecord) -> None:
        raise NotImplementedError

    def force_flush(self) -> bool:
        return True

    def shutdown(self) -> bool:
        return True

    def instrument_fastapi_app(self, app: object) -> bool:
        return False


def _sample_trace(trace_id: str | None, sampling_rate: float) -> bool:
    if sampling_rate >= 1.0:
        return True
    if sampling_rate <= 0.0:
        return False
    basis = trace_id or _utc_now_iso()
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16) / 0xFFFFFFFF
    return value <= sampling_rate
