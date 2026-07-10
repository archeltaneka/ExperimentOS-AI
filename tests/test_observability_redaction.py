from __future__ import annotations


def test_redaction_masks_sensitive_fields_and_limits_payload_size() -> None:
    from packages.observability.models import ObservabilitySettings
    from packages.observability.redaction import redact_payload

    settings = ObservabilitySettings(
        enabled=True,
        api_key="ls-test-key",
        project="experimentos-test",
        trace_inputs=True,
        trace_outputs=True,
        max_string_length=12,
        max_collection_length=2,
    )

    payload = {
        "question": "Should we roll out the payment recommendation experiment immediately?",
        "api_key": "secret-value",
        "authorization": "Bearer token",
        "document_chunks": ["chunk-1", "chunk-2", "chunk-3"],
        "nested": {
            "password": "hunter2",
            "cookie": "session=abc",
        },
    }

    redacted = redact_payload(payload, settings=settings)

    assert redacted["api_key"] == "<redacted>"
    assert redacted["authorization"] == "<redacted>"
    assert redacted["nested"]["password"] == "<redacted>"
    assert redacted["nested"]["cookie"] == "<redacted>"
    assert redacted["document_chunks"] == ["chunk-1", "chunk-2", "<truncated>"]
    assert redacted["question"].endswith("...")


def test_redaction_omits_prompt_and_response_content_by_default() -> None:
    from packages.observability.models import ObservabilitySettings
    from packages.observability.redaction import redact_payload

    settings = ObservabilitySettings(
        enabled=True,
        api_key="ls-test-key",
        project="experimentos-test",
        trace_inputs=False,
        trace_outputs=False,
    )

    assert redact_payload({"prompt": "full prompt text"}, settings=settings) == {
        "prompt": "<omitted>"
    }
    assert redact_payload({"answer": "full model answer"}, settings=settings, is_output=True) == {
        "answer": "<omitted>"
    }

