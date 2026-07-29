import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AskExperiment from "@/app/ask-experiment/page";
import Roadmap from "@/app/roadmap/page";

describe("placeholder routes", () => {
  it("keeps future product pages limited to a title, description, and issue notice", () => {
    render(<AskExperiment />);
    expect(screen.getByRole("heading", { name: "Ask Experiment" })).toBeInTheDocument();
    expect(screen.getByText("Coming in Issue #3")).toBeInTheDocument();
  });

  it("renders the roadmap as a placeholder", () => {
    render(<Roadmap />);
    expect(screen.getByRole("heading", { name: "Roadmap" })).toBeInTheDocument();
  });
});
