import { describe, expect, it } from "vitest";

import { navigationItems } from "@/lib/navigation";

describe("navigation metadata", () => {
  it("defines every MVP route in one place", () => {
    expect(navigationItems.map((item) => item.href)).toEqual([
      "/",
      "/ask-experiment",
      "/experiment-explorer",
      "/evaluation-dashboard",
      "/roadmap",
    ]);
    expect(navigationItems.every((item) => item.description && item.icon)).toBe(true);
  });
});
