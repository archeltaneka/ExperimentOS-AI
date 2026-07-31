# Evaluation Dashboard List Design

## Goal

Replace the detailed evaluation-report layout with a compact evaluations list that closely follows `docs/ui-references/05-evaluation-dashboard.jpg` while presenting the existing ExperimentOS evaluation data truthfully.

## Scope

- Keep the route at `/evaluation-dashboard` and retain its existing query, loading state, and error recovery.
- Render a single bordered evaluations panel with a title row, a disabled `Run evaluation` button, and a compact table.
- Populate the single table row from the existing dashboard run, gate, metrics, and cases.
- Show a status badge, dataset, number of cases, number of criteria, concise quality-gate criteria, and model/run metadata.
- Remove the chart, detailed metric cards, grouped quality sections, prompt-regression block, case filter/table, integrations, and metadata cards from this route.

## Interaction and Honesty

`Run evaluation` is disabled because the application currently has no mutation or backend endpoint that can start an evaluation. It includes explanatory accessible text so users are not led to expect a working action.

The dashboard remains read-only. It does not claim live telemetry when the existing service identifies its data as a fixture.

## Visual Design

- Use the reference's restrained, bright administrative layout: one large white panel, light borders, compact typography, and a table-first hierarchy.
- Use the existing application shell and design tokens; do not recreate the reference application's navigation or brand.
- Keep the page responsive by allowing horizontal table scrolling on narrow screens.

## Validation

- Update the evaluation-domain UI test to assert the title, disabled run control, core table headings, and data-driven row content.
- Run the targeted Vitest test, web typecheck, and lint after implementation.
