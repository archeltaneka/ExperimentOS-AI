## Issue #31 final-review fix

- Scope: `packages/agents/human_approval_agent.py`, `tests/test_human_approval_agent.py`
- Root cause: `decision["approval_required"]` was coerced with `bool(...)`, so malformed values like `"true"` and `None` were treated as valid control input instead of triggering the safe fallback.
- Fix: require `decision["approval_required"]` to be an actual `bool`; if the decision is missing or the value is not a `bool`, append `human_approval_missing_decision` and return the canonical fallback with `status="not_requested"`, `required=False`, empty feedback, and null actor/timestamp.
- Tests added: regression coverage for malformed `approval_required` values with string and `None` inputs.

### Verification

- `uv run pytest tests\test_human_approval_agent.py`
  - Result: 11 passed
- `uv run ruff check .`
  - Result: All checks passed
