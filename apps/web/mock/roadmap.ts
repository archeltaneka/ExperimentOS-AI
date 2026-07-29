import type { RoadmapPhase } from "@/types/domain";

export const roadmapFixtures: readonly RoadmapPhase[] = [
  { id: "phase-3", title: "Reliable RAG", status: "completed", description: "Grounded answer evaluation and quality gates.", capabilities: [{ name: "Prompt regression", phase: 3, status: "completed", detail: "Tracked in deterministic fixtures." }] },
  { id: "phase-4", title: "Experiment analysis", status: "in_progress", description: "Descriptive analysis foundation only.", capabilities: [{ name: "Descriptive statistics", phase: 4, status: "completed", detail: "Available." }, { name: "CUPED", phase: 4, status: "planned", detail: "Not implemented." }] },
  { id: "phase-5", title: "Causal research", status: "planned", description: "Future research, not an operational analysis feature.", capabilities: [{ name: "Difference-in-Differences", phase: 5, status: "future-research", detail: "Future research." }, { name: "EconML / DoWhy", phase: 5, status: "unavailable", detail: "Not connected." }] },
];
