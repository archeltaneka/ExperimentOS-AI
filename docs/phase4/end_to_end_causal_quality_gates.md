# Complete end-to-end causal quality gates

Issue #109 extends the existing statistical baseline, API evaluator, centralized
policy, and CI reporting. It adds no statistical methods or competing quality engine.

## Run offline

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run python -m packages.evals.cli statistical-baseline
```

Default `complete` scope runs native references/conformance, 39 workflow golden
cases, 36 corruption scenarios, one exporter-failure control, and 11 compatibility
records. Four compatibility records explicitly describe external checks not executed
by this command. The separate workflow inventory therefore has 87 records.
No database, live LLM, external judge, hosted exporter, or network service is required.

The existing extras job uses the same command without repeating core methods:

```bash
uv run --no-sync python -m packages.evals.cli statistical-baseline \
  --scope optional-adapters --require-optional econml --require-optional dowhy
```

Use the locked Python 3.13 `econml` and `dowhy` dependency groups. This scope has
38 native adapter cases and ten workflow cases. Its declared partial scope cannot
satisfy the complete policy. Genuine absence is advisory unless the dependency is
required; installed-but-broken or incompatible adapters fail, without native fallback.

Options:

- `--dataset FILE`: native references, retaining existing companion loading rules.
- `--workflow-dataset DIRECTORY`: complete versioned workflow inventory; malformed,
  missing, or duplicate declarations are rejected.
- `--policy FILE`: the existing centralized policy.
- `--json-output FILE`, `--output FILE`: authoritative JSON and detailed Markdown.
- `--policy-json-output FILE`, `--summary-output FILE`: optional explicit sidecars.

Sidecars default to the JSON output directory. Output destinations must be distinct.

## Ownership and evidence

```text
versioned fixtures + independent references
  → real POST /ask → real agent graph → AnalysisService → native method
  → protected evidence + gated impact → API serialization
  → reference/preservation/call/trace/privacy checks + controlled corruptions
  → schema-2 report → existing PolicyEvaluator → artifacts + exit code
```

Only external dependencies are replaced: experiment existence, fixture retrieval,
mock presentation, and controlled optional runtime failures. Analysis cases reject
retrieval. Native reference execution is separate from workflow dispatch; analytical
and DGP constants supply independent numerical references. Native/API equality tests
preservation, not independent statistical correctness.

Method-aware checks distinguish confidence and credible intervals. Typed comparisons
retain assumptions and their status, diagnostics, limitations, estimands, and provenance.
Applicable missing/skipped checks fail. Expected refusals retain native meanings.
Caller API overrides and `ASK_MODE` are restored on success and exceptions.

Replays compare method/status, statistical evidence, and business evidence. They never
discard seeds, plan/fold/configuration fingerprints, estimates, or diagnostics. Measured
durations and generated trace IDs are retained in JSON and normalized only for
cross-run semantic comparisons. A negative effect, negative impact, or interval crossing
zero is not a software defect and does not authorize rollout.

## Versioned coverage

The independent required inventory is
[`cases.py`](../../packages/evals/statistical/workflow/cases.py). Requests live in
[`data/eval/workflow_analysis`](../../data/eval/workflow_analysis),
[`fixtures.py`](../../packages/evals/statistical/workflow/fixtures.py), and
[`optional.py`](../../packages/evals/statistical/workflow/optional.py).
[`expectations.py`](../../packages/evals/statistical/workflow/expectations.py) contains
exact numerical paths, tolerances, rationales, and provenance.

| Family | Representative IDs | Independent point reference / absolute tolerance |
| --- | --- | --- |
| Fixed horizon | `randomized`, `insufficient`, `negative` | Mean difference 10 / 1e-12 |
| CUPED | `cuped-success`, `cuped-post-treatment` | Adjusted difference 3.25 / 1e-12 |
| Sequential | `sequential-success`, `sequential-invalid-plan` | Final look difference 20 / 1e-12 |
| Bayesian | `bayesian-success`, `bayesian-invalid-prior` | Beta posterior difference 6/22 / 1e-10 |
| DiD | `did`, `did-invalid-timing` | Two-by-two contrast 3 / 1e-12 |
| Propensity | `propensity-success`, `propensity-no-overlap` | Mean score 0.5 / 0.001 |
| IPW ATE/ATT | `ipw-ate-success`, `ipw-att-success`, `ipw-ate-no-overlap` | Matched-stratum effect 2 / 1e-8 |
| DML | `dml-success`, `dml-degenerate`, `dml-post-treatment` | DGP effect 2 / 0.15 |
| HTE | `hte-success`, `hte-sparse`, `hte-post-treatment` | First subgroup effect 1 / 0.35 |
| EconML | `econml_dml-real`, `econml_hte-real`, respective `-absent` and `-broken` | DGP effects 2 / 0.15 and 1 / 0.4 |
| DoWhy | `dowhy-real`, `dowhy-absent`, `dowhy-broken` | DGP effect 2 / 0.15 |
| Business | `business`, `business-negative`, `business-cross-zero`, `missing-business-provenance` | Explicit sourced inputs; preserved native calculation |
| Routing/integrity | `unsupported`, `ambiguous`, `prose_conflict`, `optional_unavailable` | Exact categorical/evidence checks |

Existing randomized, observational, and advanced native datasets provide additional
references. Finite-sample tolerances are versioned, not fitted to workflow outputs.

## Corruption and downstream gating

[`injections.py`](../../packages/evals/statistical/workflow/injections.py) is a closed
registry, never executable fixture content. It mutates real HTTP transport evidence:
p-values/intervals/status; CUPED timing/population/variance; sequential plans/spending/
boundaries; Bayesian priors/interval labels/ROPE; DiD timing/assumptions; propensity
convergence/overlap/transforms; IPW targets/clipping; DML folds/residuals; HTE modifiers/
subgroups/direct evidence; business inputs/source; and routing. Digests are recomputed
so a stale digest alone cannot detect every semantic mutation. A native dispatch
exception additionally verifies safe normalization.

Injected corruption passes only if its declared blocking rule IDs are detected.
Detected intentional violations are distinct from escaping violations. Disabling
detection fails quality; unexpected harness errors remain infrastructure failures.
Independent workflow cases continue after an error.

Request-scoped DML/IPW/business spies prove prohibited downstream calls do not occur,
with valid controls proving the spies observe calls. Existing advanced native
conformance additionally covers malformed inference, foreign/nonfinite outputs,
contradictory graphs, and refuter interpretation. Fabricated presentation cannot
replace authoritative effect, interval, posterior, or impact values.

## Traces and privacy

`ask_request` owns `workflow` and `response_serialization`; `workflow` owns `analysis`
and applicable `analysis.business_impact`; `analysis` owns `validation` and `estimator`.
Native spans attach beneath the active estimator. Checks verify actual parent links,
trace IDs, required boundaries, and completion. Policy findings correlate by safe
case/method/rule IDs; policy is not represented as part of a finished request span.

Provider/exporter failures cannot change authoritative analysis. The export control
records safe failure counts. Targeted tests exercise actual OpenTelemetry in-memory
export; the canonical compatibility record honestly labels SDK/vendor integration as
external, not executed by that run.

Recursive privacy checks inspect mappings, sequences, metadata, events, error fields,
JSON, Markdown, and summaries. They reject private keys, unit/credential patterns,
sentinels under allowed keys, raw numeric arrays, foreign objects, and nonfinite values.
Only declared aggregate row counts, quantile settings, and binary class labels receive
array/count exemptions. Rejected prose, raw rows, graphs, residuals, CATE arrays, and
exception messages are not copied into failure artifacts. These bounded fixture
checks are not a universal secret detector for arbitrary application content.

## Policy, artifacts, and exits

Default artifacts under `reports/phase4/`:

- `statistical_baseline.json`: schema 2, native results, separate typed `workflow`
  tuple, dataset hash, traces/call counts, dependency identity, and policy findings.
- `statistical_baseline.md`: detailed developer evidence and capability tables.
- `quality_policy.json`: existing policy engine decision.
- `github_summary.md`: concise counts, blockers/advisories, and explicit skips.

Native `dataset_size` and `case_results` keep their historical denominator;
`workflow_case_count` counts workflow records. Execution (`completed`, `inconclusive`,
`invalid`, `abstained`, `unavailable`, `failed`) is separate from quality (`pass`,
`warning`, `fail`, `skipped`). Expected ABSTAINED, INVALID, controlled failure, and
optional UNAVAILABLE results can satisfy correctness checks. Absence stays visible.

All 56 statistics-source rules live in
[`quality_policy.yaml`](../../config/evaluation/quality_policy.yaml), including
`analysis.*` workflow rules. Ingestion recomputes inventory, applicability, status,
forbidden-call counts, references, and injection detection. Forged zero totals,
missing cases/checks, duplicates, and partial scopes cannot pass the complete gate.
Legacy schema-1 statistical and agent JSON readers remain supported.

| Exit | Meaning |
| --- | --- |
| 0 | No blocking failures; advisory warnings/optional absence may remain |
| 1 | Blocking statistical, workflow, compatibility, or policy regression |
| 2 | Configuration, fixture, harness, parsing, rendering, or writing failure |

Infrastructure takes precedence. A typed `run_status=infrastructure_fail` artifact
contains a categorical stage/code and retains safe evaluation evidence when available.
Failure JSON/Markdown/summary replace stale successes. Unwritable destinations give a
sanitized stderr diagnostic and exit 2.

## Compatibility and CI

The command executes real legacy QA through `/ask` with fixture retrieval/mock LLM,
the existing real agent evaluator, old requests without analysis fields, internal
traces, prompt validation, Phase 3 policy guardrails, and factuality detection.
Database, LangSmith, Phoenix, and SDK integration are explicit external skips in this
matrix. A configured `DATABASE_URL` never counts as an executed database check.

The existing offline job runs complete scope. The existing extras job requires both
adapters in partial scope. The final database-backed AI gate runs the complete command
before centralized policy and requires all four artifacts. Quality exit 1 still allows
final policy reporting; infrastructure exit 2 remains distinct. PostgreSQL jobs,
Phase 3 thresholds, uploads on failure, PR markers, and fork permissions are preserved.

`scripts/verify_phase3.py --offline-only` remains a diagnostic, not strict closeout.
Its reports retain actual failures and database limitations. Successful software gates
do not establish causal identification for arbitrary data, prove refuters' nulls,
authorize business decisions, or trigger stopping, rollout, merge, or deployment.
