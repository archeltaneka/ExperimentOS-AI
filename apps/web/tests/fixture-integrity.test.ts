import { describe, expect, it } from "vitest";

import { askFixture } from "@/mock/ask";
import { evaluationDashboardFixture } from "@/mock/evaluations";
import { experimentFixtures, paymentRecommendationExperiment } from "@/mock/experiments";
import { roadmapFixtures } from "@/mock/roadmap";
import { evaluateMetric } from "@/types/domain";

const futureCapabilities = [
  "CUPED",
  "Sequential testing",
  "Bayesian A/B testing",
  "Difference-in-Differences",
  "Propensity-score methods",
  "Double Machine Learning",
  "EconML",
  "DoWhy",
  "Business-impact estimation",
];

describe("deterministic fixture contracts", () => {
  it("keeps experiment IDs unique and all evidence references resolvable", () => {
    const ids = experimentFixtures.map((experiment) => experiment.id);
    expect(new Set(ids).size).toBe(ids.length);

    for (const citation of askFixture.citations) {
      expect(ids).toContain(citation.experimentId);
    }
    for (const chunk of paymentRecommendationExperiment.retrievedChunks ?? []) {
      expect(ids).toContain(chunk.experimentId);
      expect(chunk.similarity).toBeGreaterThanOrEqual(0);
      expect(chunk.similarity).toBeLessThanOrEqual(1);
    }
    expect(
      (paymentRecommendationExperiment.retrievedChunks ?? []).map((chunk) => chunk.citationId),
    ).toEqual((paymentRecommendationExperiment.citations ?? []).map((citation) => citation.id));
  });

  it("keeps roadmap order, active status, and future capability claims honest", () => {
    expect(roadmapFixtures.map((phase) => phase.number)).toEqual([1, 2, 3, 4, 5, 6]);
    expect(roadmapFixtures.filter((phase) => phase.status === "in_progress")).toHaveLength(1);
    expect(new Set(roadmapFixtures.map((phase) => phase.number)).size).toBe(roadmapFixtures.length);

    const capabilities = roadmapFixtures.flatMap((phase) =>
      phase.capabilityGroups.flatMap((group) => group.capabilities),
    );
    for (const capability of capabilities.filter((item) => futureCapabilities.includes(item.name))) {
      expect(capability.status).not.toBe("completed");
      expect(capability.status).not.toBe("in-progress");
    }
  });

  it("keeps evaluation IDs, gate counts, and thresholds internally consistent", () => {
    const dashboard = evaluationDashboardFixture;
    expect(new Set(dashboard.cases.map((item) => item.id)).size).toBe(dashboard.cases.length);
    expect(dashboard.metrics.filter((item) => item.group === "retrieval")).not.toHaveLength(0);
    expect(dashboard.metrics.filter((item) => item.group === "generation")).not.toHaveLength(0);

    for (const metric of dashboard.metrics) {
      if (metric.threshold !== undefined && metric.value !== undefined && metric.operator !== undefined) {
        expect(["pass", "fail", "warning"]).toContain(metric.status);
        if (metric.status !== "warning") {
          expect(metric.status).toBe(evaluateMetric(metric));
        }
      }
    }
    expect(dashboard.gate.failed).toBe(dashboard.metrics.filter((item) => item.status === "fail").length);
    expect(dashboard.gate.regressions).toBe(
      dashboard.cases.filter((item) => item.status === "regressed").length,
    );
  });

  it("uses fixed ISO timestamps and never synthesizes monetary impact", () => {
    for (const experiment of experimentFixtures) {
      expect(experiment.startedAt).toMatch(/^2026-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
      expect(experiment.businessImpact).not.toBe("available");
    }
    expect(evaluationDashboardFixture.run.createdAt).toBe("2026-07-15T10:30:00Z");
  });
});
