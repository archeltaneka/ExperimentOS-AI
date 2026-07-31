import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import Roadmap from "@/app/roadmap/page";
import { Providers } from "@/app/providers";
import { roadmapFixtures } from "@/mock/roadmap";

vi.mock("@/hooks/use-services", () => ({
  useRoadmapDataSource: () => ({
    kind: "local_configuration",
    label: "Repository-backed roadmap",
    detail: "Versioned deterministic metadata.",
  }),
  useRoadmapQuery: () => ({ data: roadmapFixtures, isError: false, isLoading: false, refetch: vi.fn() }),
}));

afterEach(cleanup);

describe("roadmap page", () => {
  it("renders the six repository-backed phases in order with the current phase prominent", async () => {
    render(
      <Providers>
        <Roadmap />
      </Providers>,
    );

    expect(screen.getByRole("heading", { level: 1, name: "Roadmap" })).toBeInTheDocument();
    expect(screen.getByText("phases completed").previousElementSibling).toHaveTextContent("3");

    const phases = [
      "Foundation",
      "Agent Workflow",
      "LLMOps and AI Reliability",
      "Product Intelligence and Causal Inference",
      "Enterprise Platform",
      "Research and Advanced Intelligence",
    ];
    const timeline = screen.getByLabelText("Roadmap phases").textContent ?? "";

    expect(screen.getByRole("heading", { name: "Completed" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "In progress" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Future and research" })).toBeInTheDocument();
    expect(phases.every((phase) => timeline.includes(phase))).toBe(true);
    expect(timeline.indexOf("Foundation")).toBeLessThan(timeline.indexOf("Agent Workflow"));
    expect(timeline.indexOf("Agent Workflow")).toBeLessThan(
      timeline.indexOf("LLMOps and AI Reliability"),
    );
    expect(screen.getAllByText("Product Intelligence and Causal Inference")[1].closest("article")).toHaveTextContent(
      "In progress",
    );
    expect(screen.getByRole("link", { name: "Jump to Product Intelligence and Causal Inference" })).toHaveAttribute(
      "href",
      "#product-intelligence",
    );
  });
});
