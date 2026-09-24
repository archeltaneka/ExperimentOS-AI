# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two audiences have equal priority, as confirmed by the project owner:

- Recruiters and technical reviewers assessing the portfolio's engineering depth, evidence, and implementation quality.
- Experimentation practitioners recovering experiment evidence, reviewing grounded answers, and understanding analysis and decision limitations.

## Product Purpose

ExperimentOS AI is an experiment-intelligence workspace that turns experiment artifacts into searchable evidence, grounded answers, and repeatable AI-quality evaluation. It helps people recover the evidence behind an experiment decision and inspect how an answer was produced.

The current delivery is a portfolio-oriented web demonstration with a separately runnable backend. Equal audience priority does not imply production readiness or deployed practitioner workflows.

## Positioning

The repository combines experiment-report retrieval, cited answers, structured agent workflows, and repository-owned evaluation and quality gates. Statistical analysis uses validated services and typed evidence; generated prose must not replace authoritative numerical results.

## Operating Context

- The Next.js application lives in `apps/web`; the FastAPI backend lives in `apps/api`.
- The default web experience uses deterministic fixtures and requires no database, API key, or backend process. Start it with `npm run dev` from `apps/web`.
- The main surfaces are the landing page, Ask Experiment, Experiment Explorer and experiment detail, Evaluation Dashboard, and Roadmap.
- Local live Ask requires deliberate configuration, a running backend, PostgreSQL with pgvector, and an ingested experiment.
- Users inspect experiment reports, citations, retrieved context, evaluation cases, and capability status. Reviewers can also inspect source code and offline evaluation artifacts.

## Capabilities and Constraints

The owner confirmed preserving clearly disclosed demo fixtures, citations and evidence, explicit capability status, and human approval safeguards. The details below capture these boundaries from the repository.

- Disclose fixture-backed data. Demonstration records and evaluation fixtures must not be presented as live telemetry or customer results.
- Backend retrieval, grounded QA, and agent orchestration are implemented. The full Explorer record and Evaluation Dashboard do not have complete backing APIs.
- Phase 4 documents implemented randomized and causal analysis methods and uncertainty-aware business scenarios exposed through optional structured `/ask` requests. These backend capabilities do not imply equivalent frontend controls or public availability.
- Method selection and business inputs must be explicit and validated. Preserve uncertainty, provenance, diagnostics, abstention, and unavailable-method states. The LLM does not calculate statistics or invent business inputs.
- Positive effects do not authorize autonomous rollout. Preserve human approval safeguards and distinguish execution status from quality status.
- Public deployment is not verified in the repository. Authentication, multi-user collaboration, enterprise governance, and public LLM abuse/cost controls are not implemented.
- Some older README and frontend documentation still describe Phase 4 as planned. Consult `docs/phase4/workflow_analysis.md` and the relevant implementation before publishing capability claims; keep backend implementation, UI exposure, and deployment status separate.

## Brand Commitments

The existing product name is **ExperimentOS AI**. Repository messaging emphasizes evidence, source disclosure, and honest capability claims. No additional owner-confirmed voice or visual constraints have been established.

## Evidence on Hand

- `README.md`: product overview, local demonstration instructions, and deployment limitations; some capability summaries conflict with the later Phase 4 section.
- `apps/web/mock/`: deterministic frontend demonstration data.
- `data/synthetic/`: synthetic experiment material, not customer evidence.
- `data/eval/`: repository-owned evaluation cases, including structured workflow examples.
- `docs/phase4/workflow_analysis.md`: supported analysis methods, safeguards, and runnable examples.
- `docs/phase4/reliability_review.md`: documented Phase 4 review evidence and limitations.
- `docs/frontend-data-layer.md`: frontend service and data-source boundaries.
- `docs/portfolio-messaging.md`: portfolio presentation and demonstration guidance.
- `reports/`: curated reference artifacts; these are not proof of current live telemetry or a newly executed verification run.

No customer testimonials, adoption claims, production outcomes, or verified public deployment should be invented. Current UI screenshots are documented as pending capture.

## Product Principles

Derived from the confirmed audience priorities and documented repository constraints:

1. Make evidence useful to practitioners and inspectable by technical reviewers.
2. Keep citations, provenance, uncertainty, and limitations visible where they affect interpretation.
3. Distinguish implemented backend capabilities, demonstrated UI behavior, and deployed functionality.
4. Preserve deterministic validation and human decision authority around generated explanations.

## Open Decisions

- No additional durable requirements beyond the confirmed boundaries were specified.
- No product-specific accessibility standard or additional inclusion requirements have been confirmed.
- Relative priority between the two audiences is settled: both matter equally. Specific practitioner roles and operating environments remain unspecified.
