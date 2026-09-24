import { act, cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Services } from "@/services/contracts";
import { ApiError } from "@/services/errors";
import { MockAskService, MockExperimentService } from "@/services/mock-services";
import { askFixture } from "@/mock/ask";
import { renderWithProviders } from "./render";

const state = vi.hoisted(() => ({ services: {} }));
vi.mock("@/services/adapters", () => ({ createServices: () => state.services }));
import { AskExperimentWorkspace } from "@/features/ask-experiment/ask-experiment-workspace";
import { ExperimentBrowser, ExperimentReportPage } from "@/features/ask-experiment/experiment-browser";

const payment = "8bb4bf4d-a372-4b6e-93a5-0dd9ad7c8750";
const hotel = "508d252d-0772-4a56-aa75-2e8f933a2ca1";
const sample = "What evidence supported the payment experiment recommendation?";
const services = state.services as Services;

beforeEach(() => {
  Object.assign(services, { ask: new MockAskService(), experiments: new MockExperimentService() });
});
afterEach(cleanup);

describe("demo answer boundaries", () => {
  it.each([
    [payment, "Which experiments had inconclusive results?"],
    [hotel, sample],
    ["unknown", sample],
    [payment, ""],
    [payment, "هل نجحت التجربة؟ 🔎"],
  ])("does not return payment evidence for unsupported input %s / %s", async (experimentId, question) => {
    await expect(services.ask.ask({ experimentId, question })).rejects.toMatchObject({ code: "demo_unavailable" });
  });

  it("returns the supported payment sample, accepting whitespace and case differences", async () => {
    const result = await services.ask.ask({ experimentId: payment, question: `  ${sample.toUpperCase()}  ` });
    expect(result.answer).toMatch(/4\.2%/);
    expect(result.citations.every((citation) => citation.experimentId === payment)).toBe(true);
  });

  it("answers a limitations sample with limitations evidence rather than the rollout answer", async () => {
    const result = await services.ask.ask({ experimentId: payment, question: "What are the limitations of this payment experiment record?" });
    expect(result.answer).toMatch(/sample size/i);
    expect(result.citations[0].section).toBe("Limitations");
  });
});

describe("Ask recovery and context integrity", () => {
  it("discloses saved samples before submission and refuses arbitrary questions without showing evidence", async () => {
    renderWithProviders(<AskExperimentWorkspace experimentId={payment} />);
    expect(screen.getByText(/saved answers.*sample questions/i)).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "Question" }), { target: { value: "Which experiment won?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask question" }));
    await waitFor(() => expect(screen.getAllByText(/no saved answer/i).length).toBeGreaterThan(0));
    expect(screen.queryByRole("heading", { name: "Grounded answer" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry question" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: sample }));
    fireEvent.click(screen.getByRole("button", { name: "Ask question" }));
    expect(await screen.findByRole("heading", { name: "Grounded answer" })).toBeInTheDocument();
  });

  it("prevents asking on records with no saved samples and links to a supported record", () => {
    renderWithProviders(<AskExperimentWorkspace experimentId={hotel} />);
    expect(screen.getByText(/no saved answers for this experiment/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask question" })).toBeDisabled();
    expect(screen.getByRole("link", { name: /open.*sample/i })).toHaveAttribute("href", `/ask-experiment/${payment}`);
  });

  it("offers recovery when contexts fail, then permits asking after retry", async () => {
    vi.spyOn(services.experiments, "list").mockRejectedValueOnce(new ApiError({ code: "network", message: "offline" }));
    renderWithProviders(<AskExperimentWorkspace />);
    fireEvent.click(await screen.findByRole("button", { name: "Retry loading experiments" }));
    expect(await screen.findByRole("combobox", { name: "Experiment context" })).toHaveValue(payment);
  });

  it("explains an empty context list without presenting an unusable submit action", async () => {
    vi.spyOn(services.experiments, "list").mockResolvedValue([]);
    renderWithProviders(<AskExperimentWorkspace />);
    expect(await screen.findByText("No experiments are available.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ask question" })).not.toBeInTheDocument();
  });

  it("discards old evidence when the experiment changes, including a late response", async () => {
    let complete!: (answer: typeof askFixture) => void;
    vi.spyOn(services.ask, "ask").mockImplementation(() => new Promise((resolve) => { complete = resolve; }));
    const view = renderWithProviders(<AskExperimentWorkspace experimentId={payment} />);
    fireEvent.change(screen.getByRole("textbox", { name: "Question" }), { target: { value: sample } });
    fireEvent.click(screen.getByRole("button", { name: "Ask question" }));
    await screen.findByText("Loading saved answer");
    view.rerender(<AskExperimentWorkspace experimentId={hotel} />);
    await act(async () => { complete(askFixture); });
    expect(screen.queryByRole("heading", { name: "Grounded answer" })).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Question" })).toHaveValue("");
  });

  it("keeps arbitrary single-experiment questions available in live mode", async () => {
    const ask = vi.fn().mockResolvedValue(askFixture);
    services.ask = { source: { kind: "live_backend", label: "Live backend", detail: "Live answers" }, ask };
    renderWithProviders(<AskExperimentWorkspace experimentId={hotel} />);
    fireEvent.change(screen.getByRole("textbox", { name: "Question" }), { target: { value: "Why did this experiment stop?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask question" }));
    await screen.findByRole("heading", { name: "Grounded answer" });
    expect(ask).toHaveBeenCalledWith(expect.objectContaining({ experimentId: hotel, question: "Why did this experiment stop?" }));
  });

  it("does not reattach an initial answer when selecting a different experiment", async () => {
    renderWithProviders(<AskExperimentWorkspace initialAnswer={askFixture} />);
    const selector = await screen.findByRole("combobox", { name: "Experiment context" });
    expect(screen.getByRole("heading", { name: "Grounded answer" })).toBeInTheDocument();
    fireEvent.change(selector, { target: { value: hotel } });
    expect(screen.queryByRole("heading", { name: "Grounded answer" })).not.toBeInTheDocument();
  });

  it("retries the failed question even if the draft was edited", async () => {
    const ask = vi.fn().mockRejectedValueOnce(new ApiError({ code: "network", message: "offline" })).mockResolvedValue(askFixture);
    services.ask = { source: { kind: "live_backend", label: "Live backend", detail: "Live answers" }, ask };
    renderWithProviders(<AskExperimentWorkspace experimentId={payment} />);
    fireEvent.change(screen.getByRole("textbox", { name: "Question" }), { target: { value: sample } });
    fireEvent.click(screen.getByRole("button", { name: "Ask question" }));
    const retry = await screen.findByRole("button", { name: "Retry question" });
    fireEvent.change(screen.getByRole("textbox", { name: "Question" }), { target: { value: "Different draft" } });
    fireEvent.click(retry);
    await screen.findByRole("heading", { name: "Grounded answer" });
    expect(ask.mock.calls.map(([request]) => request.question)).toEqual([sample, sample]);
    expect(screen.getByRole("textbox", { name: "Question" })).toHaveValue("Different draft");
  });

  it("submits only once for rapid repeated keyboard submissions", async () => {
    let complete!: (answer: typeof askFixture) => void;
    const ask = vi.spyOn(services.ask, "ask").mockImplementation(() => new Promise((resolve) => { complete = resolve; }));
    renderWithProviders(<AskExperimentWorkspace experimentId={payment} />);
    const input = screen.getByRole("textbox", { name: "Question" });
    fireEvent.change(input, { target: { value: sample } });
    for (let index = 0; index < 10; index++) fireEvent.keyDown(input, { key: "Enter", ctrlKey: true });
    await screen.findByText("Loading saved answer");
    expect(ask).toHaveBeenCalledTimes(1);
    await act(async () => { complete(askFixture); });
  });

  it("does not mislabel report service failures as a missing experiment", async () => {
    vi.spyOn(services.experiments, "getById").mockRejectedValueOnce(new ApiError({ code: "network", message: "offline" }));
    renderWithProviders(<ExperimentReportPage experimentId={payment} />);
    fireEvent.click(await screen.findByRole("button", { name: "Retry loading report" }));
    expect(await screen.findByRole("heading", { name: "Experiment report" })).toBeInTheDocument();
  });

  it("lets the Ask index recover from a failed experiment list", async () => {
    vi.spyOn(services.experiments, "list").mockRejectedValueOnce(new ApiError({ code: "network", message: "offline" }));
    renderWithProviders(<ExperimentBrowser />);
    fireEvent.click(await screen.findByRole("button", { name: "Retry loading experiments" }));
    expect(await screen.findByRole("link", { name: /Adaptive payment recommendation/ })).toBeInTheDocument();
  });
});
