import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const pathname = "/roadmap";
vi.mock("next/navigation", () => ({ usePathname: () => pathname }));

import { ApplicationShell } from "@/components/application-shell";

describe("application shell", () => {
  it("marks the active route and returns focus after Escape closes mobile navigation", () => {
    render(<ApplicationShell><p>Route content</p></ApplicationShell>);

    expect(screen.getByRole("link", { name: "Roadmap" })).toHaveAttribute("aria-current", "page");
    const trigger = screen.getByRole("button", { name: "Open navigation" });
    fireEvent.click(trigger);
    expect(screen.getByRole("dialog", { name: "Navigation" })).toBeVisible();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(trigger).toHaveFocus();
  });
});
