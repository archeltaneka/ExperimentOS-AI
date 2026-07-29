export type ExperimentStatus = "completed" | "running" | "inconclusive" | "stopped";
export type DecisionStatus = "approved" | "rejected" | "pending" | "not_required";
export type AnalysisStatus = "completed" | "in-progress" | "planned" | "future-research" | "unavailable";
export type CapabilityStatus = AnalysisStatus;
export type RoadmapPhaseStatus = "completed" | "in_progress" | "planned";
export type BusinessImpactState = "available" | "not_estimated" | "unavailable";
export type DataSourceKind = "live_backend" | "deterministic_fixture" | "local_configuration" | "unavailable";

export interface DataSource {
  kind: DataSourceKind;
  label: "Live backend" | "Demo data" | "Development fixture" | "Local product configuration" | "Not yet connected";
  detail: string;
}

export interface ExperimentOwner { id: string; name: string; team: string; }
export interface ExperimentMetric { name: string; value: number; unit: string; direction: "increase" | "decrease" | "neutral"; }
export interface ExperimentDecision { status: DecisionStatus; recommendation: string; rationale: string; }
export interface Experiment {
  id: string; name: string; status: ExperimentStatus; owner: ExperimentOwner; startedAt: string;
  primaryMetric: ExperimentMetric; decision: ExperimentDecision; analysisStatus: AnalysisStatus;
  businessImpact: BusinessImpactState;
}

export interface ExperimentDetail extends Experiment {
  summary: string;
  metrics: readonly ExperimentMetric[];
  capabilities: readonly Capability[];
}

export interface SimilarityScore { value: number; }
export interface RetrievedChunk {
  experimentId: string; documentId: string; documentName: string; text: string;
  similarity: number; section?: string;
}
export interface Citation { experimentId: string; documentId?: string; documentName: string; quote?: string; section?: string; score?: number; }
export interface RequestMetadata {
  intent?: string; requiredAgents: readonly string[]; approvalStatus?: string;
  prompt?: { id: string; version: string }; workflow?: { trace: readonly WorkflowEvent[]; metrics: Readonly<Record<string, unknown>> };
}
export interface WorkflowEvent { node: string; event: string; at?: string; }
export interface RagAnswer { answer: string; citations: readonly Citation[]; retrievedChunks: readonly RetrievedChunk[]; requestMetadata: RequestMetadata; }

export interface EvaluationMetric { id: string; label: string; value: number; target: number; status: "pass" | "fail"; }
export interface EvaluationHistoryPoint { date: string; score: number; }
export interface PromptRegressionResult { name: string; baseline: number; candidate: number; status: "pass" | "regression"; }
export interface QualityGateResult { status: "pass" | "quality_fail" | "infrastructure_fail"; message: string; }
export interface Capability { name: string; phase: number; status: CapabilityStatus; detail: string; }
export interface EvaluationSummary {
  metrics: readonly EvaluationMetric[]; promptRegressions: readonly PromptRegressionResult[];
  qualityGate: QualityGateResult; capabilities: readonly Capability[];
}
export interface RoadmapPhase { id: string; title: string; status: RoadmapPhaseStatus; description: string; capabilities: readonly Capability[]; }
