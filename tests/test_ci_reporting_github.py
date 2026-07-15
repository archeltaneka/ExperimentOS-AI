from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FakeGhClient:
    comments: list[dict[str, object]]
    responses: list[dict[str, object]] = field(default_factory=list)
    calls: list[tuple[str, str, str | None]] = field(default_factory=list)

    def request(self, method: str, endpoint: str, body: str | None = None) -> dict[str, object]:
        self.calls.append((method, endpoint, body))
        if self.responses:
            return self.responses.pop(0)
        if method == "GET":
            return {"comments": self.comments}
        return {"id": 99}


def test_update_or_create_updates_only_marker_owned_comment() -> None:
    from packages.evals.ci_reporting.github import COMMENT_MARKER, update_or_create_comment

    client = FakeGhClient(
        comments=[
            {"id": 1, "body": "unrelated", "user": {"type": "Bot"}},
            {"id": 42, "body": COMMENT_MARKER + "\nold", "user": {"type": "Bot"}},
        ]
    )

    outcome = update_or_create_comment(client, "owner/repo", 67, COMMENT_MARKER + "\nnew")

    assert outcome.action == "updated"
    assert client.calls[-1][0] == "PATCH"
    assert client.calls[-1][1].endswith("/issues/comments/42")


def test_update_or_create_creates_when_no_marker_owned_comment() -> None:
    from packages.evals.ci_reporting.github import COMMENT_MARKER, update_or_create_comment

    client = FakeGhClient(comments=[{"id": 1, "body": "unrelated", "user": {"type": "Bot"}}])

    outcome = update_or_create_comment(client, "owner/repo", 67, COMMENT_MARKER + "\nnew")

    assert outcome.action == "created"
    assert client.calls[-1][0] == "POST"
    assert client.calls[-1][1].endswith("/issues/67/comments")


def test_read_only_permission_failure_is_non_blocking() -> None:
    from packages.evals.ci_reporting.github import COMMENT_MARKER, publish_comment

    class ForbiddenClient(FakeGhClient):
        def request(self, method: str, endpoint: str, body: str | None = None) -> dict[str, object]:
            raise PermissionError("HTTP 403")

    outcome = publish_comment(
        ForbiddenClient(comments=[]),
        repository="owner/repo",
        pull_request_number=67,
        body=COMMENT_MARKER + "\nnew",
        is_pull_request=True,
    )

    assert outcome.action == "unavailable"
    assert "403" in outcome.message


def test_push_event_does_not_attempt_comment() -> None:
    from packages.evals.ci_reporting.github import COMMENT_MARKER, publish_comment

    client = FakeGhClient(comments=[])

    outcome = publish_comment(
        client,
        repository="owner/repo",
        pull_request_number=None,
        body=COMMENT_MARKER + "\nnew",
        is_pull_request=False,
    )

    assert outcome.action == "skipped"
    assert not client.calls
