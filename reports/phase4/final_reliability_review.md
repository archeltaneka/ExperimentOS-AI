# Final Phase 4 causal reliability review

**Milestone readiness: READY_WITH_ADVISORIES**

Generated from `final_reliability_review.json`; evidence IDs resolve below.

## Review metadata

- baseline_version: `"3.0.0"`
- branch: `"110-final-phase4-reliability-review"`
- core_python: `"3.12.14"`
- dependency_versions: `{"core": {"arize-phoenix-otel": "0.16.1", "deepeval": "4.0.7", "dowhy": null, "econml": null, "langgraph": "1.2.8", "langsmith": "0.9.8", "numpy": "2.5.0", "opentelemetry-sdk": "1.43.0", "pydantic": "2.13.4", "ragas": "0.4.3", "scikit-learn": "1.9.0", "scipy": "1.18.0", "statsmodels": null}, "optional": {"dowhy": "0.14", "econml": "0.17.0", "numpy": "2.5.0", "pandas": "3.0.3", "scikit-learn": "1.9.0", "scipy": "1.18.0", "statsmodels": "0.15.0"}}`
- git_commit: `"9bfa1ebd20f0ccc588d09e375f36ea60f9b85ec5"`
- issue: `"https://github.com/archeltaneka/ExperimentOS-AI/issues/110"`
- lock_sha256: `"4ef8866e3955dfa96b9063685d9adc9d88ec371bc763fc1e2b5157670305907f"`
- optional_python: `"3.13.15"`
- policy_version: `"2026-09-18"`
- review_date: `"2026-09-24T04:42:02.554546+00:00"`
- review_scope: `"Phase 4 bounded statistical/causal execution and Phase 1\u20133 compatibility; no deployment certification."`
- source_state: `"Base commit plus the uncommitted review/reporting and documentation diff; source evidence is individually hashed."`

## Commands executed

| ID | Status | Exit | Required | Command | Evidence |
| --- | --- | --- | --- | --- | --- |
| format | pass | 0 | True | uv run ruff format --check . | `command-format` |
| lint | pass | 0 | True | uv run ruff check . | `command-lint` |
| mypy | pass | 0 | True | uv run mypy | `command-mypy` |
| phase3-strict | pass | 0 | True | uv run python scripts/verify_phase3.py --artifact-root artifacts/issue110/phase3 --report-root artifacts/issue110/phase3-review | `command-phase3-strict` |
| phase4-core | interrupted | 143 | False | uv run --no-sync python -m packages.evals.cli statistical-baseline --json-output artifacts/issue110/core/statistical_baseline.json --output artifacts/issue110/core/statistical_baseline.md | `command-phase4-core` |
| phase4-core-retry | pass | 0 | True | uv run --no-sync python -m packages.evals.cli statistical-baseline --json-output artifacts/issue110/core/statistical_baseline.json --output artifacts/issue110/core/statistical_baseline.md | `command-phase4-core-retry` |
| phase4-optional | interrupted | -15 | False | /tmp/phase4-quality-extras.gPBKf1/bin/python -m packages.evals.cli statistical-baseline --scope optional-adapters --require-optional econml --require-optional dowhy --json-output artifacts/issue110/optional/statistical_baseline.json --output artifacts/issue110/optional/statistical_baseline.md | `command-phase4-optional` |
| phase4-optional-retry | pass | 0 | True | /tmp/phase4-quality-extras.gPBKf1/bin/python -m packages.evals.cli statistical-baseline --scope optional-adapters --require-optional econml --require-optional dowhy --json-output artifacts/issue110/optional/statistical_baseline.json --output artifacts/issue110/optional/statistical_baseline.md | `command-phase4-optional-retry` |
| report-tests | pass | 0 | True | .venv/bin/python -m pytest -q tests/test_phase4_final_review.py --junitxml=artifacts/issue110/report-tests.xml | `command-report-tests` |
| tests-core | interrupted | -15 | False | .venv/bin/python -m pytest -q -ra --tb=short --junitxml=artifacts/issue110/core-tests.xml | `command-tests-core` |
| tests-core-retry | pass | 0 | True | .venv/bin/python -m pytest -q -ra --tb=short --junitxml=artifacts/issue110/core-tests.xml | `command-tests-core-retry` |
| tests-final | pass | 0 | True | uv run pytest -q -ra --tb=short --junitxml=artifacts/issue110/final-tests.xml | `command-tests-final` |
| tests-optional | fail | 4 | False | /tmp/phase4-quality-extras.gPBKf1/bin/python -m pytest -q -ra tests/test_advanced_conformance_cases.py tests/test_advanced_conformance_contracts.py tests/test_advanced_conformance_integration.py tests/test_advanced_conformance_mutations.py tests/test_advanced_conformance_privacy.py tests/test_advanced_dependency_states.py tests/test_econml_adapters.py tests/test_dowhy_estimation.py tests/test_dowhy_refuters.py tests/test_phase4_workflow_optional.py --junitxml=artifacts/issue110/optional-tests.xml | `command-tests-optional` |
| tests-optional-corrected | pass | 0 | True | /tmp/phase4-quality-extras.gPBKf1/bin/python -m pytest -q -ra tests/test_advanced_conformance_artifacts.py tests/test_advanced_conformance_cases.py tests/test_advanced_conformance_contracts.py tests/test_advanced_conformance_integration.py tests/test_advanced_conformance_mutations.py tests/test_advanced_conformance_privacy.py tests/test_advanced_dependency_states.py tests/test_econml_contracts.py tests/test_econml_dependency.py tests/test_econml_dml.py tests/test_econml_hte.py tests/test_econml_observability.py tests/test_econml_quality.py tests/test_econml_references.py tests/test_econml_safeguards.py tests/test_dowhy_contracts.py tests/test_dowhy_dependency.py tests/test_dowhy_documentation.py tests/test_dowhy_estimation.py tests/test_dowhy_graph.py tests/test_dowhy_identification.py tests/test_dowhy_observability.py tests/test_dowhy_public_independence.py tests/test_dowhy_quality.py tests/test_dowhy_refuters.py tests/test_phase4_workflow_optional.py --junitxml=artifacts/issue110/optional-tests.xml | `command-tests-optional-corrected` |
| phase3.ci_report.build | pass | 0 | True | uv run python -m packages.evals.run_ci_report build --report-dir artifacts/issue110/phase3/quality_gate --quality-policy-report artifacts/issue110/phase3/quality_gate/phase3/quality_policy.json --output artifacts/issue110/phase3/ci/pr_quality_report.json --format all --strict | `phase3-ci_report.build` |
| phase3.ci_report.render | pass | 0 | True | uv run python -m packages.evals.run_ci_report render --input artifacts/issue110/phase3/ci/pr_quality_report.json --format pr-comment --output artifacts/issue110/phase3/ci/pr_comment.md | `phase3-ci_report.render` |
| phase3.ci_report.validate | pass | 0 | True | uv run python -m packages.evals.run_ci_report validate --input artifacts/issue110/phase3/ci/pr_quality_report.json | `phase3-ci_report.validate` |
| phase3.config.lock | pass | 0 | True | uv lock --check | `phase3-config.lock` |
| phase3.database.ingest.1.exp-001-payment-recommendation | pass | 0 | True | uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-001-payment-recommendation --embedding-provider fake | `phase3-database.ingest.1.exp-001-payment-recommendation` |
| phase3.database.ingest.1.exp-002-hotel-image-quality | pass | 0 | True | uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-002-hotel-image-quality --embedding-provider fake | `phase3-database.ingest.1.exp-002-hotel-image-quality` |
| phase3.database.ingest.1.exp-003-search-ranking | pass | 0 | True | uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-003-search-ranking --embedding-provider fake | `phase3-database.ingest.1.exp-003-search-ranking` |
| phase3.database.ingest.1.exp-004-checkout-ux | pass | 0 | True | uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-004-checkout-ux --embedding-provider fake | `phase3-database.ingest.1.exp-004-checkout-ux` |
| phase3.database.ingest.1.exp-005-pricing | pass | 0 | True | uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-005-pricing --embedding-provider fake | `phase3-database.ingest.1.exp-005-pricing` |
| phase3.database.ingest.1.exp-006-loyalty | pass | 0 | True | uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-006-loyalty --embedding-provider fake | `phase3-database.ingest.1.exp-006-loyalty` |
| phase3.database.ingest.1.exp-007-crm-notifications | pass | 0 | True | uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-007-crm-notifications --embedding-provider fake | `phase3-database.ingest.1.exp-007-crm-notifications` |
| phase3.database.ingest.1.exp-008-recommendation-systems | pass | 0 | True | uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-008-recommendation-systems --embedding-provider fake | `phase3-database.ingest.1.exp-008-recommendation-systems` |
| phase3.database.ingest.1.exp-009-search-filters | pass | 0 | True | uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-009-search-filters --embedding-provider fake | `phase3-database.ingest.1.exp-009-search-filters` |
| phase3.database.ingest.1.exp-010-premium-subscriptions | pass | 0 | True | uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-010-premium-subscriptions --embedding-provider fake | `phase3-database.ingest.1.exp-010-premium-subscriptions` |
| phase3.database.ingest.2.exp-001-payment-recommendation | pass | 0 | True | uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-001-payment-recommendation --embedding-provider fake | `phase3-database.ingest.2.exp-001-payment-recommendation` |
| phase3.database.ingest.2.exp-002-hotel-image-quality | pass | 0 | True | uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-002-hotel-image-quality --embedding-provider fake | `phase3-database.ingest.2.exp-002-hotel-image-quality` |
| phase3.database.ingest.2.exp-003-search-ranking | pass | 0 | True | uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-003-search-ranking --embedding-provider fake | `phase3-database.ingest.2.exp-003-search-ranking` |
| phase3.database.ingest.2.exp-004-checkout-ux | pass | 0 | True | uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-004-checkout-ux --embedding-provider fake | `phase3-database.ingest.2.exp-004-checkout-ux` |
| phase3.database.ingest.2.exp-005-pricing | pass | 0 | True | uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-005-pricing --embedding-provider fake | `phase3-database.ingest.2.exp-005-pricing` |
| phase3.database.ingest.2.exp-006-loyalty | pass | 0 | True | uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-006-loyalty --embedding-provider fake | `phase3-database.ingest.2.exp-006-loyalty` |
| phase3.database.ingest.2.exp-007-crm-notifications | pass | 0 | True | uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-007-crm-notifications --embedding-provider fake | `phase3-database.ingest.2.exp-007-crm-notifications` |
| phase3.database.ingest.2.exp-008-recommendation-systems | pass | 0 | True | uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-008-recommendation-systems --embedding-provider fake | `phase3-database.ingest.2.exp-008-recommendation-systems` |
| phase3.database.ingest.2.exp-009-search-filters | pass | 0 | True | uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-009-search-filters --embedding-provider fake | `phase3-database.ingest.2.exp-009-search-filters` |
| phase3.database.ingest.2.exp-010-premium-subscriptions | pass | 0 | True | uv run python -m packages.ingestion.load_experiment --experiment-dir data/synthetic/experiments/exp-010-premium-subscriptions --embedding-provider fake | `phase3-database.ingest.2.exp-010-premium-subscriptions` |
| phase3.database.migrate | pass | 0 | True | uv run alembic upgrade head | `phase3-database.migrate` |
| phase3.format.check | pass | 0 | True | uv run ruff format --check . | `phase3-format.check` |
| phase3.lint | pass | 0 | True | uv run ruff check . | `phase3-lint` |
| phase3.observability.dry_run.langsmith | pass | 0 | True | uv run python -m packages.observability.cli dry-run --provider langsmith | `phase3-observability.dry_run.langsmith` |
| phase3.observability.dry_run.opentelemetry | pass | 0 | True | uv run python -m packages.observability.cli dry-run --provider opentelemetry | `phase3-observability.dry_run.opentelemetry` |
| phase3.observability.dry_run.phoenix | pass | 0 | True | uv run python -m packages.observability.cli dry-run --provider phoenix | `phase3-observability.dry_run.phoenix` |
| phase3.observability.status | pass | 0 | True | uv run python -m packages.observability.cli status --provider all | `phase3-observability.status` |
| phase3.observability.validate | pass | 0 | True | uv run python -m packages.observability.cli validate --provider all | `phase3-observability.validate` |
| phase3.prompt.experiment.validate | pass | 0 | True | uv run python -m packages.evals.run_prompt_experiment validate --experiment rag-answer-abstention-v1-v2 | `phase3-prompt.experiment.validate` |
| phase3.prompt.registry.validate | pass | 0 | True | uv run python -m packages.llm.prompt_registry_cli validate | `phase3-prompt.registry.validate` |
| phase3.quality_gate.full | pass | 0 | True | uv run python scripts/run_ai_quality_gate.py --artifact-root artifacts/issue110/phase3/quality_gate --dataset data/eval/qa_dataset.json --agent-dataset data/eval/agent_dataset.json | `phase3-quality_gate.full` |
| phase3.tests.database | pass | 0 | True | uv run pytest -q tests/test_alembic_config.py tests/test_db_models.py tests/test_ingestion_load_experiment.py tests/test_retrieval_service.py tests/test_retrieval_agent.py tests/test_api_ask_db_integration.py | `phase3-tests.database` |
| phase3.tests.focused | pass | 0 | True | uv run pytest -q tests/test_phase3_dataset_integrity.py tests/test_phase3_architecture.py tests/test_env_config.py tests/test_api_health.py tests/test_api_ask.py tests/test_agent_workflow.py tests/test_evaluation_harness.py tests/test_agent_evaluation.py tests/test_agent_e2e_evaluation.py tests/test_ragas_evaluation.py tests/test_deepeval_evaluation.py tests/test_prompt_registry.py tests/test_prompt_registry_cli.py tests/test_prompt_regression.py tests/test_prompt_experiment_validation.py tests/test_prompt_experiment_runner.py tests/test_prompt_experiment_cli.py tests/test_factuality.py tests/test_quality_policy.py tests/test_observability_config.py tests/test_observability_cli.py tests/test_observability_langsmith.py tests/test_observability_phoenix.py tests/test_observability_opentelemetry.py tests/test_observability_composite.py tests/test_observability_redaction.py tests/test_observability_integration.py tests/test_ci_quality_gate.py tests/test_ci_reporting.py tests/test_github_actions_ci.py tests/test_repository_hygiene.py tests/test_phase3_verification.py | `phase3-tests.focused` |
| phase3.tests.full | pass | 0 | True | uv run pytest -q | `phase3-tests.full` |

## Capability matrix

| Capability | Classification | Supported scope | Limitations | Evidence |
| --- | --- | --- | --- | --- |
| statistical_contracts | PRODUCTION_READY_WITHIN_SCOPE | Frozen owned requests/results, metric, estimand, assumptions, diagnostics, uncertainty, provenance and abstention contracts. | Typed validity does not establish study validity; caller declarations remain evidence, not proof. | `doc-statistical_contracts`, `source-statistical_contracts`, `core`, `core-policy`, `core-tests` |
| eligibility_validation | PRODUCTION_READY_WITHIN_SCOPE | Explicit design/data/method eligibility before execution. | Unknown or unsupported designs abstain; no automatic repair of inputs. | `doc-eligibility_validation`, `source-eligibility_validation`, `core`, `core-policy`, `core-tests` |
| descriptive_statistics | PRODUCTION_READY_WITHIN_SCOPE | Deterministic eligible arm summaries and missingness diagnostics. | Descriptive summaries are not causal effects or significance tests. | `doc-descriptive_statistics`, `source-descriptive_statistics`, `core`, `core-policy`, `core-tests` |
| fixed_horizon | PRODUCTION_READY_WITHIN_SCOPE | Two independent randomized arms, continuous Welch or binary two-proportion z, treatment minus control, two-sided fixed-horizon inference. | Binary Wald interval is asymptotic; sparse cells are gated. Zero baseline suppresses undefined relative lift. No clustering, paired or repeated-peeking guarantee. | `doc-fixed_horizon`, `source-fixed_horizon`, `core`, `core-policy`, `core-tests` |
| cuped | PRODUCTION_READY_WITHIN_SCOPE | One pre-treatment continuous covariate; pooled complete-case theta; same retained-population Welch comparison. | No causal-confounding repair; constant covariate abstains; negative variance reduction is permitted and disclosed. | `doc-cuped`, `source-cuped`, `core`, `core-policy`, `core-tests` |
| sequential | PRODUCTION_READY_WITHIN_SCOPE | Registered immutable discrete looks with O’Brien-Fleming-shaped weighted Bonferroni alpha spending. | Not exact canonical joint-normal O’Brien-Fleming. Look-level fixed-horizon intervals are contextual, not sequentially adjusted; no automatic stopping or business-impact inference. | `doc-sequential`, `source-sequential`, `core`, `core-policy`, `core-tests` |
| bayesian | PRODUCTION_READY_WITHIN_SCOPE | Caller-supplied Beta-Binomial or Normal-Inverse-Gamma priors; deterministic quadrature; equal-tailed credible intervals and posterior superiority. | Priors and likelihood are assumptions. No posterior Monte Carlo sampling; ROPE only if declared. No frequentist significance label. | `doc-bayesian`, `source-bayesian`, `core`, `core-policy`, `core-tests` |
| causal_identification | PRODUCTION_READY_WITHIN_SCOPE | Explicit causal design, estimand, timing, adjustment set and required assumptions, separated from estimation. | Identified means conditional on the supplied assumptions; exchangeability and parallel trends are not proven. No effect or effect interval from identification alone. | `doc-causal_identification`, `source-causal_identification`, `core`, `core-policy`, `core-tests` |
| did | ADVISORY | Two-group/two-period balanced panel ATT contrast; common stable adoption; unit-cluster CR1 t uncertainty. | No staggered adoption or treatment reversal. Minimum-cluster gates cannot establish nominal small-sample coverage; few-cluster/pretrend concerns remain explicit. Parallel trends is conditional. | `doc-did`, `source-did`, `core`, `core-policy`, `core-tests` |
| propensity_diagnostics | PRODUCTION_READY_WITHIN_SCOPE | Explicit pre-treatment numeric/categorical adjustment set, deterministic logistic propensity fit, overlap, balance, convergence and ESS. | Diagnostic only: no treatment-effect or causal-proof claim. Severe overlap/separation blocks downstream readiness. | `doc-propensity_diagnostics`, `source-propensity_diagnostics`, `core`, `core-policy`, `core-tests` |
| ipw_ate | ADVISORY | Full-population ATE using explicit propensity weights, Hájek arm means, overlap/ESS/balance gates and normal uncertainty. | Uncertainty conditions on fitted scores and can understate propensity-model estimation uncertainty. Stabilization/clipping only if explicit and recorded. No unmeasured-confounding guarantee. | `doc-ipw_ate`, `source-ipw_ate`, `core`, `core-policy`, `core-tests` |
| ipw_att | ADVISORY | Treated-population ATT using explicit propensity weights, Hájek arm means, overlap/ESS/balance gates and normal uncertainty. | Uncertainty conditions on fitted scores and can understate propensity-model estimation uncertainty. Stabilization/clipping only if explicit and recorded. No unmeasured-confounding guarantee. | `doc-ipw_att`, `source-ipw_att`, `core`, `core-policy`, `core-tests` |
| dml | PRODUCTION_READY_WITHIN_SCOPE | Binary treatment, continuous outcome, numeric pre-treatment adjustment, partially linear constant-effect ATE, deterministic stratified folds and held-out orthogonal scores. | No IV-DML or automatic nuisance selection. Asymptotic influence uncertainty and asserted exchangeability; no cross-platform bitwise guarantee. | `doc-dml`, `source-dml`, `core`, `core-policy`, `core-tests` |
| hte | ADVISORY | Registered discrete categorical or fixed-bin subgroup ATEs using held-out DML interactions, direct contrasts and multiplicity context. | Not individualized CATE or uplift recommendations. Subgroup power/overlap and asymptotic inference limits; no data-mined subgroup discovery. | `doc-hte`, `source-hte`, `core`, `core-policy`, `core-tests` |
| econml_adapters | OPTIONAL | EconML 0.17.0 LinearDML constant-effect ATE and LinearDRLearner two prespecified binary subgroup effects; owned normalized HC1 inference. | Optional runtime only; no estimator objects cross boundaries. Model/identification assumptions remain conditional. Tested Python 3.13 runtime does not establish all platforms. | `doc-econml_adapters`, `source-econml_adapters`, `core`, `core-policy`, `core-tests` |
| dowhy_identification | OPTIONAL | Explicit graph/backdoor ATE identification conditional on the declared graph. | No graph discovery or graph-truth proof. Refuter non-rejection does not establish causality. Estimation provides no effect interval and cannot support business-impact inference. | `doc-dowhy_identification`, `source-dowhy_identification`, `core`, `core-policy`, `core-tests` |
| dowhy_estimation | OPTIONAL | One backdoor linear-regression handoff, advisory point estimate only. | No graph discovery or graph-truth proof. Refuter non-rejection does not establish causality. Estimation provides no effect interval and cannot support business-impact inference. | `doc-dowhy_estimation`, `source-dowhy_estimation`, `core`, `core-policy`, `core-tests` |
| dowhy_refutation | OPTIONAL | Seeded placebo-treatment, random-common-cause and data-subset refuters. | No graph discovery or graph-truth proof. Refuter non-rejection does not establish causality. Estimation provides no effect interval and cannot support business-impact inference. | `doc-dowhy_refutation`, `source-dowhy_refutation`, `core`, `core-policy`, `core-tests` |
| business_impact | PRODUCTION_READY_WITHIN_SCOPE | Owned eligible effect plus explicit sourced population, exposure, horizon, conversion, costs and compatible units/currency; statistical and scenario bands remain distinct. | Not a forecast or rollout recommendation; no invented revenue, ROI, midpoint, costs or exposure. Sequential and DoWhy interval-free sources refuse. Conditional source assumptions survive. | `doc-business_impact`, `source-business_impact`, `core`, `core-policy`, `core-tests` |
| analysis_service | PRODUCTION_READY_WITHIN_SCOPE | Explicit registry dispatch and deterministic execution through AnalysisService. | Only declared methods and evidence-supported inputs; presentation cannot override statistical results. No autonomous rollout or live-LLM statistical calculation. | `doc-analysis_service`, `source-analysis_service`, `core`, `core-policy`, `core-tests` |
| workflow_integration | PRODUCTION_READY_WITHIN_SCOPE | Real existing agent graph preserves authoritative results, assumptions, diagnostics and human approval. | Only declared methods and evidence-supported inputs; presentation cannot override statistical results. No autonomous rollout or live-LLM statistical calculation. | `doc-workflow_integration`, `source-workflow_integration`, `core`, `core-policy`, `core-tests` |
| api_integration | PRODUCTION_READY_WITHIN_SCOPE | Optional structured POST /ask analysis fields; old requests and legacy_rag remain supported. | Only declared methods and evidence-supported inputs; presentation cannot override statistical results. No autonomous rollout or live-LLM statistical calculation. | `doc-api_integration`, `source-api_integration`, `core`, `core-policy`, `core-tests` |
| structured_artifacts | PRODUCTION_READY_WITHIN_SCOPE | Owned immutable/fingerprinted statistical evidence through serialization and report rendering. | Only declared methods and evidence-supported inputs; presentation cannot override statistical results. No autonomous rollout or live-LLM statistical calculation. | `doc-structured_artifacts`, `source-structured_artifacts`, `core`, `core-policy`, `core-tests` |
| abstention_propagation | PRODUCTION_READY_WITHIN_SCOPE | Native refusals preserved; prohibited estimator/business calls are absent with positive controls. | Only declared methods and evidence-supported inputs; presentation cannot override statistical results. No autonomous rollout or live-LLM statistical calculation. | `doc-abstention_propagation`, `source-abstention_propagation`, `core`, `core-policy`, `core-tests` |
| statistical_baseline | PRODUCTION_READY_WITHIN_SCOPE | Versioned independent references and controlled negative fixtures, method-aware centralized policy, deterministic offline execution and machine-readable artifacts. | Finite fixture/reference coverage is not universal statistical proof. Optional real-runtime coverage is separate. Vendor services are dry-run/in-memory only. | `doc-statistical_baseline`, `source-statistical_baseline`, `core`, `core-policy`, `core-tests` |
| randomized_reliability | PRODUCTION_READY_WITHIN_SCOPE | Versioned independent references and controlled negative fixtures, method-aware centralized policy, deterministic offline execution and machine-readable artifacts. | Finite fixture/reference coverage is not universal statistical proof. Optional real-runtime coverage is separate. Vendor services are dry-run/in-memory only. | `doc-randomized_reliability`, `source-randomized_reliability`, `core`, `core-policy`, `core-tests` |
| observational_reliability | PRODUCTION_READY_WITHIN_SCOPE | Versioned independent references and controlled negative fixtures, method-aware centralized policy, deterministic offline execution and machine-readable artifacts. | Finite fixture/reference coverage is not universal statistical proof. Optional real-runtime coverage is separate. Vendor services are dry-run/in-memory only. | `doc-observational_reliability`, `source-observational_reliability`, `core`, `core-policy`, `core-tests` |
| advanced_conformance | PRODUCTION_READY_WITHIN_SCOPE | Versioned independent references and controlled negative fixtures, method-aware centralized policy, deterministic offline execution and machine-readable artifacts. | Finite fixture/reference coverage is not universal statistical proof. Optional real-runtime coverage is separate. Vendor services are dry-run/in-memory only. | `doc-advanced_conformance`, `source-advanced_conformance`, `core`, `core-policy`, `core-tests` |
| end_to_end_quality_gate | PRODUCTION_READY_WITHIN_SCOPE | Versioned independent references and controlled negative fixtures, method-aware centralized policy, deterministic offline execution and machine-readable artifacts. | Finite fixture/reference coverage is not universal statistical proof. Optional real-runtime coverage is separate. Vendor services are dry-run/in-memory only. | `doc-end_to_end_quality_gate`, `source-end_to_end_quality_gate`, `core`, `core-policy`, `core-tests` |
| unsupported_extensions | UNSUPPORTED | No supported implementation claim for staggered DiD, IV-DML, causal forests, discovered/individualized HTE, graph discovery, autonomous rollout or ROI calculation. | These are explicit exclusions, not features removed to hide regressions. | `doc-unsupported_extensions`, `source-unsupported_extensions`, `core`, `core-policy`, `core-tests` |

## Engineering and statistical principle matrix

| Principle | Status | Finding | Evidence |
| --- | --- | --- | --- |
| deterministic_statistics | PASS | Deterministic native calculations, stable folds and seeded optional paths are replayed within their runtime; no universal bitwise claim. | `core`, `optional`, `core-tests`, `optional-tests` |
| typed_inputs_outputs | PASS | Owned immutable contracts define inputs, outputs, semantic uncertainty and provenance. | `source-statistical_contracts`, `test-test_analysis_contract_serialization`, `core-tests` |
| assumptions_explicit | PASS | ASSERTED and UNVERIFIED remain distinct from diagnostic support; exchangeability cannot be declared fully testable. | `assumptions`, `native-causal_identification`, `core-tests` |
| no_fabricated_statistics | PASS | Closed corruption scenarios must trigger declared blocking rules; fabricated presenter effects, p-values, intervals and posterior claims cannot replace structured evidence. | `injections`, `core`, `test-test_phase4_workflow_injections`, `phase3` |
| no_fabricated_financial_impact | PASS | Explicit sourced inputs and dimensional checks precede impact calculation; ROI is not calculated. | `source-business_impact`, `test-test_impact_service`, `phase3` |
| uncertainty_semantics | PASS | Confidence, credible, conditional-score and scenario uncertainty retain distinct semantics; interval-free paths cannot imply effect certainty. | `doc-bayesian`, `doc-sequential`, `doc-ipw_ate`, `doc-business_impact`, `core` |
| causal_vs_associational | PASS | Identification precedes observational estimation and stays conditional on assumptions; propensity is diagnostic, subgroup ATE is not individualized CATE. | `doc-causal_identification`, `doc-propensity_diagnostics`, `doc-hte` |
| diagnostics_and_abstention | PASS | Insufficient samples, timing, plan/prior failures, overlap, degeneracy and missing business provenance preserve refusal and downstream gating. | `test-test_phase4_workflow_gating`, `core`, `core-tests` |
| provenance | PASS | Source identity, estimand, configuration/fold/plan fingerprints, dependency versions and business input provenance are preserved. | `registry`, `integrity`, `core`, `optional` |
| backward_compatibility | PASS | Executed core and database-backed Phase 3 suites retain old API, RAG retrieval/citations, agent workflow and fallback behavior. | `phase3`, `core-tests`, `test-test_phase4_backward_compatibility` |
| agent_workflow_default | PASS | Default graph and human approval behavior are covered by API/workflow and database suites. | `test-test_agent_workflow`, `test-test_api_ask`, `phase3` |
| legacy_rag_supported | PASS | Legacy QA and real database retrieval/citations are executed, not inferred from configuration. | `test-test_phase4_backward_compatibility`, `phase3` |
| tests_for_components | PASS | Full core suite, database suite, installed adapters and report negative tests executed; skips remain explicit. | `core-tests`, `optional-tests`, `report-tests`, `phase3` |
| evaluation_integration | PASS | Canonical complete command and optional scope reuse existing reference/conformance/workflow fixtures. | `core`, `optional`, `workflow-cases` |
| centralized_quality_policy | PASS | Policy owns thresholds; required inventories and corrupted or incomplete evidence fail closed; unfavorable effects alone do not fail quality. | `policy`, `core-policy`, `test-test_phase4_workflow_policy` |
| ci_coverage | PASS | Current-base CI execution includes core, optional, offline and database gates; YAML retains always-upload artifacts and concise summaries. | `ci`, `ci-config`, `test-test_phase4_backward_compatibility` |
| third_party_isolation | PASS | Optional estimators, inference objects and raw exceptions stay private; boundary/foreign-object conformance checks execute. | `optional`, `optional-tests`, `source-econml_adapters`, `source-dowhy_identification` |
| context7_history | GAP | Committed EconML and DoWhy consultation records exist; separate historical SciPy/scikit-learn/statsmodels consultation is not established by the searched records. | `context7`, `context7-econml`, `context7-dowhy` |
| no_live_llm_statistics | PASS | Deterministic estimators execute with mock presentation; external network is blocked in tests and no judge or hosted exporter is required. | `network-guard`, `environment`, `phase3`, `registry` |
| privacy_and_optional_observability | PASS | Recursive negative fixtures, actual parent links, in-memory OpenTelemetry and provider-failure isolation execute; no hosted service claim. | `privacy`, `test-test_phase4_workflow_telemetry`, `core-tests`, `phase3` |
| versioned_prompts | PASS | Registry validation, prompt experiments/regression and factuality checks execute in strict Phase 3 verification. | `phase3` |
| no_post_treatment_leakage | PASS | Post-treatment adjustments/modifiers refuse before estimator work; cross-fit audits observe held-out predictions. | `test-test_phase4_workflow_gating`, `test-test_dml_crossfit`, `core`, `optional` |
| sequential_alpha_control | PASS | Frozen preregistered looks and weighted Bonferroni increments control the declared discrete-look budget; ordinary CIs remain contextual. | `doc-sequential`, `native-sequential`, `core-tests` |
| hte_direct_evidence | PASS | Direct subgroup contrasts and multiplicity context are required; subgroup significance differences alone are not heterogeneity proof. | `doc-hte`, `test-test_hte_quality`, `native-repository_hte` |
| dowhy_conditional_refutation | PASS | Graph-conditional identification and bounded refuter semantics do not assert discovered or proven causality. | `doc-dowhy_identification`, `doc-dowhy_refutation`, `optional` |
| operational_assumptions | PASS | Measured versus assumed business quantities and source uncertainty remain separate; crossing zero or negative impact is valid. | `doc-business_impact`, `test-test_impact_integration`, `core` |

## Executive summary

The supported bounded implementation is READY_WITH_ADVISORIES. Complete-scope evaluation contains 142 native cases and 87 separate workflow records, with 0 native quality failures and no blocking policy rules. Expected abstained, invalid, unavailable and controlled-failure results are not software failures. Evidence: `core`, `core-policy`.

This review does not close the issue, certify deployment, prove identifying assumptions, or authorize stopping, treatment assignment or rollout. Capability classifications describe bounded engineering support, not scientific validity for arbitrary data. Evidence: `issues`, `workflow-doc`.


## Review scope and methodology

Every Phase 4 family is inventoried separately, including contracts, validation, descriptive statistics, randomized, observational, advanced, business, API/workflow and reliability infrastructure. Classifications combine source contracts, actual verification, policy, privacy, CI and limitations. The JSON is authoritative; Markdown is rendered from it. Evidence: `core`, `phase3`, `ci`, `registry`.

The base commit is the merge of prerequisite #109. Prior milestone issues are closed, but current implementation and fresh executions—not issue closure—support this review. The checked-in schema-1 baseline and historical offline Phase 3 diagnostic were not reused as current success evidence. Evidence: `issues`, `ci`, `core`, `phase3`.


## Environment and versions

Core and optional environments have separate Python and dependency identities recorded in environment evidence. Core lacks EconML, DoWhy and statsmodels; optional Python 3.13 provides EconML 0.17.0 and DoWhy 0.14. The existing lock was reused without dependency changes. Evidence: `environment`.

DATABASE_URL was initially unset. The existing disposable pgvector verification container was started and its credentials were passed only to subprocesses; strict local database verification then executed. No credentials or raw datasets are copied into the review. Evidence: `phase3`, `command-phase3-strict`.


## Randomized inference findings

Fixed-horizon continuous estimates use Welch uncertainty; binary estimates use pooled-null testing and unpooled Wald intervals. Two-sided treatment-minus-control semantics, sparse samples, constant arms and undefined relative lift have explicit cases. CUPED uses one declared pre-treatment covariate, pooled theta and the same retained population for variance comparisons. Evidence: `doc-fixed_horizon`, `doc-cuped`, `native-randomized_continuous`, `native-randomized_binary`, `native-cuped`.

Sequential inference uses registered fingerprinted looks and O’Brien-Fleming-shaped weighted Bonferroni spending. It is not the canonical joint-normal boundary and does not produce a sequential effect interval. Bayesian inference uses explicit conjugate priors and deterministic quadrature; credible intervals, superiority and explicitly declared ROPE are not frequentist p-values. Evidence: `doc-sequential`, `doc-bayesian`, `native-sequential`, `native-bayesian_binary`, `native-bayesian_continuous`.


## Observational causal findings

Causal contracts require explicit estimands, variable roles, pre-treatment timing, adjustment sets and assumptions. DiD is balanced 2x2 panel ATT with stable adoption and clustered CR1 uncertainty; pretrend non-rejection does not establish parallel trends. Propensity scores diagnose measured-covariate overlap and balance, never treatment effects. Evidence: `assumptions`, `doc-did`, `doc-propensity_diagnostics`, `native-causal_identification`.

IPW ATE and ATT have distinct targets and weight formulas, recorded stabilization/clipping and downstream overlap/ESS/balance gates. Their uncertainty conditions on fitted scores and can understate score-estimation uncertainty; both remain ADVISORY for causal inference rather than receiving an unqualified production label. Evidence: `doc-ipw_ate`, `native-ipw_ate`, `native-ipw_att`.


## Advanced causal findings

DML uses deterministic stable-ID folds, fresh fold-specific nuisance fits, held-out predictions and the partially linear orthogonal score. Residual degeneracy abstains. HTE is discrete subgroup ATE with registered pre-treatment modifiers, subgroup overlap, direct contrasts and multiplicity context—not personalized CATE. Evidence: `doc-dml`, `test-test_dml_crossfit`, `doc-hte`, `native-repository_dml`, `native-repository_hte`.

The required optional run exercises real adapters plus controlled absence/broken states. EconML supports exactly the declared LinearDML and LinearDRLearner paths. DoWhy supports graph-conditional identification, one interval-free regression handoff and three bounded refuters; passing a refuter is not proof of causality. Evidence: `optional`, `optional-tests`, `doc-econml_adapters`, `doc-dowhy_refutation`.


## Business-impact findings

Explicit sourced population, exposure/adoption, horizon, conversion, costs, units and applicable currency are required. Dimensional checks and source eligibility run before arithmetic. Negative scenarios and bands crossing zero remain valid; no midpoint, financial input or rollout recommendation is invented. Evidence: `doc-business_impact`, `test-test_impact_service`, `test-test_impact_inputs`, `core`.

Selected HTE subgroup scenarios require the corresponding population; sequential and DoWhy sources without eligible effect intervals refuse. Statistical bands remain distinct from operational scenario ranges and assumptions. Evidence: `test-test_impact_integration`, `test-test_impact_sources`, `doc-business_impact`.


## Workflow integration findings

Explicit registry routing calls AnalysisService and native methods. Authoritative protected statistical evidence survives the real graph and POST /ask serialization; mock presentation cannot replace effects, intervals, priors, assumptions or business impact. Human approval and old request behavior remain covered. Evidence: `registry`, `integrity`, `test-test_phase4_workflow_execution`, `test-test_phase4_workflow_references`, `phase3`.


## No-fabrication, uncertainty and abstention audit

All 36 declared workflow corruption scenarios were detected (36 detections). They cover method evidence, intervals/p-values, posterior semantics, plan integrity, timing, weighting, folds, subgroup claims, business inputs and routing. Native conformance adds malformed/foreign/nonfinite-output cases; Phase 3 separately records zero critical fabrication/approval contradictions. Evidence: `core`, `injections`, `phase3`, `test-test_phase4_workflow_injections`.

Insufficient randomized sample, constant CUPED covariate, invalid sequential plan/prior, post-treatment adjustments, no overlap/low ESS, degenerate DML, sparse HTE, absent adapters and missing business provenance have typed refusal evidence. Call-spy positive controls verify that prohibited downstream DML/IPW/business execution does not occur. Identification/propensity/refuter paths do not fabricate effect uncertainty. Evidence: `core`, `optional`, `test-test_phase4_workflow_gating`, `test-test_impact_sources`.


## Determinism and third-party isolation

Native fixtures include repeatability checks; workflow replays preserve estimates, diagnostics, seeds and configuration/plan/fold fingerprints while allowing generated trace IDs and durations to differ. Optional seeded paths are verified in one locked runtime. This establishes bounded numerical reproducibility, not bitwise equality across BLAS, operating systems or library versions. Evidence: `core`, `optional`, `test-test_advanced_conformance_contracts`, `test-test_phase4_complete_artifacts`.

Public/domain objects remain ExperimentOS-owned. Conformance rejects external objects, malformed inference and unsafe errors; third-party package names and scalar version provenance are permitted. Evidence: `optional-tests`, `test-test_advanced_conformance_privacy`, `test-test_econml_contracts`, `test-test_dowhy_contracts`.


## Evaluation and quality-policy findings

The centralized policy reports no blocking rules in core or optional scope. Advisory rules remain visible for case/performance concerns and small capability inventories. Optional scope does not satisfy complete coverage; missing/forged inventories and disabled corruption detection fail closed. Negative effects, inconclusive science or negative impact are not quality defects. Evidence: `core-policy`, `optional-policy`, `test-test_phase4_workflow_policy`, `test-test_phase4_native_policy_integrity`.

Major blockers include numerical-reference failures, fabricated or mutated evidence, missing required uncertainty/assumptions/provenance, fatal diagnostic bypass, post-treatment leakage, sequential plan violations, DML leakage, invalid HTE modifiers, installed-broken adapters, private telemetry, nonfinite outputs and backward-compatibility regressions. Existing policy—not this report—owns numerical thresholds. Evidence: `policy`, `injections`, `test-test_phase4_workflow_policy`.


## Observability and privacy findings

Executed request traces link ask_request → workflow → analysis → validation/estimator, applicable business impact and response serialization. Required parent links and actual OpenTelemetry in-memory export are tested. Policy findings correlate by safe case/method/rule identities; policy is not falsely placed inside an already-finished request span. Evidence: `test-test_phase4_workflow_telemetry`, `workflow-doc`, `core-tests`.

Recursive privacy fixtures cover raw outcomes, treatment/covariates, unit IDs, propensity/weights, nuisance predictions/residuals, row-level CATE, posterior samples, graphs, business rows and credentials. JSON, Markdown and safe summaries are checked, including injected values under otherwise allowed keys. These are bounded tests, not a universal secret detector. Evidence: `privacy`, `test-test_phase4_complete_artifacts`, `test-test_advanced_conformance_privacy`, `core-tests`.

Internal tracing is authoritative; LangSmith, Phoenix and OpenTelemetry providers are tested with dry-run/in-memory behavior and failure isolation. No hosted telemetry service was contacted or certified. Evidence: `phase3`, `core-tests`.


## CI findings

Current-base CI run 35952089560 completed successfully for commit 9bfa1ebd20f0ccc588d09e375f36ea60f9b85ec5, including advanced-causal-optional, offline-eval-smoke, integration-db and ai-quality-gate. This is base-commit CI evidence; the local review diff has not been pushed or run in GitHub CI. Evidence: `ci`.

The YAML uses the canonical complete command and separate required optional scope, fake/mock providers and fixed seeds; uploads run on failure, summaries are concise, and centralized policy thresholds are not duplicated in YAML. Phase 3 and PostgreSQL jobs remain present. Evidence: `ci-config`, `test-test_phase4_backward_compatibility`, `policy`.


## Backward-compatibility and database findings

Fresh core verification: 2213 passed, 45 skipped; skip identities/reasons are preserved. Strict Phase 3 verification executed 38 command stages, including full database-enabled tests, targeted database tests, migrations/repeated ingestion and the full AI quality gate. Exact stage results are in the command matrix and portable evidence. Evidence: `core-tests`, `phase3`.

Locally executed database results supersede the initial unset-DATABASE_URL limitation. The canonical Phase 4 compatibility matrix still correctly marks database and vendor SDK checks as external to that command; separate executed suites supply the missing evidence. Old /ask, RAG retrieval/citations, agent_workflow default, legacy_rag, planner/approval, prompt registry/regression, factuality and optional providers remain verified within offline scope. Evidence: `phase3`, `test-test_phase4_backward_compatibility`, `core`.


## Optional dependency findings

The optional run has 38 native cases and 10 workflow records. Installed-adapter tests passed 169 cases with no skips. Controlled unavailable and failed execution records are expected dependency-state tests, not silently successful numerical estimates. Evidence: `optional`, `optional-tests`.

Core execution proves optional absence does not prevent native DML/HTE or API imports. Installed-but-broken cases surface real normalized failures, with no native fallback; required-optional CLI absence blocks. Evidence: `core`, `optional`, `test-test_advanced_dependency_states`, `test-test_phase4_workflow_optional`.


## Context7 evidence

EconML consultation is recorded in committed verification documentation and PR #154. DoWhy consultation is recorded in its committed verification document. The searched tracked documentation and recent merged PR descriptions do not establish separate historical consultation for every SciPy/scikit-learn/statsmodels integration; this remains an explicit process-evidence gap. A fresh query would not prove historical consultation. Evidence: `context7`, `context7-econml`, `context7-dowhy`.


## Documentation corrections

The README now replaces its stale foundations-only status with bounded implemented scope and links this review. The baseline guide now acknowledges complete-scope business/workflow coverage. The EconML guide now distinguishes absent from installed-but-unimportable dependencies and links the conformance suite that already exists. Historical verification notes remain historical evidence rather than claims about current support. Evidence: `doc-statistical_baseline`, `doc-econml_adapters`, `readme`, `review-guide`.


## Final verification of the review changes

The final full database-enabled suite, after the report validation fixes, passed 2236 tests with 36 optional-runtime skips and 0 failures. The separate installed-adapter run supplies optional coverage. Report-specific tests reject stale evidence, contradictory command claims and stale Markdown; key order cannot change rendering. Evidence: `final-tests`, `report-tests`, `optional-tests`, `review-validator`.


## Findings and follow-ups

Blocking: 0; advisory: 5; gaps: 1.

### P4-R110-A01 — ADVISORY / medium

Capability: did/ipw/hte. Observational assumptions and finite-sample uncertainty limits remain; IPW conditions on fitted scores and DiD few-cluster warnings do not establish nominal coverage.

Impact: These methods remain advisory within their documented causal scope.

Follow-up: Require study-specific assumption review and retain uncertainty limitations before interpreting results.

Required before close: False. Evidence: `doc-did`, `doc-ipw_ate`, `doc-hte`.

### P4-R110-A02 — ADVISORY / medium

Capability: sequential/dowhy/business_impact. Sequential look-level and DoWhy interval-free effects cannot support eligible business-impact intervals.

Impact: Bounded refusals are correct; no general effect-uncertainty or business projection claim is made for those paths.

Follow-up: Keep API/documentation exclusions explicit; any future uncertainty extension needs a separate scoped issue.

Required before close: False. Evidence: `doc-sequential`, `doc-dowhy_estimation`, `doc-business_impact`.

### P4-R110-A03 — ADVISORY / low

Capability: quality_gates. Case/performance and minimum capability-count advisories remain in the existing policy; successful gates do not remove them.

Impact: No blocking software invariant failed. Finite fixtures cannot establish universal coverage.

Follow-up: Retain case-level advisories and expand references only when supporting additional scope.

Required before close: False. Evidence: `core-policy`, `optional-policy`.

### P4-R110-A04 — ADVISORY / low

Capability: optional_adapters/observability. Optional adapters were tested on one Python 3.13 Linux runtime; hosted vendor services and deployment scaling are outside this audit. Upstream deprecation warnings remain.

Impact: No cross-platform bitwise or production-service certification.

Follow-up: Reverify supported runtime changes and use a separate deployment review for hosted services.

Required before close: False. Evidence: `environment`, `optional-tests`, `phase3`.

### P4-R110-G01 — GAP / medium

Capability: historical_context7. Historical consultation for every version-sensitive integration is not established; EconML/DoWhy records are present.

Impact: A process-provenance gap, not evidence of a numerical defect; disclosed here and not treated as proof that consultation never happened.

Follow-up: Locate original implementation PR/comments or records for SciPy, scikit-learn and statsmodels; do not backdate new consultation.

Required before close: False. Evidence: `context7`, `context7-econml`, `context7-dowhy`.

### P4-R110-A05 — ADVISORY / low

Capability: execution_environment. Initial sandbox core/optional/test attempts stalled and were interrupted; reruns outside the sandbox completed. One optional test invocation named a nonexistent file, then was corrected.

Impact: Interrupted/invalid invocations are preserved as attempts and do not count as verification passes. Required successful reruns and the full strict gate supply evidence.

Follow-up: Use the recorded successful commands and offline provider settings for reproduction.

Required before close: False. Evidence: `command-phase4-core`, `command-phase4-optional`, `command-tests-core`, `command-tests-optional`, `command-phase4-core-retry`, `command-phase4-optional-retry`, `command-tests-optional-corrected`.

## Evidence index

Paths are relative to the repository root. SHA-256 digests and exact JSON Pointer values are in the authoritative JSON. Runtime artifacts remain local; portable snapshots are committed.

- `assumptions`: `packages/experiments/analysis/causal/assumptions.py`
- `ci`: `reports/phase4/reliability_evidence.json` → `/ci`
- `ci-config`: `.github/workflows/ci.yml`
- `command-format`: `reports/phase4/reliability_evidence.json` → `/commands/format`
- `command-lint`: `reports/phase4/reliability_evidence.json` → `/commands/lint`
- `command-mypy`: `reports/phase4/reliability_evidence.json` → `/commands/mypy`
- `command-phase3-strict`: `reports/phase4/reliability_evidence.json` → `/commands/phase3-strict`
- `command-phase4-core`: `reports/phase4/reliability_evidence.json` → `/commands/phase4-core`
- `command-phase4-core-retry`: `reports/phase4/reliability_evidence.json` → `/commands/phase4-core-retry`
- `command-phase4-optional`: `reports/phase4/reliability_evidence.json` → `/commands/phase4-optional`
- `command-phase4-optional-retry`: `reports/phase4/reliability_evidence.json` → `/commands/phase4-optional-retry`
- `command-report-tests`: `reports/phase4/reliability_evidence.json` → `/commands/report-tests`
- `command-tests-core`: `reports/phase4/reliability_evidence.json` → `/commands/tests-core`
- `command-tests-core-retry`: `reports/phase4/reliability_evidence.json` → `/commands/tests-core-retry`
- `command-tests-final`: `reports/phase4/reliability_evidence.json` → `/commands/tests-final`
- `command-tests-optional`: `reports/phase4/reliability_evidence.json` → `/commands/tests-optional`
- `command-tests-optional-corrected`: `reports/phase4/reliability_evidence.json` → `/commands/tests-optional-corrected`
- `context7`: `reports/phase4/reliability_evidence.json` → `/context7`
- `context7-dowhy`: `docs/phase4/dowhy_adapters_verification.md`
- `context7-econml`: `docs/phase4/econml_adapters_verification.md`
- `core`: `reports/phase4/reliability_evidence.json` → `/runs/core/summary`
- `core-policy`: `reports/phase4/reliability_evidence.json` → `/runs/core/policy`
- `core-tests`: `reports/phase4/reliability_evidence.json` → `/tests/core`
- `doc-abstention_propagation`: `docs/phase4/workflow_analysis.md`
- `doc-advanced_conformance`: `docs/phase4/advanced_causal_conformance.md`
- `doc-analysis_service`: `docs/phase4/workflow_analysis.md`
- `doc-api_integration`: `docs/phase4/workflow_analysis.md`
- `doc-bayesian`: `docs/phase4/bayesian_ab_testing.md`
- `doc-business_impact`: `docs/phase4/business_impact_scenarios.md`
- `doc-causal_identification`: `docs/phase4/causal_identification_contracts.md`
- `doc-cuped`: `docs/phase4/cuped_covariate_adjustment.md`
- `doc-descriptive_statistics`: `docs/phase4/descriptive_statistics.md`
- `doc-did`: `docs/phase4/difference_in_differences.md`
- `doc-dml`: `docs/phase4/double_machine_learning.md`
- `doc-dowhy_estimation`: `docs/phase4/dowhy_adapters.md`
- `doc-dowhy_identification`: `docs/phase4/dowhy_adapters.md`
- `doc-dowhy_refutation`: `docs/phase4/dowhy_adapters.md`
- `doc-econml_adapters`: `docs/phase4/econml_adapters.md`
- `doc-eligibility_validation`: `docs/phase4/statistical_input_validation.md`
- `doc-end_to_end_quality_gate`: `docs/phase4/end_to_end_causal_quality_gates.md`
- `doc-fixed_horizon`: `docs/phase4/unadjusted_randomized_analysis.md`
- `doc-hte`: `docs/phase4/heterogeneous_treatment_effects.md`
- `doc-ipw_ate`: `docs/phase4/ipw_treatment_effects.md`
- `doc-ipw_att`: `docs/phase4/ipw_treatment_effects.md`
- `doc-observational_reliability`: `docs/phase4/observational_causal_reliability.md`
- `doc-propensity_diagnostics`: `docs/phase4/propensity_score_diagnostics.md`
- `doc-randomized_reliability`: `docs/phase4/statistical_reliability_baseline.md`
- `doc-sequential`: `docs/phase4/sequential_testing.md`
- `doc-statistical_baseline`: `docs/phase4/statistical_reliability_baseline.md`
- `doc-statistical_contracts`: `docs/phase4/statistical_analysis_contracts.md`
- `doc-structured_artifacts`: `docs/phase4/workflow_analysis.md`
- `doc-unsupported_extensions`: `docs/phase4/workflow_analysis.md`
- `doc-workflow_integration`: `docs/phase4/workflow_analysis.md`
- `environment`: `reports/phase4/reliability_evidence.json` → `/environment`
- `final-tests`: `reports/phase4/reliability_evidence.json` → `/tests/final`
- `injections`: `packages/evals/statistical/workflow/injections.py`
- `integrity`: `packages/experiments/analysis/orchestration/integrity.py`
- `issues`: `reports/phase4/reliability_evidence.json` → `/issues`
- `native-bayesian_binary`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/bayesian_binary`
- `native-bayesian_continuous`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/bayesian_continuous`
- `native-causal_identification`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/causal_identification`
- `native-cuped`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/cuped`
- `native-descriptive_statistics`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/descriptive_statistics`
- `native-difference_in_differences`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/difference_in_differences`
- `native-dowhy_common_cause`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/dowhy_common_cause`
- `native-dowhy_estimation`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/dowhy_estimation`
- `native-dowhy_identification`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/dowhy_identification`
- `native-dowhy_placebo`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/dowhy_placebo`
- `native-dowhy_subset`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/dowhy_subset`
- `native-econml_dml`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/econml_dml`
- `native-econml_hte`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/econml_hte`
- `native-eligibility_validation`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/eligibility_validation`
- `native-ipw_ate`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/ipw_ate`
- `native-ipw_att`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/ipw_att`
- `native-observational_coverage`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/observational_coverage`
- `native-propensity_score`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/propensity_score`
- `native-randomized_binary`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/randomized_binary`
- `native-randomized_continuous`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/randomized_continuous`
- `native-repository_dml`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/repository_dml`
- `native-repository_hte`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/repository_hte`
- `native-sequential`: `reports/phase4/reliability_evidence.json` → `/runs/core/capabilities/sequential`
- `network-guard`: `tests/conftest.py`
- `optional`: `reports/phase4/reliability_evidence.json` → `/runs/optional/summary`
- `optional-policy`: `reports/phase4/reliability_evidence.json` → `/runs/optional/policy`
- `optional-tests`: `reports/phase4/reliability_evidence.json` → `/tests/optional`
- `phase3`: `reports/phase4/reliability_evidence.json` → `/phase3`
- `phase3-ci_report.build`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/ci_report.build`
- `phase3-ci_report.render`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/ci_report.render`
- `phase3-ci_report.validate`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/ci_report.validate`
- `phase3-config.lock`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/config.lock`
- `phase3-database.ingest.1.exp-001-payment-recommendation`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/database.ingest.1.exp-001-payment-recommendation`
- `phase3-database.ingest.1.exp-002-hotel-image-quality`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/database.ingest.1.exp-002-hotel-image-quality`
- `phase3-database.ingest.1.exp-003-search-ranking`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/database.ingest.1.exp-003-search-ranking`
- `phase3-database.ingest.1.exp-004-checkout-ux`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/database.ingest.1.exp-004-checkout-ux`
- `phase3-database.ingest.1.exp-005-pricing`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/database.ingest.1.exp-005-pricing`
- `phase3-database.ingest.1.exp-006-loyalty`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/database.ingest.1.exp-006-loyalty`
- `phase3-database.ingest.1.exp-007-crm-notifications`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/database.ingest.1.exp-007-crm-notifications`
- `phase3-database.ingest.1.exp-008-recommendation-systems`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/database.ingest.1.exp-008-recommendation-systems`
- `phase3-database.ingest.1.exp-009-search-filters`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/database.ingest.1.exp-009-search-filters`
- `phase3-database.ingest.1.exp-010-premium-subscriptions`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/database.ingest.1.exp-010-premium-subscriptions`
- `phase3-database.ingest.2.exp-001-payment-recommendation`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/database.ingest.2.exp-001-payment-recommendation`
- `phase3-database.ingest.2.exp-002-hotel-image-quality`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/database.ingest.2.exp-002-hotel-image-quality`
- `phase3-database.ingest.2.exp-003-search-ranking`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/database.ingest.2.exp-003-search-ranking`
- `phase3-database.ingest.2.exp-004-checkout-ux`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/database.ingest.2.exp-004-checkout-ux`
- `phase3-database.ingest.2.exp-005-pricing`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/database.ingest.2.exp-005-pricing`
- `phase3-database.ingest.2.exp-006-loyalty`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/database.ingest.2.exp-006-loyalty`
- `phase3-database.ingest.2.exp-007-crm-notifications`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/database.ingest.2.exp-007-crm-notifications`
- `phase3-database.ingest.2.exp-008-recommendation-systems`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/database.ingest.2.exp-008-recommendation-systems`
- `phase3-database.ingest.2.exp-009-search-filters`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/database.ingest.2.exp-009-search-filters`
- `phase3-database.ingest.2.exp-010-premium-subscriptions`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/database.ingest.2.exp-010-premium-subscriptions`
- `phase3-database.migrate`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/database.migrate`
- `phase3-format.check`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/format.check`
- `phase3-lint`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/lint`
- `phase3-observability.dry_run.langsmith`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/observability.dry_run.langsmith`
- `phase3-observability.dry_run.opentelemetry`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/observability.dry_run.opentelemetry`
- `phase3-observability.dry_run.phoenix`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/observability.dry_run.phoenix`
- `phase3-observability.status`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/observability.status`
- `phase3-observability.validate`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/observability.validate`
- `phase3-policy`: `reports/phase4/reliability_evidence.json` → `/phase3/policy`
- `phase3-prompt.experiment.validate`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/prompt.experiment.validate`
- `phase3-prompt.registry.validate`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/prompt.registry.validate`
- `phase3-quality_gate.full`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/quality_gate.full`
- `phase3-tests.database`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/tests.database`
- `phase3-tests.focused`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/tests.focused`
- `phase3-tests.full`: `reports/phase4/reliability_evidence.json` → `/phase3/commands/tests.full`
- `policy`: `config/evaluation/quality_policy.yaml`
- `privacy`: `packages/evals/statistical/workflow/telemetry.py`
- `readme`: `README.md`
- `registry`: `packages/experiments/analysis/orchestration/registry.py`
- `report-tests`: `reports/phase4/reliability_evidence.json` → `/tests/report`
- `review-guide`: `docs/phase4/reliability_review.md`
- `review-validator`: `packages/evals/phase4_review.py`
- `runtime-core`: `artifacts/issue110/core/statistical_baseline.json`
- `runtime-optional`: `artifacts/issue110/optional/statistical_baseline.json`
- `source-abstention_propagation`: `packages/experiments/analysis/orchestration/business.py`
- `source-advanced_conformance`: `packages/evals/statistical/evaluator.py`
- `source-analysis_service`: `packages/experiments/analysis/orchestration/service.py`
- `source-api_integration`: `apps/api/main.py`
- `source-bayesian`: `packages/experiments/analysis/randomized/bayesian/service.py`
- `source-business_impact`: `packages/experiments/analysis/impact/service.py`
- `source-causal_identification`: `packages/experiments/analysis/causal/service.py`
- `source-cuped`: `packages/experiments/analysis/randomized/cuped/service.py`
- `source-descriptive_statistics`: `packages/experiments/analysis/randomized/descriptive.py`
- `source-did`: `packages/experiments/analysis/causal/did/service.py`
- `source-dml`: `packages/experiments/analysis/causal/dml/service.py`
- `source-dowhy_estimation`: `packages/experiments/analysis/causal/dowhy/adapter.py`
- `source-dowhy_identification`: `packages/experiments/analysis/causal/dowhy/adapter.py`
- `source-dowhy_refutation`: `packages/experiments/analysis/causal/dowhy/adapter.py`
- `source-econml_adapters`: `packages/experiments/analysis/causal/econml/dml.py`
- `source-eligibility_validation`: `packages/experiments/analysis/validation/service.py`
- `source-end_to_end_quality_gate`: `packages/evals/statistical/evaluator.py`
- `source-fixed_horizon`: `packages/experiments/analysis/randomized/service.py`
- `source-hte`: `packages/experiments/analysis/causal/hte/service.py`
- `source-ipw_ate`: `packages/experiments/analysis/causal/ipw/service.py`
- `source-ipw_att`: `packages/experiments/analysis/causal/ipw/service.py`
- `source-observational_reliability`: `packages/evals/statistical/evaluator.py`
- `source-propensity_diagnostics`: `packages/experiments/analysis/causal/propensity/service.py`
- `source-randomized_reliability`: `packages/evals/statistical/evaluator.py`
- `source-sequential`: `packages/experiments/analysis/randomized/sequential/service.py`
- `source-statistical_baseline`: `packages/evals/statistical/evaluator.py`
- `source-statistical_contracts`: `packages/experiments/analysis/results.py`
- `source-structured_artifacts`: `packages/experiments/analysis/orchestration/integrity.py`
- `source-unsupported_extensions`: `packages/experiments/analysis/orchestration/registry.py`
- `source-workflow_integration`: `packages/agents/workflow.py`
- `test-test_advanced_conformance_artifacts`: `tests/test_advanced_conformance_artifacts.py`
- `test-test_advanced_conformance_cases`: `tests/test_advanced_conformance_cases.py`
- `test-test_advanced_conformance_contracts`: `tests/test_advanced_conformance_contracts.py`
- `test-test_advanced_conformance_integration`: `tests/test_advanced_conformance_integration.py`
- `test-test_advanced_conformance_mutations`: `tests/test_advanced_conformance_mutations.py`
- `test-test_advanced_conformance_privacy`: `tests/test_advanced_conformance_privacy.py`
- `test-test_advanced_dependency_states`: `tests/test_advanced_dependency_states.py`
- `test-test_agent_workflow`: `tests/test_agent_workflow.py`
- `test-test_analysis_artifacts`: `tests/test_analysis_artifacts.py`
- `test-test_analysis_business_gating`: `tests/test_analysis_business_gating.py`
- `test-test_analysis_contract_documentation`: `tests/test_analysis_contract_documentation.py`
- `test-test_analysis_contract_serialization`: `tests/test_analysis_contract_serialization.py`
- `test-test_analysis_datasets`: `tests/test_analysis_datasets.py`
- `test-test_analysis_dispatch`: `tests/test_analysis_dispatch.py`
- `test-test_analysis_dispatch_causal`: `tests/test_analysis_dispatch_causal.py`
- `test-test_analysis_dispatch_optional`: `tests/test_analysis_dispatch_optional.py`
- `test-test_analysis_dispatch_randomized`: `tests/test_analysis_dispatch_randomized.py`
- `test-test_analysis_e2e`: `tests/test_analysis_e2e.py`
- `test-test_analysis_envelope`: `tests/test_analysis_envelope.py`
- `test-test_analysis_estimates`: `tests/test_analysis_estimates.py`
- `test-test_analysis_integrity`: `tests/test_analysis_integrity.py`
- `test-test_analysis_minimal_dependencies`: `tests/test_analysis_minimal_dependencies.py`
- `test-test_analysis_orchestration_requests`: `tests/test_analysis_orchestration_requests.py`
- `test-test_analysis_policy`: `tests/test_analysis_policy.py`
- `test-test_analysis_rendering`: `tests/test_analysis_rendering.py`
- `test-test_analysis_requests`: `tests/test_analysis_requests.py`
- `test-test_analysis_results`: `tests/test_analysis_results.py`
- `test-test_analysis_review_regressions`: `tests/test_analysis_review_regressions.py`
- `test-test_analysis_service`: `tests/test_analysis_service.py`
- `test-test_analysis_validation_contracts`: `tests/test_analysis_validation_contracts.py`
- `test-test_analysis_validation_data_rules`: `tests/test_analysis_validation_data_rules.py`
- `test-test_analysis_validation_design_rules`: `tests/test_analysis_validation_design_rules.py`
- `test-test_analysis_validation_documentation`: `tests/test_analysis_validation_documentation.py`
- `test-test_analysis_validation_evaluation`: `tests/test_analysis_validation_evaluation.py`
- `test-test_analysis_validation_observability`: `tests/test_analysis_validation_observability.py`
- `test-test_analysis_validation_policy`: `tests/test_analysis_validation_policy.py`
- `test-test_analysis_validation_request_rules`: `tests/test_analysis_validation_request_rules.py`
- `test-test_analysis_validation_service`: `tests/test_analysis_validation_service.py`
- `test-test_analysis_workflow_documentation`: `tests/test_analysis_workflow_documentation.py`
- `test-test_analysis_workflow_observability`: `tests/test_analysis_workflow_observability.py`
- `test-test_api_analysis`: `tests/test_api_analysis.py`
- `test-test_api_ask`: `tests/test_api_ask.py`
- `test-test_bayesian_binary`: `tests/test_bayesian_binary.py`
- `test-test_bayesian_continuous`: `tests/test_bayesian_continuous.py`
- `test-test_bayesian_contracts`: `tests/test_bayesian_contracts.py`
- `test-test_bayesian_exports`: `tests/test_bayesian_exports.py`
- `test-test_bayesian_numerics`: `tests/test_bayesian_numerics.py`
- `test-test_bayesian_observability`: `tests/test_bayesian_observability.py`
- `test-test_bayesian_service`: `tests/test_bayesian_service.py`
- `test-test_business_impact_contracts`: `tests/test_business_impact_contracts.py`
- `test-test_causal_identification_contracts`: `tests/test_causal_identification_contracts.py`
- `test-test_causal_identification_documentation`: `tests/test_causal_identification_documentation.py`
- `test-test_causal_identification_models`: `tests/test_causal_identification_models.py`
- `test-test_causal_identification_observability`: `tests/test_causal_identification_observability.py`
- `test-test_causal_identification_serialization`: `tests/test_causal_identification_serialization.py`
- `test-test_causal_identification_service`: `tests/test_causal_identification_service.py`
- `test-test_cuped_contracts`: `tests/test_cuped_contracts.py`
- `test-test_cuped_exports`: `tests/test_cuped_exports.py`
- `test-test_cuped_numerics`: `tests/test_cuped_numerics.py`
- `test-test_cuped_observability`: `tests/test_cuped_observability.py`
- `test-test_cuped_reference_cases`: `tests/test_cuped_reference_cases.py`
- `test-test_cuped_service`: `tests/test_cuped_service.py`
- `test-test_descriptive_statistics_contracts`: `tests/test_descriptive_statistics_contracts.py`
- `test-test_descriptive_statistics_diagnostics`: `tests/test_descriptive_statistics_diagnostics.py`
- `test-test_descriptive_statistics_golden_cases`: `tests/test_descriptive_statistics_golden_cases.py`
- `test-test_descriptive_statistics_numeric`: `tests/test_descriptive_statistics_numeric.py`
- `test-test_descriptive_statistics_observability`: `tests/test_descriptive_statistics_observability.py`
- `test-test_descriptive_statistics_service`: `tests/test_descriptive_statistics_service.py`
- `test-test_did_contracts`: `tests/test_did_contracts.py`
- `test-test_did_documentation`: `tests/test_did_documentation.py`
- `test-test_did_estimation`: `tests/test_did_estimation.py`
- `test-test_did_evaluation`: `tests/test_did_evaluation.py`
- `test-test_did_inference`: `tests/test_did_inference.py`
- `test-test_did_observability`: `tests/test_did_observability.py`
- `test-test_did_pretrends`: `tests/test_did_pretrends.py`
- `test-test_did_serialization`: `tests/test_did_serialization.py`
- `test-test_did_service`: `tests/test_did_service.py`
- `test-test_did_validation`: `tests/test_did_validation.py`
- `test-test_dml_adapter`: `tests/test_dml_adapter.py`
- `test-test_dml_crossfit`: `tests/test_dml_crossfit.py`
- `test-test_dml_documentation`: `tests/test_dml_documentation.py`
- `test-test_dml_folds`: `tests/test_dml_folds.py`
- `test-test_dml_numerics`: `tests/test_dml_numerics.py`
- `test-test_dml_observability`: `tests/test_dml_observability.py`
- `test-test_dml_protocols`: `tests/test_dml_protocols.py`
- `test-test_dml_public_contracts`: `tests/test_dml_public_contracts.py`
- `test-test_dml_service`: `tests/test_dml_service.py`
- `test-test_dml_uncertainty`: `tests/test_dml_uncertainty.py`
- `test-test_dml_validation`: `tests/test_dml_validation.py`
- `test-test_dowhy_contracts`: `tests/test_dowhy_contracts.py`
- `test-test_dowhy_dependency`: `tests/test_dowhy_dependency.py`
- `test-test_dowhy_documentation`: `tests/test_dowhy_documentation.py`
- `test-test_dowhy_estimation`: `tests/test_dowhy_estimation.py`
- `test-test_dowhy_graph`: `tests/test_dowhy_graph.py`
- `test-test_dowhy_identification`: `tests/test_dowhy_identification.py`
- `test-test_dowhy_observability`: `tests/test_dowhy_observability.py`
- `test-test_dowhy_public_independence`: `tests/test_dowhy_public_independence.py`
- `test-test_dowhy_quality`: `tests/test_dowhy_quality.py`
- `test-test_dowhy_refuters`: `tests/test_dowhy_refuters.py`
- `test-test_econml_contracts`: `tests/test_econml_contracts.py`
- `test-test_econml_dependency`: `tests/test_econml_dependency.py`
- `test-test_econml_dml`: `tests/test_econml_dml.py`
- `test-test_econml_hte`: `tests/test_econml_hte.py`
- `test-test_econml_observability`: `tests/test_econml_observability.py`
- `test-test_econml_quality`: `tests/test_econml_quality.py`
- `test-test_econml_references`: `tests/test_econml_references.py`
- `test-test_econml_safeguards`: `tests/test_econml_safeguards.py`
- `test-test_hte_assignment`: `tests/test_hte_assignment.py`
- `test-test_hte_contracts`: `tests/test_hte_contracts.py`
- `test-test_hte_numerics`: `tests/test_hte_numerics.py`
- `test-test_hte_observability`: `tests/test_hte_observability.py`
- `test-test_hte_overlap`: `tests/test_hte_overlap.py`
- `test-test_hte_provenance`: `tests/test_hte_provenance.py`
- `test-test_hte_public_contracts`: `tests/test_hte_public_contracts.py`
- `test-test_hte_quality`: `tests/test_hte_quality.py`
- `test-test_hte_service`: `tests/test_hte_service.py`
- `test-test_hte_validation`: `tests/test_hte_validation.py`
- `test-test_impact_arithmetic`: `tests/test_impact_arithmetic.py`
- `test-test_impact_inputs`: `tests/test_impact_inputs.py`
- `test-test_impact_integration`: `tests/test_impact_integration.py`
- `test-test_impact_reporting`: `tests/test_impact_reporting.py`
- `test-test_impact_service`: `tests/test_impact_service.py`
- `test-test_impact_sources`: `tests/test_impact_sources.py`
- `test-test_ipw_contracts`: `tests/test_ipw_contracts.py`
- `test-test_ipw_numerics`: `tests/test_ipw_numerics.py`
- `test-test_ipw_observability`: `tests/test_ipw_observability.py`
- `test-test_ipw_safety`: `tests/test_ipw_safety.py`
- `test-test_ipw_serialization`: `tests/test_ipw_serialization.py`
- `test-test_ipw_service`: `tests/test_ipw_service.py`
- `test-test_ipw_uncertainty`: `tests/test_ipw_uncertainty.py`
- `test-test_ipw_weighting_diagnostics`: `tests/test_ipw_weighting_diagnostics.py`
- `test-test_observational_reliability_dataset`: `tests/test_observational_reliability_dataset.py`
- `test-test_observational_reliability_did`: `tests/test_observational_reliability_did.py`
- `test-test_observational_reliability_identification`: `tests/test_observational_reliability_identification.py`
- `test-test_observational_reliability_ipw`: `tests/test_observational_reliability_ipw.py`
- `test-test_observational_reliability_propensity`: `tests/test_observational_reliability_propensity.py`
- `test-test_observational_reliability_simulation`: `tests/test_observational_reliability_simulation.py`
- `test-test_observational_reliability_telemetry`: `tests/test_observational_reliability_telemetry.py`
- `test-test_phase4_backward_compatibility`: `tests/test_phase4_backward_compatibility.py`
- `test-test_phase4_complete_artifacts`: `tests/test_phase4_complete_artifacts.py`
- `test-test_phase4_complete_cli`: `tests/test_phase4_complete_cli.py`
- `test-test_phase4_final_review`: `tests/test_phase4_final_review.py`
- `test-test_phase4_native_policy_integrity`: `tests/test_phase4_native_policy_integrity.py`
- `test-test_phase4_workflow_dataset`: `tests/test_phase4_workflow_dataset.py`
- `test-test_phase4_workflow_execution`: `tests/test_phase4_workflow_execution.py`
- `test-test_phase4_workflow_gating`: `tests/test_phase4_workflow_gating.py`
- `test-test_phase4_workflow_injections`: `tests/test_phase4_workflow_injections.py`
- `test-test_phase4_workflow_optional`: `tests/test_phase4_workflow_optional.py`
- `test-test_phase4_workflow_policy`: `tests/test_phase4_workflow_policy.py`
- `test-test_phase4_workflow_references`: `tests/test_phase4_workflow_references.py`
- `test-test_phase4_workflow_telemetry`: `tests/test_phase4_workflow_telemetry.py`
- `test-test_propensity_adapter`: `tests/test_propensity_adapter.py`
- `test-test_propensity_contracts`: `tests/test_propensity_contracts.py`
- `test-test_propensity_encoding`: `tests/test_propensity_encoding.py`
- `test-test_propensity_exports`: `tests/test_propensity_exports.py`
- `test-test_propensity_numerics`: `tests/test_propensity_numerics.py`
- `test-test_propensity_observability`: `tests/test_propensity_observability.py`
- `test-test_propensity_retention`: `tests/test_propensity_retention.py`
- `test-test_propensity_serialization`: `tests/test_propensity_serialization.py`
- `test-test_propensity_service`: `tests/test_propensity_service.py`
- `test-test_propensity_validation`: `tests/test_propensity_validation.py`
- `test-test_randomized_binary`: `tests/test_randomized_binary.py`
- `test-test_randomized_continuous`: `tests/test_randomized_continuous.py`
- `test-test_randomized_contracts`: `tests/test_randomized_contracts.py`
- `test-test_randomized_inference_reliability_artifacts`: `tests/test_randomized_inference_reliability_artifacts.py`
- `test-test_randomized_inference_reliability_evaluator`: `tests/test_randomized_inference_reliability_evaluator.py`
- `test-test_randomized_inference_reliability_fixtures`: `tests/test_randomized_inference_reliability_fixtures.py`
- `test-test_randomized_inference_reliability_policy`: `tests/test_randomized_inference_reliability_policy.py`
- `test-test_randomized_inference_reliability_telemetry`: `tests/test_randomized_inference_reliability_telemetry.py`
- `test-test_randomized_numerics`: `tests/test_randomized_numerics.py`
- `test-test_randomized_observability`: `tests/test_randomized_observability.py`
- `test-test_randomized_service`: `tests/test_randomized_service.py`
- `test-test_sequential_boundaries`: `tests/test_sequential_boundaries.py`
- `test-test_sequential_exports`: `tests/test_sequential_exports.py`
- `test-test_sequential_observability`: `tests/test_sequential_observability.py`
- `test-test_sequential_plan`: `tests/test_sequential_plan.py`
- `test-test_sequential_reference_cases`: `tests/test_sequential_reference_cases.py`
- `test-test_sequential_service`: `tests/test_sequential_service.py`
- `test-test_statistical_baseline_cli`: `tests/test_statistical_baseline_cli.py`
- `test-test_statistical_baseline_dataset`: `tests/test_statistical_baseline_dataset.py`
- `test-test_statistical_baseline_evaluator`: `tests/test_statistical_baseline_evaluator.py`
- `test-test_statistical_baseline_policy`: `tests/test_statistical_baseline_policy.py`
- `test-test_statistical_baseline_reporting`: `tests/test_statistical_baseline_reporting.py`
- `workflow-cases`: `packages/evals/statistical/workflow/cases.py`
- `workflow-doc`: `docs/phase4/end_to_end_causal_quality_gates.md`

## Final milestone readiness

READY_WITH_ADVISORIES
