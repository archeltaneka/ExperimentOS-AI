import type { Capability } from "@/types/domain";

// Repository implementation status, not runtime availability or results for a record.
// Sources: docs/phase4/workflow_analysis.md and docs/phase4/reliability_review.md.
export const analysisCapabilities: readonly (Capability & { optional?: boolean })[] = [
  { name: "Statistical contracts", phase: 4, status: "completed", detail: "Typed analysis requests, evidence, uncertainty, and refusal states are implemented in the backend." },
  { name: "Analysis eligibility", phase: 4, status: "completed", detail: "The backend validates declared methods and inputs before running an analysis." },
  { name: "Descriptive statistics", phase: 4, status: "completed", detail: "The backend computes eligible arm summaries. Descriptive differences alone do not establish causal effects." },
  { name: "Fixed-horizon randomized analysis", phase: 4, status: "completed", detail: "Implemented for supported continuous and binary outcomes in two independent randomized arms." },
  { name: "CUPED", phase: 4, status: "completed", detail: "Implemented with one pre-treatment continuous covariate and explicit eligibility checks." },
  { name: "Sequential testing", phase: 4, status: "completed", detail: "Implemented for predeclared analysis looks and an explicit error-spending plan. It does not stop experiments automatically." },
  { name: "Bayesian A/B testing", phase: 4, status: "completed", detail: "Implemented for supported binary and continuous outcomes with caller-supplied priors." },
  { name: "Difference-in-Differences", phase: 4, status: "completed", detail: "Implemented within the documented design limits. Parallel-trend assumptions and inference advisories remain the caller’s responsibility." },
  { name: "Propensity-score methods", phase: 4, status: "completed", detail: "Diagnostics and ATE/ATT weighting are implemented. Poor overlap can block analysis; diagnostics alone are not an effect estimate." },
  { name: "Double Machine Learning", phase: 4, status: "completed", detail: "The repository implementation uses explicit inputs, cross-fitting, and validated nuisance-model configuration." },
  { name: "Heterogeneous treatment effects", phase: 4, status: "completed", detail: "Implemented for declared subgroups, with sample-size safeguards and inference advisories." },
  { name: "Business-impact estimation", phase: 4, status: "completed", detail: "Eligible analysis can produce uncertainty-aware scenarios from explicit, sourced business assumptions. Missing inputs cause abstention; scenarios do not authorize rollout." },
  { name: "EconML", phase: 4, status: "completed", optional: true, detail: "Backend adapters are implemented. Execution requires compatible optional dependencies and valid configuration; otherwise the method is unavailable." },
  { name: "DoWhy", phase: 4, status: "completed", optional: true, detail: "Backend identification and refutation adapters are implemented. Execution requires compatible optional dependencies and declared causal assumptions." },
];

export const analysisAvailability = {
  backend: "Statistical and causal methods are implemented in the backend within documented limits. Structured API requests must specify the method, data, and assumptions.",
  interface: "The default web demo shows saved records and answers. Web forms do not run structured statistical or causal analyses, including in live Ask mode.",
  deployment: "Local development is supported. No public deployment has been verified, and no autonomous rollout is authorized.",
};

export const analysisGuideUrl = "https://github.com/archeltaneka/ExperimentOS-AI/blob/main/docs/phase4/workflow_analysis.md";
export const analysisReviewUrl = "https://github.com/archeltaneka/ExperimentOS-AI/blob/main/docs/phase4/reliability_review.md";
