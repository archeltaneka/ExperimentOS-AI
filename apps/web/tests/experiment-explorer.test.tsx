import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ExperimentExplorer } from "@/features/experiment-explorer/experiment-explorer";
import type { DataSource, Experiment } from "@/types/domain";

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
];

const source: DataSource = {
  kind: "deterministic_fixture",
  label: "Development fixture",
  detail: "Fixed portfolio development data; not live telemetry.",
};

const queryState = {
  data: experiments,
  isPending: false,
  isError: false,
  error: null as { userMessage: string } | null,
  refetch: vi.fn(),
};

vi.mock("@/hooks/use-services", () => ({
  useExperimentsQuery: () => queryState,
  useExperimentDataSource: () => source,
}));

describe("Experiment Explorer", () => {
  afterEach(cleanup);

  beforeEach(() => {
    queryState.data = experiments;
    queryState.isPending = false;
    queryState.isError = false;
    queryState.error = null;
    queryState.refetch.mockReset();
    window.history.replaceState({}, "", "/experiment-explorer");
  });

  it("renders its title, fixture disclosure, and service-backed rows", () => {
    render(<ExperimentExplorer />);

    expect(screen.getByText("Development fixture")).toBeInTheDocument();
    expect(screen.getByText(source.detail)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Payment recommendation/i })).toHaveAttribute(
      "href",
      "/experiment-explorer/exp-1",
    );
  });

  it("filters case-insensitively, composes filters, and clears them", () => {
    render(<ExperimentExplorer />);

    fireEvent.change(screen.getByRole("searchbox", { name: "Search experiments" }), {
      target: { value: " SEARCH " },
    });
    expect(screen.getByText("1 of 2 experiments")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "running" } });
    fireEvent.change(screen.getByLabelText("Owner"), { target: { value: "lin" } });
    expect(screen.getByText("Search explanation")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Clear all filters" }));
    expect(screen.getByText("2 experiments")).toBeInTheDocument();
  });

  it("renders decision text and honest non-monetary business-impact states", () => {
    render(<ExperimentExplorer />);

    expect(screen.getByText("Ship")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText("Not estimated")).toBeInTheDocument();
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.queryByText(/\$|AUD|USD/)).not.toBeInTheDocument();
  });

  it("shows distinct loading, error, no-data, and no-match states", () => {
    queryState.isPending = true;
    const { rerender } = render(<ExperimentExplorer />);
    expect(screen.getByLabelText("Loading experiments")).toBeInTheDocument();

    queryState.isPending = false;
    queryState.isError = true;
    queryState.error = { userMessage: "The request timed out." };
    rerender(<ExperimentExplorer />);
    fireEvent.click(screen.getByRole("button", { name: "Retry loading experiments" }));
    expect(queryState.refetch).toHaveBeenCalledOnce();

    queryState.isError = false;
    queryState.error = null;
    queryState.data = [];
    rerender(<ExperimentExplorer />);
    expect(screen.getByText("No experiments are available")).toBeInTheDocument();

    queryState.data = experiments;
    rerender(<ExperimentExplorer />);
    fireEvent.change(screen.getByRole("searchbox", { name: "Search experiments" }), {
      target: { value: "missing" },
    });
    expect(screen.getByText("No experiments match your explorer settings")).toBeInTheDocument();
  });
});
