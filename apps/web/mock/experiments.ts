import type { Experiment, ExperimentDetail } from "@/types/domain";

export const paymentRecommendationExperiment: ExperimentDetail = {
  id: "8bb4bf4d-a372-4b6e-93a5-0dd9ad7c8750", name: "Adaptive payment recommendation", status: "completed",
  owner: { id: "owner-ava", name: "Ava Patel", team: "Payments" }, startedAt: "2026-06-03T09:00:00Z",
  primaryMetric: { name: "Payment completion", value: 4.2, unit: "% lift", direction: "increase" },
  decision: { status: "approved", recommendation: "Controlled rollout", rationale: "The primary metric improved with acceptable guardrails." },
  analysisStatus: "completed", businessImpact: "not_estimated", summary: "A deterministic portfolio fixture showing an approved rollout decision.",
  metrics: [{ name: "Payment completion", value: 4.2, unit: "% lift", direction: "increase" }, { name: "Checkout errors", value: -0.3, unit: "% change", direction: "decrease" }],
  capabilities: [{ name: "Descriptive statistics", phase: 4, status: "completed", detail: "Available in fixture." }, { name: "CUPED", phase: 4, status: "planned", detail: "Not implemented." }, { name: "Business-impact estimation", phase: 4, status: "unavailable", detail: "No operational estimate is available." }],
};

export const experimentFixtures: readonly Experiment[] = [
  paymentRecommendationExperiment,
  { id: "7a23d911-c5c8-4dd5-9a29-4a3e06607ab1", name: "Search result explanation", status: "running", owner: { id: "owner-lin", name: "Lin Chen", team: "Search" }, startedAt: "2026-07-20T09:00:00Z", primaryMetric: { name: "Search refinement", value: 1.8, unit: "% lift", direction: "increase" }, decision: { status: "pending", recommendation: "Continue monitoring", rationale: "Collection window is still open." }, analysisStatus: "in-progress", businessImpact: "unavailable" },
  { id: "78e43638-05ca-4de8-a470-5f3c56c3b3de", name: "Loyalty progress nudges", status: "inconclusive", owner: { id: "owner-milo", name: "Milo Singh", team: "Growth" }, startedAt: "2026-05-10T09:00:00Z", primaryMetric: { name: "Repeat purchase", value: 0.2, unit: "% lift", direction: "neutral" }, decision: { status: "pending", recommendation: "Gather more evidence", rationale: "The observed result is inconclusive." }, analysisStatus: "completed", businessImpact: "unavailable" },
  { id: "508d252d-0772-4a56-aa75-2e8f933a2ca1", name: "Hotel image quality", status: "stopped", owner: { id: "owner-noor", name: "Noor Hassan", team: "Marketplace" }, startedAt: "2026-04-12T09:00:00Z", primaryMetric: { name: "Booking conversion", value: -1.1, unit: "% lift", direction: "decrease" }, decision: { status: "rejected", recommendation: "Do not resume", rationale: "Guardrail performance did not support continuation." }, analysisStatus: "completed", businessImpact: "unavailable" },
];
