# Phase 3 Prompt Regression

ExperimentOS AI now includes a deterministic prompt-regression workflow for prompt-backed
`legacy_rag` behavior.

## What it compares

Prompt regression compares:

- one baseline prompt version
- one candidate prompt version
- the same input cases
- the same retrieved evidence
- the same offline-safe evaluation surfaces

Current coverage focuses on the repository's real prompt-backed paths:

- `legacy_rag` QA evaluation cases from `data/eval/qa_dataset.json`
- `legacy_rag` `/ask` compatibility through the existing ask adapter

`agent_workflow` stays the default API mode and remains intentionally prompt-free.

## Command

Run the default offline prompt regression:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
uv run python -m packages.evals.run_prompt_regression --prompt-id rag.answer --baseline-version 1 --candidate-version 1 --offline --embedding-provider fake --llm-provider mock --output reports/phase3/prompt_regression.md --json-output reports/phase3/prompt_regression.json
```

Outputs:

- `reports/phase3/prompt_regression.md`
- `reports/phase3/prompt_regression.json`

## Default offline behavior

Offline mode is the default design target.

It:

- uses deterministic fake or mock-compatible evaluation inputs
- freezes retrieval once so both prompt versions see the same evidence
- avoids live OpenAI calls by default
- reuses the repository's custom evaluation, RAGAS, and DeepEval integrations in offline-safe mode

## Judge mode

`--judge` is optional.

When enabled, prompt regression forwards the existing DeepEval judge configuration into the
comparison flow. Judge metrics remain opt-in and require the same provider credentials as the
existing DeepEval workflow.

## How to add a new prompt version

1. Register the new version in `packages/llm/prompt_registry.py`.
2. Keep the existing baseline version registered.
3. Run prompt regression against the old and new versions before switching the active version.
4. Review the Markdown and JSON reports for regressions, improvements, and render failures.

## Report interpretation

The prompt regression report includes:

- compared prompt versions
- per-case baseline and candidate outputs
- deterministic metric deltas
- regression and improvement counts
- offline RAGAS and DeepEval comparison summaries

Typical regression signals:

- answer output disappeared
- expected keywords dropped
- document references disappeared
- render failures appeared
- legacy fallback response shape changed

## Limitations

- prompt regression does not use exact free-form string matching as the pass/fail source of truth
- only prompt-backed `legacy_rag` surfaces are covered today
- offline scoring is deterministic and heuristic by design, not a semantic judge by default
