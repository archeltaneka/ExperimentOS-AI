import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import Home from "@/app/page";

afterEach(cleanup);

describe("landing page", () => {
  it("keeps the featured evidence disclosed and linked to its matching record", async () => {
    render(await Home());
    const preview = screen.getByRole("region", { name: "Featured demo experiment" });
    expect(preview).toHaveTextContent("Adaptive payment recommendation");
    expect(preview).toHaveTextContent("4.2");
    expect(preview).toHaveTextContent(/fixture/i);
    expect(preview).toHaveTextContent(/not a causal/i);
    expect(within(preview).getByRole("link", { name: /inspect experiment/i })).toHaveAttribute(
      "href", "/experiment-explorer/8bb4bf4d-a372-4b6e-93a5-0dd9ad7c8750",
    );
  });
  it("explains grounded experiment decision support with one primary heading", async () => {
    render(await Home());

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Evidence-backed answers for product experiments.",
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("uses verified demo and repository destinations", async () => {
    render(await Home());

    expect(screen.getAllByRole("link", { name: /launch demo/i })[0]).toHaveAttribute(
      "href",
      "/ask-experiment",
    );
    expect(screen.getAllByRole("link", { name: /view github/i })[0]).toHaveAttribute(
      "href",
      "https://github.com/archeltaneka/ExperimentOS-AI",
    );
  });

  it("exposes accessible navigation and keyboard-reachable actions", async () => {
    render(await Home());

    expect(screen.getByRole("navigation", { name: "Landing page navigation" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View ExperimentOS AI on GitHub" })).toHaveAttribute(
      "target",
      "_blank",
    );
    expect(screen.getAllByRole("link", { name: /launch demo/i })[0]).not.toHaveAttribute(
      "tabindex",
      "-1",
    );
  });

  it("renders architecture stages in evidence-to-decision order", async () => {
    render(await Home());

    const stages = [
      "Experiment Repository",
      "Semantic Retrieval",
      "RAG Question Answering",
      "Agent Workflow",
      "Statistical Analysis",
      "Decision Intelligence",
    ];
    const text = screen.getByLabelText("ExperimentOS system architecture").textContent ?? "";

    expect(stages.every((stage) => text.includes(stage))).toBe(true);
    expect(text.indexOf("Experiment Repository")).toBeLessThan(text.indexOf("Semantic Retrieval"));
    expect(text.indexOf("Semantic Retrieval")).toBeLessThan(text.indexOf("RAG Question Answering"));
    expect(text.indexOf("RAG Question Answering")).toBeLessThan(text.indexOf("Agent Workflow"));
    expect(text.indexOf("Agent Workflow")).toBeLessThan(text.indexOf("Statistical Analysis"));
    expect(text.indexOf("Statistical Analysis")).toBeLessThan(text.indexOf("Decision Intelligence"));
  });

  it("distinguishes implemented analysis from future enterprise scope", async () => {
    render(await Home());

    expect(screen.getByText("CUPED").closest("section")).toHaveTextContent("Completed");
    expect(screen.getByText("Double Machine Learning").closest("section")).toHaveTextContent("Completed");
    expect(screen.getByText("Enterprise Platform").closest("li")).toHaveTextContent(
      "Future research",
    );
    expect(screen.getAllByText("Future research").some((badge) => badge.closest("li")?.textContent?.includes("Research"))).toBe(true);
    expect(screen.getByRole("link", { name: /view full roadmap/i })).toHaveAttribute(
      "href",
      "/roadmap",
    );
  });
});
