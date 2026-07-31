export type ExperimentStatus = "completed" | "running" | "inconclusive" | "stopped";
export type DecisionStatus = "approved" | "rejected" | "pending" | "not_required";
export type AnalysisStatus = "completed" | "in-progress" | "planned" | "future-research" | "unavailable";
export type CapabilityStatus = AnalysisStatus;
export type RoadmapPhaseStatus = "completed" | "in_progress" | "planned" | "future" | "research";
export type BusinessImpactState = "available" | "not_estimated" | "unavailable";
export type DataSourceKind = "live_backend" | "deterministic_fixture" | "local_configuration" | "unavailable";

export interface DataSource {
  kind: DataSourceKind;
  label: "Live backend" | "Demo data" | "Development fixture" | "Local product configuration" | "Repository-backed roadmap" | "Not yet connected";
  detail: string;
}

export interface ExperimentOwner { id: string; name: string; team: string; }
export interface ExperimentMetric {
  name: string;
  value: number;
  unit: string;
  direction: "increase" | "decrease" | "neutral";
  baseline?: number;
  treatment?: number;
  absoluteChange?: number;
  relativeChange?: number;
}
export interface ExperimentDecision {
  status: DecisionStatus;
  recommendation: string;
  rationale: string;
  decidedAt?: string;
  decidedBy?: string;
  nextAction?: string;
}
export interface Experiment {
  id: string; name: string; status: ExperimentStatus; owner: ExperimentOwner; startedAt: string;
  primaryMetric: ExperimentMetric; decision: ExperimentDecision; analysisStatus: AnalysisStatus;
  businessImpact: BusinessImpactState;
}

export interface ExperimentDetail extends Experiment {
  summary: string;
  metrics: readonly ExperimentMetric[];
  capabilities: readonly Capability[];
  overview?: ExperimentOverview;
  report?: ExperimentReport;
  analysisReadiness?: AnalysisReadiness;
  retrievedChunks?: readonly ExperimentRetrievedChunk[];
  citations?: readonly ExperimentCitation[];
  recordMetadata?: readonly RecordMetadataItem[];
}

export interface ExperimentOverview {
  hypothesis?: string;
  problemStatement?: string;
  description?: string;
  targetAudience?: string;
  platform?: string;
  experimentType?: string;
  endedAt?: string;
  tags?: readonly string[];
}

export interface ExperimentReport {
  id?: string;
  source: string;
  executiveSummary?: string;
  methodology?: string;
  results?: string;
  interpretation?: string;
  recommendation?: string;
  limitations?: string;
  followUpActions?: readonly string[];
}

export type ReadinessStatus = "eligible" | "ineligible" | "needs_more_data" | "unavailable";
export type ReadinessCheckStatus = "pass" | "fail" | "unavailable";
export interface AnalysisReadinessCheck {
  label: string;
  status: ReadinessCheckStatus;
  detail: string;
}
export interface AnalysisReadiness {
  status: ReadinessStatus;
  stage: string;
  checks: readonly AnalysisReadinessCheck[];
  blockedBy?: string;
}

export interface ExperimentRetrievedChunk extends RetrievedChunk {
  id: string;
  citationId?: string;
}
export interface ExperimentCitation {
  id: string;
  documentId?: string;
  documentName: string;
  chunkId?: string;
  section?: string;
}
export interface RecordMetadataItem { label: string; value: string; }

export interface SimilarityScore { value: number; }
export interface RetrievedChunk {
  experimentId: string; documentId: string; documentName: string; text: string;
  similarity?: number; section?: string; experimentName?: string; chunkType?: string;
}
export interface Citation { experimentId: string; documentId?: string; documentName: string; quote?: string; section?: string; score?: number; }
export interface RequestMetadata {
  intent?: string; requiredAgents: readonly string[]; approvalStatus?: string;
  prompt?: { id: string; version: string }; model?: string; latencyMs?: number;
  retrievedChunkCount?: number; averageSimilarity?: number;
  workflow?: { trace: readonly WorkflowEvent[]; metrics: Readonly<Record<string, unknown>> };
}
export interface WorkflowEvent { node: string; event: string; at?: string; }
export interface RagAnswer { answer: string; citations: readonly Citation[]; retrievedChunks: readonly RetrievedChunk[]; requestMetadata: RequestMetadata; }

export type ComparisonOperator = ">=" | "<=";
export type EvaluationStatus = "pass" | "fail" | "warning" | "not_evaluated" | "regressed" | "improved" | "unchanged" | "not_gated";
export interface EvaluationMetric { id: string; label: string; value?: number; baseline?: number; threshold?: number; target?: number; operator?: ComparisonOperator; status: EvaluationStatus; group?: "retrieval" | "generation" | "prompt"; framework?: string; sampleCount?: number; blocking?: boolean; detail?: string; }
export function evaluateMetric(metric: Pick<EvaluationMetric, "value" | "threshold" | "operator">): "pass" | "fail" | "not_gated" { if (metric.value === undefined || metric.threshold === undefined || metric.operator === undefined) return "not_gated"; return metric.operator === ">=" ? (metric.value >= metric.threshold ? "pass" : "fail") : (metric.value <= metric.threshold ? "pass" : "fail"); }
export interface EvaluationHistoryPoint { date: string; score: number; }
export interface PromptRegressionResult { name: string; baseline: number; candidate: number; status: "pass" | "regression"; }
export interface QualityGateResult { status: "pass" | "quality_fail" | "infrastructure_fail"; message: string; }
export interface Capability { name: string; phase: number; status: CapabilityStatus; detail: string; }
export interface EvaluationSummary {
  metrics: readonly EvaluationMetric[]; promptRegressions: readonly PromptRegressionResult[];
  qualityGate: QualityGateResult; capabilities: readonly Capability[];
}
export interface EvaluationCase { id: string; name: string; type: "Retrieval" | "Generation" | "Prompt regression"; status: EvaluationStatus; current?: number; baseline?: number; expected: string; reason?: string; framework: string; blocking: boolean; answerExcerpt?: string; evidence?: string; }
export interface EvaluationDashboard { run: { id: string; name: string; status: "pass" | "fail" | "warning" | "not_evaluated"; prompt?: string; dataset: string; model?: string; createdAt: string; }; metrics: readonly EvaluationMetric[]; cases: readonly EvaluationCase[]; gate: { status: "pass" | "fail" | "warning" | "not_evaluated"; message: string; passed: number; failed: number; warnings: number; regressions: number; blockers: readonly string[]; }; promptRegression: { prompt: string; baseline: string; goldenCases: number; passed: number; failed: number; regressed: number; improved: number; unchanged: number; }; integrations: readonly { name: string; state: "available" | "not_connected"; detail: string }[]; }
export interface RoadmapCapabilityGroup {
  title: string;
  description?: string;
  capabilities: readonly Capability[];
}
export interface RoadmapPhase {
  id: string;
  number: number;
  title: string;
  status: RoadmapPhaseStatus;
  description: string;
  objective: string;
  technicalSignificance: string;
  limitations: string;
  capabilityGroups: readonly RoadmapCapabilityGroup[];
  relatedRoutes?: readonly { href: string; label: string }[];
}
