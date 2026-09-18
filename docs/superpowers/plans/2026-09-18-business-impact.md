# Business Impact Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development for independent tasks; implement shared contracts and integration inline. Steps use checkbox syntax for tracking.

**Goal:** Implement issue #107 as a deterministic, sourced scenario service.
**Architecture:** Owned source adapters feed a strictly validated operational request, bounded arithmetic, and an auditable result. Source evidence, business assumptions, and derived values remain separate. Existing Phase 2 descriptive reporting stays separate.
**Tech Stack:** Python 3.12+, Pydantic, pytest; no added dependency.
**Spec:** docs/superpowers/specs/2026-09-18-business-impact-design.md

## Global Constraints

- No forecasting, inference of missing business inputs, FX, ROI, or recommendations.
- Every operational input has explicit provenance, origin, and measured/assumed status.
- No network, database, or live LLM dependency in calculation or tests.
- Preserve native source statuses, identities, diagnostics, assumptions and uncertainty.
- Refuse sequential and DoWhy results without appropriate effect intervals.
- Work on the existing user-requested issue branch in this checkout.

## Task 1: Source adapters

Files: impact/sources.py, impact/source_models.py, impact/source_randomized.py,
impact/source_causal.py; tests/test_impact_sources.py.
Interface: adapt_source(source: object, subgroup_id: str | None = None) -> SourceEffect.
SourceEffect carries source identity, metric/outcome/unit/population/time, estimand,
effect scale, point and CI/credible interval, native status, provenance, conditional
flag, and typed diagnostics/warnings/assumptions. Refused adapters return an audit
with point/interval absent and blocking diagnostics. Revalidate exact owned types.

- [x] Write tests using public randomized/IPW/DML/HTE fixture services and owned results.
  Example: `assert adapt_source(invalid_source).point is None`.
- [x] Run `pytest -q tests/test_impact_sources.py`; verify missing feature failure.
- [x] Implement explicit family adapters; existing quality checks apply. Preserve
  parent CUPED/HTE evidence; ATT is a treated target; no fit/refit/import of optional libs.
- [x] Run source tests; inspect conditional outcomes and malformed result refusals.

## Task 2: Operational contracts and bounded arithmetic

Files: impact/inputs.py, impact/units.py, impact/arithmetic.py;
tests/test_impact_inputs.py, tests/test_impact_arithmetic.py.
Interfaces: InputRange(lower, upper, central=None), InputEvidence(origin, status,
provenance, reference); BusinessImpactRequest; interval operations -> Bounds.

- [x] Test rates, missing provenance, nonfinite values, unknown units and horizons.
  `with pytest.raises(ValidationError): InputRange(lower=2, upper=1)`.
- [x] Test sign-aware bounds: `multiply([-1,3], [2,4]) == [-4,12]`.
- [x] Run each new test file to observe failure before implementation.
- [x] Implement strict frozen leaf contracts, enums, explicit period alignment,
  population and exposure bases, conversions, cost declarations, and interval math.
- [x] Run tests and type checks; no midpoint/default provenance assumptions.

## Task 3: Scenario service, result and integration

Files: impact/validation.py, impact/service.py, impact/results.py,
impact/reporting.py, impact/__init__.py; analysis/__init__.py, serialization.py;
tests/impact_fixtures.py, tests/test_impact_service.py.
Interface: BusinessImpactService.analyze(source: object, request: BusinessImpactRequest
| Mapping[str, object]) -> BusinessImpactResult.

- [x] Write hand fixture and refusal tests first: source effect .02, CI [.01,.03],
  N=100000, r=.5 gives Q=1000, [500,1500], $10 gives [5000,15000], fixed $1000
  gives net [4000,14000]. Range fixture must give [-7920,23760] money.
- [x] Run focused tests and verify failure.
- [x] Implement source validation, semantic matching, explicit horizon/persistence,
  relative baseline, typed exposure/conversion, costs and currency checks.
- [x] Compute statistical-only, business-only, and combined envelopes independently;
  preserve common factors in net expression; central absent when input central absent.
- [x] Emit derived records with formula/input references, status and abstention;
  render all intervals and assumptions, never a central-only gain claim.
- [x] Cover source/malformed requests, missing provenance, zero/negative effects,
  HTE sparse/overlap/target mismatch, double exposure and annualization, no-cost
  declaration, recurrence, fixed cost once, signed incremental cost, round trips.
- [x] Run service, arithmetic, source, export/serialization regression tests.

## Task 4: Phase 2 safety and documentation

Files: packages/agents/business_impact_agent.py; tests/test_business_impact_agent.py;
docs/phase4/business_impact_scenarios.md.

- [x] Test quote without currency never produces USD; explicit code retains currency.
- [x] Run regression before fix; fix parser and descriptive/reporting labels without
  introducing new scenario inference or changing downstream decision policy.
- [x] Add runnable sourced request example and document capability/refusal table,
  period normalization, uncertainty decomposition, and declared-cost semantics.
- [x] Run legacy business agent/contracts tests.

## Task 5: Review and verification

- [x] Review all spec sections against implementation and tests; resolve safety gaps.
- [x] Run focused impact/legacy tests plus relevant analysis/source regressions.
- [x] Run `uv run ruff check .`, strict analysis mypy, and core offline suite as feasible.
- [x] Independently review branch diff, address findings and rerun affected tests.
- [x] Commit reviewed implementation on issue branch; report verification and limitations.

## Execution record

- Tasks 1–5 complete; independent safety findings resolved and verified.
- Existing checkout on the issue branch retained as requested; no extra worktree.
- Reviewed input evidence references now resolve against explicit structured
  RepositoryInputRecord values, preserving offline operation.
- Scope selectors control returned quantities; effect-independent costs/population
  do not inherit the treatment estimate confidence level.
- Existing PostgreSQL integration tests need a running localhost:5433 database;
  these eight tests are excluded from the final database-free regression run.

- Focused impact and legacy checks: 143 passed.
- Repository regression: 1880 passed, 36 skipped, 8 database-dependent tests
  deselected, 2 existing deprecation warnings.
- Ruff passed; mypy passed across 138 analysis source files.
- Follow-up independent review: all seven findings resolved; 17 targeted tests passed.
