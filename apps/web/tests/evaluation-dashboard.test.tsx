import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { EvaluationDashboardView } from "@/features/evaluation-dashboard/evaluation-dashboard";
import { evaluationDashboardFixture } from "@/mock/evaluations";
import type { EvaluationDashboard } from "@/types/domain";

const state = { data: undefined as EvaluationDashboard | undefined, isError: false, isPending: false, error: { userMessage: "Unable to reach the service." }, refetch: vi.fn() };
vi.mock("@/hooks/use-services", () => ({
  useEvaluationDataSource: () => ({ kind: "deterministic_fixture", label: "Development fixture", detail: "Deterministic dashboard data." }),
  useEvaluationDashboardQuery: () => state,
}));
beforeEach(() => { state.data = structuredClone(evaluationDashboardFixture); state.isError = false; state.isPending = false; });
afterEach(cleanup);

it("identifies the saved run and explains why execution is disabled", () => {
  render(<EvaluationDashboardView />);
  expect(screen.getByRole("heading", { level: 1, name: "Evaluations" })).toBeInTheDocument();
  expect(screen.getByText(evaluationDashboardFixture.run.name)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Run evaluation" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Run evaluation" })).toHaveAccessibleDescription(/saved evaluation results/i);
});
it("puts failures first without treating unevaluated metrics as failures", () => {
  render(<EvaluationDashboardView />);
  const attention = screen.getByRole("region", { name: "Needs attention" });
  expect(within(attention).getByRole("link", { name: /Groundedness/ })).toHaveAttribute("href", "#metric-groundedness");
  expect(within(attention).queryByText("Faithfulness")).not.toBeInTheDocument();
  expect(attention.compareDocumentPosition(screen.getByRole("region", { name: "All metrics" })) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});
it("shows scores, comparison rules and baselines while preserving missing values", () => {
  render(<EvaluationDashboardView />);
  const metric = screen.getByRole("article", { name: "Groundedness" });
  expect(metric).toHaveTextContent("0.78");
  expect(metric).toHaveTextContent("≥ 0.85");
  expect(metric).toHaveTextContent("0.91");
  expect(metric).toHaveTextContent("Release-blocking check");
  const missing = screen.getByRole("article", { name: "Faithfulness" });
  expect(missing).toHaveTextContent("Not evaluated");
  expect(missing).toHaveTextContent("Not recorded");
  expect(missing).toHaveTextContent("Optional judge metric is disabled");
});
it("opens evidence inline from a priority link and allows collapse", () => {
  render(<EvaluationDashboardView />);
  fireEvent.click(within(screen.getByRole("region", { name: "Needs attention" })).getByRole("link", { name: /Insufficient evidence abstention/ }));
  const toggle = screen.getByRole("button", { name: /Insufficient evidence abstention/ });
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByText("Abstain when evidence is insufficient.")).toBeVisible();
  expect(screen.getByText("Candidate answer asserted an unsupported conclusion.")).toBeVisible();
  expect(screen.getByText("The experiment should be rolled out globally.")).toBeVisible();
  fireEvent.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByText("The experiment should be rolled out globally.")).not.toBeInTheDocument();
});
it("explains missing case evidence without inventing an answer", () => {
  render(<EvaluationDashboardView />);
  fireEvent.click(screen.getByRole("button", { name: /Citation coverage/ }));
  const details = screen.getByRole("region", { name: "Citation coverage details" });
  expect(details).toHaveTextContent("No answer excerpt was recorded.");
  expect(details).toHaveTextContent("No evidence reference was recorded.");
  expect(details).toHaveTextContent("No explanation was recorded.");
});
it("preserves zero scores and does not invent a threshold operator", () => {
  state.data!.metrics = [{ id: "zero", label: "Zero score", value: 0, baseline: 0, threshold: 0.5, status: "warning" }];
  render(<EvaluationDashboardView />);
  const metric = screen.getByRole("article", { name: "Zero score" });
  expect(within(metric).getAllByText("0")).toHaveLength(2);
  expect(metric).toHaveTextContent("0.5 (comparison rule not recorded)");
});
it("does not call missing detail results a passing evaluation", () => {
  state.data!.metrics = []; state.data!.cases = [];
  render(<EvaluationDashboardView />);
  expect(screen.getByText("No metric results were recorded.")).toBeInTheDocument();
  expect(screen.getByText("No case results were recorded.")).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Needs attention" })).toHaveTextContent(/gate reports a failure/i);
});
it("shows a no-blocker state for a passing run", () => {
  state.data!.gate = { status: "pass", message: "All required checks passed.", passed: 1, failed: 0, warnings: 0, regressions: 0, blockers: [] };
  state.data!.metrics = [{ id: "pass", label: "Passed check", value: 1, status: "pass", blocking: true }]; state.data!.cases = [];
  render(<EvaluationDashboardView />);
  expect(screen.getByRole("region", { name: "Needs attention" })).toHaveTextContent("No failed checks or regressions were recorded.");
});
it("announces loading by name", () => {
  state.isPending = true;
  render(<EvaluationDashboardView />);
  expect(screen.getByRole("status")).toHaveTextContent("Loading evaluation results");
});
it("provides retry for failed loads", () => {
  state.isError = true;
  render(<EvaluationDashboardView />);
  fireEvent.click(screen.getByRole("button", { name: "Retry loading evaluations" }));
  expect(state.refetch).toHaveBeenCalledOnce();
});
it("handles a missing run without a success summary", () => {
  state.data = undefined;
  render(<EvaluationDashboardView />);
  expect(screen.getByText("No evaluation run is available.")).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Evaluation quality gate" })).not.toBeInTheDocument();
});

it("prioritizes blocking cases ahead of non-blocking failed metrics", () => {
  state.data!.metrics = [{ id: "advisory", label: "Advisory metric", value: 0.1, status: "fail", blocking: false }];
  render(<EvaluationDashboardView />);
  const links = within(screen.getByRole("region", { name: "Needs attention" })).getAllByRole("link");
  expect(links[0]).toHaveTextContent("Insufficient evidence abstention");
  expect(links[1]).toHaveTextContent("Advisory metric");
});
