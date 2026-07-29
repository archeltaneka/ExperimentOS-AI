import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RagAnswer } from "@/types/domain";

const mutate = vi.fn();
const reset = vi.fn();

vi.mock("@/hooks/use-services", () => ({
  useAskMutation: () => ({ mutate, reset, isPending: false, isError: false, error: null }),
  useAskDataSource: () => ({
    kind: "deterministic_fixture",
    label: "Development fixture",
    detail: "Fixed portfolio development data; not live telemetry.",
  }),
}));

import { AskExperimentWorkspace } from "@/features/ask-experiment/ask-experiment-workspace";

afterEach(cleanup);

const answer: RagAnswer = {
  answer: "Payment completion increased by 4.2%.",
  citations: [
    {
      experimentId: "8bb4bf4d-a372-4b6e-93a5-0dd9ad7c8750",
      documentId: "report-results",
      documentName: "Payment recommendation report",
      section: "Results",
      score: 0.92,
    },
  ],
  retrievedChunks: [
    {
      experimentId: "8bb4bf4d-a372-4b6e-93a5-0dd9ad7c8750",
      documentId: "report-results",
      documentName: "Payment recommendation report",
      text: "Payment completion increased by 4.2%.",
      section: "Results",
      similarity: 0.92,
    },
  ],
  requestMetadata: {
    intent: "decision_support",
    requiredAgents: ["retrieval", "decision"],
    approvalStatus: "pending",
  },
};

describe("AskExperimentWorkspace", () => {
  it("renders a labelled question form and prevents blank submissions", () => {
    render(<AskExperimentWorkspace />);

    expect(screen.getByRole("heading", { name: "Ask Experiment" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Ask question" }));
    expect(screen.getByText("Enter a question before asking.")).toBeInTheDocument();
    expect(mutate).not.toHaveBeenCalled();
  });

  it("populates editable text from an example and submits only with Ctrl+Enter", () => {
    render(<AskExperimentWorkspace />);

    fireEvent.click(screen.getByRole("button", { name: /Which experiment produced/i }));
    const question = screen.getByRole("textbox", { name: "Question" });
    expect(question).toHaveValue("Which experiment produced the highest conversion lift?");
    fireEvent.keyDown(question, { key: "Enter" });
    expect(mutate).not.toHaveBeenCalled();
    fireEvent.keyDown(question, { key: "Enter", ctrlKey: true });
    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({ question: "Which experiment produced the highest conversion lift?" }),
      expect.any(Object),
    );
  });

  it("renders answer evidence and clears it on reset", () => {
    render(<AskExperimentWorkspace initialAnswer={answer} />);

    expect(screen.getAllByText("Payment completion increased by 4.2%.")).not.toHaveLength(0);
    expect(screen.getAllByText("Similarity 0.92")).not.toHaveLength(0);
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument();
    expect(screen.getByText(/higher similarity indicates closer embedding-space relevance/i)).toBeInTheDocument();
    expect(screen.getByText("Payment recommendation report")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reset result" }));
    expect(screen.queryByText("Payment completion increased by 4.2%.")).not.toBeInTheDocument();
    expect(reset).toHaveBeenCalled();
  });
});
