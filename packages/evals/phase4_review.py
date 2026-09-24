"""Validate and render the human Phase 4 audit; does not execute or score estimators.

Evidence is a repository-relative file digest and, optionally, an exact JSON Pointer
value. Full runtime artifacts may be checked with --verify-runtime; portable review
snapshots and source references are always checked. Readiness is derived from the
reviewer's declared findings and executed command results, not statistical outcomes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
from collections import Counter
from pathlib import Path

DIMENSIONS = frozenset(
    {
        "typed_contracts",
        "validation",
        "determinism",
        "uncertainty",
        "assumptions",
        "diagnostics",
        "abstention",
        "provenance",
        "tests",
        "evaluation",
        "quality_policy",
        "privacy",
        "ci",
        "limitations",
    }
)
CLASSIFICATIONS = frozenset(
    {
        "PRODUCTION_READY_WITHIN_SCOPE",
        "ADVISORY",
        "OPTIONAL",
        "BLOCKED",
        "UNSUPPORTED",
    }
)


def json_pointer(payload, pointer):
    """Resolve an RFC 6901 pointer without evaluating fixture content."""
    if not pointer:
        return payload
    if not pointer.startswith("/"):
        raise ValueError("invalid JSON pointer")
    for part in pointer[1:].split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        payload = payload[int(key)] if isinstance(payload, list) else payload[key]
    return payload


def readiness(review):
    blocked = (
        any(f["kind"] == "BLOCKING" or f["required_before_close"] for f in review["findings"])
        or any(
            c["required"] and (c["status"] != "pass" or c["exit_code"] != 0)
            for c in review["commands"]
        )
        or any(c["classification"] == "BLOCKED" for c in review["capabilities"])
    )
    if blocked:
        return "NOT_READY_BLOCKING_FINDINGS"
    if review["findings"] or any(
        c["classification"] in {"ADVISORY", "OPTIONAL"} for c in review["capabilities"]
    ):
        return "READY_WITH_ADVISORIES"
    return "READY_TO_CLOSE"


def validate_review(review, root: Path, *, verify_runtime=False):
    """Fail closed on stale, unresolvable or internally contradictory review claims."""
    if review["schema_version"] != "phase4-final-review-v1":
        raise ValueError("unsupported review schema")
    root = root.resolve()
    evidence = review["evidence"]
    if not evidence or not review["capabilities"] or not review["commands"]:
        raise ValueError("empty review inventory")

    def references(ids):
        if not ids or any(i not in evidence for i in ids):
            raise ValueError("missing evidence reference")

    for identity, item in evidence.items():
        path = (root / item["path"]).resolve()
        if not path.is_relative_to(root) or Path(item["path"]).is_absolute():
            raise ValueError(f"invalid evidence path: {identity}")
        if item.get("runtime_artifact", False) and not verify_runtime:
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"evidence digest mismatch: {identity}")
        if "pointer" in item:
            actual = json_pointer(json.loads(path.read_text()), item["pointer"])
            if json.dumps(actual, sort_keys=True) != json.dumps(item["value"], sort_keys=True):
                raise ValueError(f"evidence value mismatch: {identity}")

    for group in ("commands", "capabilities", "principles", "findings"):
        seen = set()
        for record in review[group]:
            if record["id"] in seen:
                raise ValueError(f"duplicate {group} identity")
            seen.add(record["id"])
            references(record["evidence"])
    for command in review["commands"]:
        result = evidence[command["evidence"][0]].get("value", {})
        if (
            not isinstance(result, dict)
            or result.get("id", result.get("command_id")) != command["id"].removeprefix("phase3.")
            or result.get("status") != command["status"]
            or result.get("exit_code") != command["exit_code"]
            or not isinstance(result.get("argv"), list)
            or shlex.join(result["argv"]) != command["command"]
        ):
            raise ValueError("command evidence contradicts execution claim")
        if command["status"] not in {"pass", "fail", "skipped", "interrupted"}:
            raise ValueError("invalid command status")
        if command["status"] == "pass" and command["exit_code"] != 0:
            raise ValueError("passing command has nonzero exit")
    for capability in review["capabilities"]:
        if capability["classification"] not in CLASSIFICATIONS:
            raise ValueError("invalid capability classification")
        if not capability["scope"] or not capability["limitations"]:
            raise ValueError("capability requires scope and limitations")
        if capability["classification"] == "PRODUCTION_READY_WITHIN_SCOPE":
            dimensions = capability.get("readiness_dimensions", {})
            if set(dimensions) != DIMENSIONS:
                raise ValueError("missing production readiness dimensions")
            for ids in dimensions.values():
                references(ids)
    for finding in review["findings"]:
        if finding["kind"] not in {"BLOCKING", "ADVISORY", "GAP"}:
            raise ValueError("invalid finding kind")
        for key in ("severity", "capability", "description", "impact", "follow_up"):
            if not finding[key]:
                raise ValueError(f"finding missing {key}")
    for section in review["sections"]:
        for claim in section["claims"]:
            references(claim["evidence"])
    if readiness(review) != review["milestone_readiness"]:
        raise ValueError("readiness contradicts findings or required command evidence")


def render_review(review):
    """Render categorical and numerical summaries exclusively from the JSON review."""

    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", "<br>")

    def refs(ids):
        return ", ".join(f"`{i}`" for i in ids)

    lines = [
        "# Final Phase 4 causal reliability review",
        "",
        f"**Milestone readiness: {review['milestone_readiness']}**",
        "",
        "Generated from `final_reliability_review.json`; evidence IDs resolve below.",
        "",
        "## Review metadata",
        "",
    ]
    for key, value in sorted(review["metadata"].items()):
        lines.append(f"- {key}: `{json.dumps(value, sort_keys=True)}`")
    lines += [
        "",
        "## Commands executed",
        "",
        "| ID | Status | Exit | Required | Command | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for c in review["commands"]:
        lines.append(
            f"| {c['id']} | {c['status']} | {c['exit_code']} | {c['required']} | "
            f"{cell(c.get('command', 'See evidence'))} | {refs(c['evidence'])} |"
        )
    lines += [
        "",
        "## Capability matrix",
        "",
        "| Capability | Classification | Supported scope | Limitations | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for c in review["capabilities"]:
        lines.append(
            f"| {c['id']} | {c['classification']} | {cell(c['scope'])} | "
            f"{cell('; '.join(c['limitations']))} | {refs(c['evidence'][:5])} |"
        )
    lines += [
        "",
        "## Engineering and statistical principle matrix",
        "",
        "| Principle | Status | Finding | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for p in review["principles"]:
        lines.append(f"| {p['id']} | {p['status']} | {cell(p['claim'])} | {refs(p['evidence'])} |")
    for section in review["sections"]:
        lines += ["", "## " + section["title"], ""]
        for claim in section["claims"]:
            lines += [claim["text"] + " Evidence: " + refs(claim["evidence"]) + ".", ""]
    counts = Counter(f["kind"] for f in review["findings"])
    lines += [
        "",
        "## Findings and follow-ups",
        "",
        f"Blocking: {counts['BLOCKING']}; advisory: {counts['ADVISORY']}; gaps: {counts['GAP']}.",
        "",
    ]
    for f in review["findings"]:
        lines += [
            f"### {f['id']} — {f['kind']} / {f['severity']}",
            "",
            f"Capability: {f['capability']}. {f['description']}",
            "",
            f"Impact: {f['impact']}",
            "",
            f"Follow-up: {f['follow_up']}",
            "",
            f"Required before close: {f['required_before_close']}. "
            f"Evidence: {refs(f['evidence'])}.",
            "",
        ]
    lines += [
        "## Evidence index",
        "",
        "Paths are relative to the repository root. SHA-256 digests and exact JSON Pointer "
        "values are in the authoritative JSON. Runtime artifacts remain local; "
        "portable snapshots are committed.",
        "",
    ]
    for identity, e in sorted(review["evidence"].items()):
        lines.append(
            f"- `{identity}`: `{e['path']}`" + (f" → `{e['pointer']}`" if "pointer" in e else "")
        )
    lines += ["", "## Final milestone readiness", "", review["milestone_readiness"], ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--review", type=Path, default=Path("reports/phase4/final_reliability_review.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("reports/phase4/final_reliability_review.md")
    )
    parser.add_argument(
        "--check", action="store_true", help="Verify existing Markdown without writing."
    )
    parser.add_argument(
        "--verify-runtime", action="store_true", help="Also require local raw execution artifacts."
    )
    args = parser.parse_args(argv)
    try:
        review = json.loads(args.review.read_text())
        validate_review(review, Path.cwd(), verify_runtime=args.verify_runtime)
        markdown = render_review(review)
        if args.check:
            if args.output.read_text() != markdown:
                raise ValueError("Markdown differs from authoritative JSON")
        else:
            args.output.write_text(markdown)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print(f"Review validation failed: {type(exc).__name__}: {exc}")
        return 1
    print(f"Review validated: {review['milestone_readiness']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
