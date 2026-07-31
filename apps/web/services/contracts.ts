import type { DataSource, EvaluationDashboard, EvaluationHistoryPoint, EvaluationSummary, Experiment, ExperimentDetail, RagAnswer, RoadmapPhase } from "@/types/domain";

export interface AskRequest { question: string; experimentId: string; topK?: number; signal?: AbortSignal; }
export interface AskService { readonly source: DataSource; ask(request: AskRequest): Promise<RagAnswer>; }
export interface ExperimentService { readonly source: DataSource; list(signal?: AbortSignal): Promise<readonly Experiment[]>; getById(id: string, signal?: AbortSignal): Promise<ExperimentDetail>; }
export interface EvaluationService { readonly source: DataSource; getSummary(signal?: AbortSignal): Promise<EvaluationSummary>; getHistory(signal?: AbortSignal): Promise<readonly EvaluationHistoryPoint[]>; getDashboard(signal?: AbortSignal): Promise<EvaluationDashboard>; }
export interface RoadmapService { readonly source: DataSource; list(signal?: AbortSignal): Promise<readonly RoadmapPhase[]>; }
export interface Services { ask: AskService; experiments: ExperimentService; evaluations: EvaluationService; roadmap: RoadmapService; }
