import type { AskService, EvaluationService, ExperimentService, RoadmapService } from "@/services/contracts";
import { ApiError } from "@/services/errors";
import { askFixture } from "@/mock/ask";
import { evaluationDashboardFixture, evaluationFixture, evaluationHistoryFixture } from "@/mock/evaluations";
import { experimentFixtures, paymentRecommendationExperiment } from "@/mock/experiments";
import { roadmapFixtures } from "@/mock/roadmap";
import type { DataSource, ExperimentDetail, RagAnswer } from "@/types/domain";
const fixtureSource: DataSource = { kind: "deterministic_fixture", label: "Development fixture", detail: "Fixed portfolio development data; not live telemetry." };
const roadmapSource: DataSource = { kind: "local_configuration", label: "Local product configuration", detail: "Versioned roadmap metadata." };
export class MockAskService implements AskService { readonly source = fixtureSource; async ask(): Promise<RagAnswer> { return askFixture; } }
export class MockExperimentService implements ExperimentService { readonly source = fixtureSource; async list() { return experimentFixtures; } async getById(id: string): Promise<ExperimentDetail> { if (id === paymentRecommendationExperiment.id) return paymentRecommendationExperiment; const summary = experimentFixtures.find((experiment) => experiment.id === id); if (summary) return { ...summary, summary: "Deterministic portfolio fixture.", metrics: [summary.primaryMetric], capabilities: [] }; throw new ApiError({ code: "not_found", message: "Experiment fixture not found", status: 404, diagnostic: id }); } }
export class MockEvaluationService implements EvaluationService { readonly source = fixtureSource; async getSummary() { return evaluationFixture; } async getHistory() { return evaluationHistoryFixture; } async getDashboard() { return evaluationDashboardFixture; } }
export class LocalRoadmapService implements RoadmapService { readonly source = roadmapSource; async list() { return roadmapFixtures; } }
