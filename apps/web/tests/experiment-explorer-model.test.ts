import { describe, expect, it } from "vitest";

import {
  getExplorerResults,
  normalizeExplorerState,
  type ExplorerState,
} from "@/features/experiment-explorer/explorer-model";
import type { Experiment } from "@/types/domain";

const experiments: readonly Experiment[] = [
  {
    id: "exp-1",
    name: "Payment recommendation",
    status: "completed",
    owner: { id: "ava", name: "Ava Patel", team: "Payments" },
    startedAt: "2026-06-03T09:00:00Z",
    primaryMetric: { name: "Payment completion", value: 4.2, unit: "% lift", direction: "increase" },
    decision: { status: "approved", recommendation: "Controlled rollout", rationale: "Ready" },
    analysisStatus: "completed",
    businessImpact: "not_estimated",
  },
  {
    id: "exp-2",
    name: "Search explanation",
    status: "running",
    owner: { id: "lin", name: "Lin Chen", team: "Search" },
    startedAt: "2026-07-20T09:00:00Z",
    primaryMetric: { name: "Search refinement", value: 1.8, unit: "% lift", direction: "increase" },
    decision: { status: "pending", recommendation: "Continue monitoring", rationale: "Open" },
    analysisStatus: "in-progress",
    businessImpact: "unavailable",
  },
  {
    id: "exp-3",
    name: "Payment retry treatment",
    status: "stopped",
    owner: { id: "ava", name: "Ava Patel", team: "Payments" },
    startedAt: "2026-04-12T09:00:00Z",
    primaryMetric: { name: "Retry completion", value: Number.NaN, unit: "% lift", direction: "neutral" },
    decision: { status: "rejected", recommendation: "Do not resume", rationale: "Guardrail" },
    analysisStatus: "completed",
    businessImpact: "unavailable",
  },
];

const defaultState: ExplorerState = {
  query: "",
  status: "",
  owner: "",
  from: "",
  to: "",
  sort: "startedAt",
  direction: "desc",
};

describe("Experiment Explorer model", () => {
  it("searches names case-insensitively after trimming whitespace", () => {
    const results = getExplorerResults(experiments, { ...defaultState, query: "  PAYMENT  " });

    expect(results.map((experiment) => experiment.id)).toEqual(["exp-1", "exp-3"]);
  });

  it("treats whitespace-only search as an empty query", () => {
    expect(getExplorerResults(experiments, { ...defaultState, query: "   " })).toHaveLength(3);
  });

  it("intersects status and owner filters", () => {
    const results = getExplorerResults(experiments, {
      ...defaultState,
      status: "completed",
      owner: "ava",
    });

    expect(results.map((experiment) => experiment.id)).toEqual(["exp-1"]);
  });

  it("sorts metric values deterministically and places unavailable values last", () => {
    const results = getExplorerResults(experiments, {
      ...defaultState,
      sort: "primaryMetric",
      direction: "asc",
    });

    expect(results.map((experiment) => experiment.id)).toEqual(["exp-2", "exp-1", "exp-3"]);
  });

  it("recovers safely from invalid URL state", () => {
    expect(
      normalizeExplorerState(
        new URLSearchParams("status=invalid&owner=unknown&from=not-a-date&sort=nope&direction=up"),
        experiments,
      ),
    ).toEqual(defaultState);
  });
});
