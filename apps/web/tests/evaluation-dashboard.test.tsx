import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EvaluationDashboardView } from "@/features/evaluation-dashboard/evaluation-dashboard";
import { evaluationDashboardFixture } from "@/mock/evaluations";

vi.mock("@/hooks/use-services", () => ({
  useEvaluationDataSource: () => ({
    kind: "deterministic_fixture",
    label: "Development fixture",
    detail: "Deterministic dashboard data.",
  }),
  useEvaluationDashboardQuery: () => ({
    data: evaluationDashboardFixture,
    isError: false,
    isPending: false,
  }),
}));

afterEach(cleanup);

describe("evaluation dashboard", () => {
  it("renders a disabled run control and the current evaluation as a compact table row", () => {
    render(<EvaluationDashboardView />);

    expect(screen.getByRole("heading", { level: 1, name: "Evaluations" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run evaluation" })).toBeDisabled();
    expect(screen.getByRole("columnheader", { name: "Name" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Dataset" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Criteria" })).toBeInTheDocument();
    expect(screen.getByText(evaluationDashboardFixture.run.name)).toBeInTheDocument();
    expect(screen.getByText(evaluationDashboardFixture.run.dataset)).toBeInTheDocument();
  });
});
