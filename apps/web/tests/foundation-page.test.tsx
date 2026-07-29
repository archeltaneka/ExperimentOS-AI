import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Home from "@/app/page";
import { Providers } from "@/app/providers";
import { capabilityStatuses } from "@/lib/capability-status";
import { cn } from "@/lib/utils";

describe("foundation page", () => {
  it("composes class names through the shared utility", () => {
    expect(cn("base", false && "hidden", "active")).toBe("base active");
  });

  it("renders the temporary foundation screen and every capability status", () => {
    render(<Home />);

    expect(screen.getByRole("heading", { name: "ExperimentOS AI" })).toBeInTheDocument();
    expect(screen.getByText("Foundation preview")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("In progress")).toBeInTheDocument();
    expect(screen.getByText("Planned")).toBeInTheDocument();
    expect(screen.getByText("Future research")).toBeInTheDocument();
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
  });

  it("exposes every honest capability status through the central mapping", () => {
    expect(Object.values(capabilityStatuses).map((status) => status.label)).toEqual([
      "Completed",
      "In progress",
      "Planned",
      "Future research",
      "Unavailable",
    ]);
  });

  it("renders content inside the Query provider", () => {
    render(
      <Providers>
        <span>Provider ready</span>
      </Providers>,
    );

    expect(screen.getByText("Provider ready")).toBeInTheDocument();
  });
});
