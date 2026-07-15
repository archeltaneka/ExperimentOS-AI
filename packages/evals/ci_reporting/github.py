from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Protocol

from packages.evals.ci_reporting.renderer import COMMENT_MARKER


class GhApiClient(Protocol):
    def request(self, method: str, endpoint: str, body: str | None = None) -> object: ...


@dataclass(frozen=True)
class CommentOutcome:
    action: str
    message: str


class SubprocessGhApiClient:
    def request(self, method: str, endpoint: str, body: str | None = None) -> object:
        command = ["gh", "api", "--method", method, endpoint]
        if method == "GET":
            command.extend(["--paginate", "--slurp"])
        if body is not None:
            command.extend(["--input", "-"])
        completed = subprocess.run(
            command,
            input=body,
            text=True,
            check=True,
            capture_output=True,
        )
        payload = json.loads(completed.stdout or "{}")
        return payload


def update_or_create_comment(
    client: GhApiClient,
    repository: str,
    pull_request_number: int,
    body: str,
) -> CommentOutcome:
    comments = _comments(
        client.request("GET", f"repos/{repository}/issues/{pull_request_number}/comments")
    )
    comment_id = _marker_comment_id(comments)
    if comment_id is not None:
        client.request("PATCH", f"repos/{repository}/issues/comments/{comment_id}", body)
        return CommentOutcome("updated", "Updated the existing ExperimentOS AI quality report.")
    client.request("POST", f"repos/{repository}/issues/{pull_request_number}/comments", body)
    return CommentOutcome("created", "Created the ExperimentOS AI quality report.")


def publish_comment(
    client: GhApiClient,
    *,
    repository: str,
    pull_request_number: int | None,
    body: str,
    is_pull_request: bool,
) -> CommentOutcome:
    if not is_pull_request or pull_request_number is None:
        return CommentOutcome(
            "skipped", "PR comment publication is disabled for non-pull-request events."
        )
    try:
        return update_or_create_comment(client, repository, pull_request_number, body)
    except (PermissionError, subprocess.CalledProcessError, OSError, ValueError) as exc:
        return CommentOutcome("unavailable", f"PR comment was not published: {exc}")


def _comments(payload: object) -> list[dict[str, object]]:
    values = payload.get("comments", payload) if isinstance(payload, dict) else payload
    if isinstance(values, list):
        comments: list[dict[str, object]] = []
        for item in values:
            if isinstance(item, dict):
                comments.append(item)
            elif isinstance(item, list):
                comments.extend(entry for entry in item if isinstance(entry, dict))
        return comments
    return []


def _marker_comment_id(comments: list[dict[str, object]]) -> int | None:
    for comment in comments:
        user = comment.get("user")
        if not isinstance(user, dict) or user.get("type") != "Bot":
            continue
        body = comment.get("body")
        comment_id = comment.get("id")
        if isinstance(body, str) and COMMENT_MARKER in body and isinstance(comment_id, int):
            return comment_id
    return None
