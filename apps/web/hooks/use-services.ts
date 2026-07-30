"use client";
import { useMutation, useQuery, type UseMutationResult } from "@tanstack/react-query";
import { createServices } from "@/services/adapters";
import type { ApiError } from "@/services/errors";
import type { AskRequest } from "@/services/contracts";
import type { DataSource } from "@/types/domain";
import { askQueryKeys } from "@/services/query-keys";
import type { EvaluationHistoryPoint, EvaluationSummary, Experiment, ExperimentDetail, RagAnswer, RoadmapPhase } from "@/types/domain";
const services = createServices();
const staleTime = 5 * 60_000;
export function useAskMutation(): UseMutationResult<RagAnswer, ApiError, AskRequest> { return useMutation({ mutationFn: (request) => services.ask.ask(request) }); }
export function useAskDataSource(): DataSource { return services.ask.source; }
export function useExperimentsQuery() { return useQuery<readonly Experiment[], ApiError>({ queryKey: askQueryKeys.experimentList(), queryFn: ({ signal }) => services.experiments.list(signal), staleTime }); }
export function useExperimentDetailQuery(id: string) { return useQuery<ExperimentDetail, ApiError>({ queryKey: askQueryKeys.experimentDetail(id), queryFn: ({ signal }) => services.experiments.getById(id, signal), enabled: Boolean(id), staleTime }); }
export function useEvaluationSummaryQuery() { return useQuery<EvaluationSummary, ApiError>({ queryKey: askQueryKeys.evaluationSummary(), queryFn: ({ signal }) => services.evaluations.getSummary(signal), staleTime }); }
export function useEvaluationHistoryQuery() { return useQuery<readonly EvaluationHistoryPoint[], ApiError>({ queryKey: askQueryKeys.evaluationHistory(), queryFn: ({ signal }) => services.evaluations.getHistory(signal), staleTime }); }
export function useRoadmapQuery() { return useQuery<readonly RoadmapPhase[], ApiError>({ queryKey: askQueryKeys.roadmap(), queryFn: ({ signal }) => services.roadmap.list(signal), staleTime: Infinity }); }
