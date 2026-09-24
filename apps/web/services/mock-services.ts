import type { AskRequest, AskService, EvaluationService, ExperimentService, RoadmapService } from "@/services/contracts";
import { ApiError } from "@/services/errors";
import { askSamples } from "@/mock/ask";
import { evaluationDashboardFixture, evaluationFixture, evaluationHistoryFixture } from "@/mock/evaluations";
import { experimentFixtures, paymentRecommendationExperiment } from "@/mock/experiments";
import { roadmapFixtures } from "@/mock/roadmap";
import type { DataSource, ExperimentDetail, RagAnswer } from "@/types/domain";
const fixtureSource: DataSource = { kind: "deterministic_fixture", label: "Development fixture", detail: "Fixed portfolio development data; not live telemetry." };
const roadmapSource: DataSource = { kind: "local_configuration", label: "Repository-backed roadmap", detail: "Versioned deterministic metadata, audited against repository implementation and project planning." };
export class MockAskService implements AskService {
  readonly source = fixtureSource;
  readonly samples = askSamples.map(({ experimentId, question }) => ({ experimentId, question }));
  async ask(request: AskRequest): Promise<RagAnswer> {
    const normalize = (question: string) => question.trim().replace(/\s+/g, " ").toLowerCase();
    const sample = askSamples.find((sample) => sample.experimentId === request.experimentId && normalize(sample.question) === normalize(request.question));
    if (!sample) throw new ApiError({ code: "demo_unavailable", message: "No saved demo answer matches this experiment and question." });
    return structuredClone(sample.answer);
  }
}
export class MockExperimentService implements ExperimentService { readonly source = fixtureSource; async list() { return experimentFixtures; } async getById(id: string): Promise<ExperimentDetail> { if (id === paymentRecommendationExperiment.id) return paymentRecommendationExperiment; const summary = experimentFixtures.find((experiment) => experiment.id === id); if (summary) return { ...summary, summary: "Deterministic portfolio fixture.", metrics: [summary.primaryMetric], capabilities: [] }; throw new ApiError({ code: "not_found", message: "Experiment fixture not found", status: 404, diagnostic: id }); } }
export class MockEvaluationService implements EvaluationService { readonly source = fixtureSource; async getSummary() { return evaluationFixture; } async getHistory() { return evaluationHistoryFixture; } async getDashboard() { return evaluationDashboardFixture; } }
export class LocalRoadmapService implements RoadmapService { readonly source = roadmapSource; async list() { return roadmapFixtures; } }
