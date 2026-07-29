import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AskExperiment from "@/app/ask-experiment/page";
import Roadmap from "@/app/roadmap/page";
import { Providers } from "@/app/providers";

describe("placeholder routes", () => {
  it("renders the Ask Experiment workspace inside the application route", () => {
    render(<Providers><AskExperiment /></Providers>);
    expect(screen.getByRole("heading", { name: "Ask Experiment" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Question" })).toBeInTheDocument();
  });

  it("renders the roadmap as a placeholder", () => {
    render(<Roadmap />);
    expect(screen.getByRole("heading", { name: "Roadmap" })).toBeInTheDocument();
  });
});
