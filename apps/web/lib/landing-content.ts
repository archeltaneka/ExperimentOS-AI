import { analysisCapabilities } from "@/lib/analysis-capabilities";
import type { CapabilityStatus } from "@/types/domain";

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
  { title: "Statistical Analysis", status: "completed", detail: "Backend statistical and causal methods with explicit inputs, diagnostics, and uncertainty." },
  { title: "Decision Intelligence", status: "completed", detail: "Validated business scenarios and decision safeguards; human approval remains required." },
];

export const capabilityStatusGroups: readonly {
  title: string;
  description: string;
  status: CapabilityStatus;
  items: readonly string[];
}[] = [
  {
    title: "Implemented backend capabilities",
    description: "Implementation status within the documented scope. These badges do not indicate results for a particular experiment or controls in the web interface.",
    status: "completed",
    items: ["Retrieval and grounded answers", "Agent workflow and human approval", "Evaluation and quality gates", ...analysisCapabilities.filter((capability) => !capability.optional).map((capability) => capability.name)],
  },
  {
    title: "Optional backend adapters",
    description: "Implemented adapters that require compatible dependencies and configuration before they can run.",
    status: "completed",
    items: analysisCapabilities.filter((capability) => capability.optional).map((capability) => capability.name),
  },
  {
    title: "Future platform and research",
    description: "Future scope with no delivery or deployment commitment.",
    status: "future-research",
    items: ["Enterprise permissions and collaboration", "Adaptive experimentation", "Advanced uplift modelling and policy learning"],
  },
];
