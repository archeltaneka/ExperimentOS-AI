import type { CapabilityStatus, RoadmapPhase } from "@/types/domain";

export const githubUrl = "https://github.com/archeltaneka/ExperimentOS-AI";
export const demoUrl = "/ask-experiment";

export const architectureStages: readonly {
  title: string;
  status: CapabilityStatus;
  detail: string;
}[] = [
  { title: "Experiment Repository", status: "completed", detail: "Reports, metrics, and experiment context." },
  { title: "Semantic Retrieval", status: "completed", detail: "pgvector-backed evidence lookup." },
  { title: "RAG Question Answering", status: "completed", detail: "Grounded answers with citations." },
  { title: "Agent Workflow", status: "completed", detail: "LangGraph orchestration with approval." },
  { title: "Statistical Analysis", status: "in-progress", detail: "Contracts, eligibility, and descriptive summaries." },
  { title: "Decision Intelligence", status: "planned", detail: "Evidence-led product decisions; broader reasoning is planned." },
];

export const capabilityGroups: readonly {
  title: string;
  detail: string;
  status: CapabilityStatus;
}[] = [
  { title: "Retrieve evidence", detail: "Find report chunks and experiment context with semantic search.", status: "completed" },
  { title: "Ground answers", detail: "Return traceable answers with citations and retrieved evidence.", status: "completed" },
  { title: "Coordinate reasoning", detail: "Use a deterministic LangGraph workflow for retrieval, risk, decisions, and approval.", status: "completed" },
  { title: "Measure reliability", detail: "Run deterministic evaluation, prompt regression, quality policy, RAGAS, and DeepEval workflows.", status: "completed" },
  { title: "Extend analysis safely", detail: "Keep statistical contracts and eligibility explicit while broader analysis develops.", status: "in-progress" },
];

export const capabilityStatusGroups: readonly {
  title: string;
  status: CapabilityStatus;
  items: readonly string[];
}[] = [
  {
    title: "Completed",
    status: "completed",
    items: [
      "Backend foundation",
      "Retrieval and embeddings",
      "RAG question answering",
      "LangGraph agent workflow",
      "Human approval",
      "Evaluation and observability",
      "Prompt registry and regression",
      "CI quality gates",
      "Statistical contracts",
      "Analysis eligibility",
      "Descriptive statistics",
    ],
  },
  {
    title: "In progress",
    status: "in-progress",
    items: ["Product Intelligence", "Randomized-analysis foundations", "Further statistical-analysis capabilities"],
  },
  {
    title: "Planned and future research",
    status: "planned",
    items: [
      "CUPED",
      "Sequential testing",
      "Bayesian A/B testing",
      "Difference-in-Differences",
      "Propensity-score methods",
      "Double Machine Learning",
      "EconML",
      "DoWhy",
      "Business-impact estimation",
      "Enterprise platform capabilities",
      "Research capabilities",
    ],
  },
];

export function roadmapSummary(phases: readonly RoadmapPhase[]): readonly RoadmapPhase[] {
  return phases;
}
