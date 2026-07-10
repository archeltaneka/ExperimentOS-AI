from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FakeRunTree:
    name: str
    run_type: str
    inputs: dict[str, object] | None = None
    tags: list[str] | None = None
    extra: dict[str, object] | None = None
    client: object | None = None
    project_name: str | None = None
    children: list[FakeRunTree] = field(default_factory=list)
    outputs: dict[str, object] | None = None
    error: str | None = None
    posted: bool = False
    patched: bool = False

    def post(self) -> None:
        self.posted = True

    def create_child(self, **kwargs) -> FakeRunTree:
        child = FakeRunTree(**kwargs)
        self.children.append(child)
        return child

    def end(
        self,
        *,
        outputs: dict[str, object] | None = None,
        error: str | None = None,
    ) -> None:
        self.outputs = outputs
        self.error = error

    def patch(self) -> None:
        self.patched = True


def test_langsmith_provider_emits_root_and_child_spans_with_redacted_payloads() -> None:
    from packages.observability.langsmith import LangSmithObservabilityProvider
    from packages.observability.models import ObservabilitySettings

    settings = ObservabilitySettings(
        enabled=True,
        api_key="ls-test-key",
        project="experimentos-test",
        sampling_rate=1.0,
        trace_inputs=True,
        trace_outputs=False,
    )
    emitted: list[FakeRunTree] = []

    def fake_run_tree_factory(**kwargs):
        tree = FakeRunTree(**kwargs)
        emitted.append(tree)
        return tree

    provider = LangSmithObservabilityProvider(
        settings=settings,
        client=object(),
        run_tree_factory=fake_run_tree_factory,
    )

    root = provider.start_root_span(
        "ask_request",
        trace_id="req-123",
        inputs={"question": "hello", "api_key": "secret"},
        metadata={"experimentos_trace_id": "req-123", "surface": "ask"},
        tags=("api",),
    )
    with root.activate():
        child = provider.start_span(
            "workflow",
            run_type="chain",
            metadata={"workflow": "agent_workflow"},
        )
        child.finish(outputs={"answer": "do not export raw answer"})
    root.finish(outputs={"status": "ok"})

    assert len(emitted) == 1
    assert emitted[0].name == "ask_request"
    assert emitted[0].inputs == {"question": "hello", "api_key": "<redacted>"}
    assert emitted[0].children[0].name == "workflow"
    assert emitted[0].children[0].outputs == {"answer": "<omitted>"}
    assert emitted[0].extra["metadata"]["experimentos_trace_id"] == "req-123"


def test_langsmith_provider_skips_unsampled_successful_traces() -> None:
    from packages.observability.langsmith import LangSmithObservabilityProvider
    from packages.observability.models import ObservabilitySettings

    emitted: list[FakeRunTree] = []
    settings = ObservabilitySettings(
        enabled=True,
        api_key="ls-test-key",
        project="experimentos-test",
        sampling_rate=0.0,
    )

    provider = LangSmithObservabilityProvider(
        settings=settings,
        client=object(),
        run_tree_factory=lambda **kwargs: emitted.append(FakeRunTree(**kwargs)) or emitted[-1],
    )
    root = provider.start_root_span("ask_request", trace_id="req-123")
    root.finish(outputs={"status": "ok"})

    assert emitted == []


def test_langsmith_provider_failure_does_not_raise_and_tracks_failure_count() -> None:
    from packages.observability.langsmith import LangSmithObservabilityProvider
    from packages.observability.models import ObservabilitySettings

    settings = ObservabilitySettings(
        enabled=True,
        api_key="ls-test-key",
        project="experimentos-test",
        sampling_rate=1.0,
    )

    def boom(**kwargs):
        raise RuntimeError("langsmith transport failed")

    provider = LangSmithObservabilityProvider(
        settings=settings,
        client=object(),
        run_tree_factory=boom,
    )

    root = provider.start_root_span("ask_request", trace_id="req-123")
    root.finish(outputs={"status": "ok"})

    assert provider.failure_count == 1
