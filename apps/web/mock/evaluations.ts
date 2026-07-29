import type { EvaluationHistoryPoint, EvaluationSummary } from "@/types/domain";

export const evaluationFixture: EvaluationSummary = {
  metrics: [{ id: "groundedness", label: "Groundedness", value: 0.94, target: 0.9, status: "pass" }, { id: "citation-coverage", label: "Citation coverage", value: 0.91, target: 0.9, status: "pass" }, { id: "abstention", label: "Safe abstention", value: 0.82, target: 0.9, status: "fail" }],
  promptRegressions: [{ name: "Grounded answer", baseline: 0.93, candidate: 0.94, status: "pass" }, { name: "Abstention behaviour", baseline: 0.9, candidate: 0.82, status: "regression" }],
  qualityGate: { status: "quality_fail", message: "Fixture gate demonstrates an unresolved abstention regression." },
  capabilities: [{ name: "Descriptive statistics", phase: 4, status: "completed", detail: "Available." }, { name: "Sequential testing", phase: 4, status: "planned", detail: "Not implemented." }, { name: "Bayesian A/B testing", phase: 4, status: "future-research", detail: "Research only." }, { name: "Double Machine Learning", phase: 4, status: "unavailable", detail: "Not connected." }],
};
export const evaluationHistoryFixture: readonly EvaluationHistoryPoint[] = [{ date: "2026-06-01", score: 0.88 }, { date: "2026-06-15", score: 0.9 }, { date: "2026-07-01", score: 0.92 }, { date: "2026-07-15", score: 0.91 }];
