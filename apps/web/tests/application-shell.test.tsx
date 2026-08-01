import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const pathname = "/roadmap";
vi.mock("next/navigation", () => ({ usePathname: () => pathname }));

import { ApplicationShell } from "@/components/application-shell";

afterEach(cleanup);

describe("application shell", () => {
  it("provides a skip link that targets the main content landmark", () => {
    render(<ApplicationShell><p>Route content</p></ApplicationShell>);

    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute(
      "href",
      "#main-content",
    );
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
  });

  it("marks the active route and returns focus after Escape closes mobile navigation", () => {
    render(<ApplicationShell><p>Route content</p></ApplicationShell>);

    expect(screen.getByRole("link", { name: "Roadmap" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "View demo" })).toHaveAttribute("href", "/");
    const trigger = screen.getByRole("button", { name: "Open navigation" });
    fireEvent.click(trigger);
    expect(screen.getByRole("dialog", { name: "Navigation" })).toBeVisible();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(trigger).toHaveFocus();
  });
});
