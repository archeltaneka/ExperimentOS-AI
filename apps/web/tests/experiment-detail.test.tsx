import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ExperimentDetail } from "@/features/experiment-detail/experiment-detail";
import type { DataSource, ExperimentDetail as ExperimentDetailRecord } from "@/types/domain";

const experiment: ExperimentDetailRecord = {
  id: "8bb4bf4d-a372-4b6e-93a5-0dd9ad7c8750",
  name: "Adaptive payment recommendation",
  status: "completed",
  owner: { id: "owner-ava", name: "Ava Patel", team: "Payments" },
  startedAt: "2026-06-03T09:00:00Z",
  primaryMetric: {
    name: "Payment completion",
    value: 4.2,
    unit: "% lift",
    direction: "increase",
  },
  decision: {
    status: "approved",
    recommendation: "Controlled rollout",
    rationale: "The primary metric improved with acceptable guardrails.",
  },
  analysisStatus: "completed",
  businessImpact: "not_estimated",
  summary: "A deterministic portfolio fixture showing an approved rollout decision.",
  metrics: [
    {
      name: "Payment completion",
      value: 4.2,
      unit: "% lift",
      direction: "increase",
    },
    {
      name: "Checkout errors",
      value: -0.3,
      unit: "% change",
      direction: "decrease",
    },
  ],
  capabilities: [
    { name: "Statistical contracts", phase: 4, status: "completed", detail: "Implemented." },
    { name: "Descriptive statistics", phase: 4, status: "completed", detail: "Implemented." },
    { name: "CUPED", phase: 4, status: "planned", detail: "Not implemented." },
    { name: "Sequential testing", phase: 4, status: "planned", detail: "Not implemented." },
    { name: "Bayesian A/B testing", phase: 4, status: "planned", detail: "Not implemented." },
    { name: "Difference-in-Differences", phase: 4, status: "future-research", detail: "Future research." },
    { name: "Propensity-score methods", phase: 4, status: "future-research", detail: "Future research." },
    { name: "Double Machine Learning", phase: 4, status: "future-research", detail: "Future research." },
    { name: "EconML", phase: 4, status: "future-research", detail: "Future research." },
    { name: "DoWhy", phase: 4, status: "future-research", detail: "Future research." },
    { name: "Business-impact estimation", phase: 4, status: "unavailable", detail: "Not available." },
  ],
  report: {
    id: "payment-report",
    source: "Experiment report",
    executiveSummary: "Payment completion increased in the recorded result.",
    results: "The observed descriptive difference was +4.2% lift.",
    limitations: "No inferential statistics are attached to this fixture.",
  },
  analysisReadiness: {
    status: "eligible",
    stage: "Descriptive statistics available",
    checks: [
      { label: "Required metrics available", status: "pass", detail: "Primary and guardrail metrics are recorded." },
      { label: "Assignment integrity", status: "unavailable", detail: "No assignment audit is attached to this fixture." },
    ],
  },
  retrievedChunks: [
    {
      id: "payment-report-results-1",
      experimentId: "8bb4bf4d-a372-4b6e-93a5-0dd9ad7c8750",
      documentId: "payment-report",
      documentName: "Payment recommendation report",
      text: "Payment completion increased by 4.2% with no material checkout-error increase.",
      section: "Results",
      similarity: 0.92,
      citationId: "[1]",
    },
  ],
  citations: [
    {
      id: "[1]",
      documentId: "payment-report",
      documentName: "Payment recommendation report",
      chunkId: "payment-report-results-1",
      section: "Results",
    },
  ],
};

const source: DataSource = {
  kind: "deterministic_fixture",
  label: "Development fixture",
  detail: "Fixed portfolio development data; not live telemetry.",
};

const queryState = {
  data: experiment as ExperimentDetailRecord | undefined,
  isPending: false,
  isError: false,
  error: null as { code: string; userMessage: string } | null,
  refetch: vi.fn(),
};

vi.mock("@/hooks/use-services", () => ({
  useExperimentDetailQuery: () => queryState,
  useExperimentDataSource: () => source,
}));

describe("Experiment detail", () => {
  afterEach(cleanup);

  beforeEach(() => {
    queryState.data = experiment;
    queryState.isPending = false;
    queryState.isError = false;
    queryState.error = null;
    queryState.refetch.mockReset();
  });

  it("renders a service-backed fixture record with honest decision and metric semantics", () => {
    render(<ExperimentDetail experimentId={experiment.id} explorerSearch="q=payment&status=completed" />);

    expect(screen.getByRole("heading", { name: experiment.name })).toBeInTheDocument();
    expect(screen.getAllByText(experiment.id).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Completed").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Ship").length).toBeGreaterThan(0);
    expect(screen.getByText("Development fixture")).toBeInTheDocument();
    expect(screen.getAllByText(/observed difference/i).length).toBeGreaterThan(0);
    expect(screen.getByText("4.2% lift")).toBeInTheDocument();
    expect(screen.getByText(/not a causal impact estimate/i)).toBeInTheDocument();
    expect(screen.queryByText(/p-value|confidence interval/i)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /back to experiment explorer/i })).toHaveAttribute(
      "href",
      "/experiment-explorer?q=payment&status=completed",
    );
  });

  it("renders report evidence, truthful capability states, and ranked chunk citations", () => {
    render(<ExperimentDetail experimentId={experiment.id} />);

    expect(screen.getByText("Experiment report")).toBeInTheDocument();
    expect(screen.getByText("Analysis readiness")).toBeInTheDocument();
    expect(screen.getByText("Eligible")).toBeInTheDocument();
    expect(screen.getByText("CUPED")).toBeInTheDocument();
    expect(screen.getAllByText("Planned").length).toBeGreaterThan(0);
    expect(screen.getByText(/Higher similarity indicates closer embedding-space relevance/i)).toBeInTheDocument();
    expect(screen.getByText("Similarity 0.92")).toBeInTheDocument();
    expect(screen.getByText("[1]")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /run analysis/i })).not.toBeInTheDocument();
  });

  it("renders loading, not-found, and normalized error states through the query boundary", () => {
    queryState.isPending = true;
    const { rerender } = render(<ExperimentDetail experimentId={experiment.id} />);
    expect(screen.getByLabelText("Loading experiment detail")).toBeInTheDocument();

    queryState.isPending = false;
    queryState.isError = true;
    queryState.error = { code: "not_found", userMessage: "The requested item was not found." };
    rerender(<ExperimentDetail experimentId="missing-id" />);
    expect(screen.getByRole("heading", { name: "Experiment not found" })).toBeInTheDocument();
    expect(screen.getByText("missing-id")).toBeInTheDocument();

    queryState.error = { code: "timeout", userMessage: "The request timed out." };
    rerender(<ExperimentDetail experimentId={experiment.id} />);
    fireEvent.click(screen.getByRole("button", { name: "Retry loading experiment" }));
    expect(queryState.refetch).toHaveBeenCalledOnce();
  });

  it("degrades unavailable metric values without treating them as zero", () => {
    queryState.data = {
      ...experiment,
      primaryMetric: { ...experiment.primaryMetric, value: Number.NaN },
    };

    render(<ExperimentDetail experimentId={experiment.id} />);

    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
    expect(screen.queryByText("0% lift")).not.toBeInTheDocument();
  });

  it("keeps raw fixtures and direct fetch calls outside the presentation component", () => {
    const source = readFileSync(
      resolve(process.cwd(), "features/experiment-detail/experiment-detail.tsx"),
      "utf8",
    );

    expect(source).not.toMatch(/@\/mock\//);
    expect(source).not.toMatch(/\bfetch\s*\(/);
    expect(source).toContain("useExperimentDetailQuery");
  });
});
