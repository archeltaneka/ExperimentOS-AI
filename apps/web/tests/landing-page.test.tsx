import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import Home from "@/app/page";

afterEach(cleanup);

describe("landing page", () => {
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

  it("keeps roadmap and unfinished analytical capabilities honest", async () => {
    render(await Home());

    expect(screen.getAllByText("Product Intelligence")).not.toHaveLength(0);
    expect(screen.getAllByText("In progress")).not.toHaveLength(0);
    expect(screen.getByText("CUPED").closest("li")).toHaveTextContent("Planned");
    expect(screen.getByText("Double Machine Learning").closest("li")).toHaveTextContent(
      "Future research",
    );
    expect(screen.getByText("Enterprise Platform").closest("li")).toHaveTextContent(
      "Future research",
    );
    expect(screen.getByText("Research").closest("li")).toHaveTextContent("Future research");
    expect(screen.getByRole("link", { name: /view full roadmap/i })).toHaveAttribute(
      "href",
      "/roadmap",
    );
  });
});
