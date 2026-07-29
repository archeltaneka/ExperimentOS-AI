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

  it("renders the landing page", async () => {
    render(await Home());

    expect(screen.getByRole("heading", { name: "Evidence-backed answers for product experiments." })).toBeInTheDocument();
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
