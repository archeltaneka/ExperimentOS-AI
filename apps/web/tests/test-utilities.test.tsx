import { useQuery } from "@tanstack/react-query";
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { createTestQueryClient, renderWithProviders } from "@/tests/render";

function QueryProbe({ label }: Readonly<{ label: string }>) {
  const query = useQuery({ queryKey: ["probe"], queryFn: async () => label });
  return <output>{query.data ?? "loading"}</output>;
}

describe("frontend test utilities", () => {
  it("creates isolated query clients with retries disabled", async () => {
    const first = createTestQueryClient();
    const second = createTestQueryClient();

    first.setQueryData(["probe"], "first");
    expect(second.getQueryData(["probe"])).toBeUndefined();
    expect(first.getDefaultOptions().queries?.retry).toBe(false);
  });

  it("renders each component with an explicitly supplied isolated client", async () => {
    const queryClient = createTestQueryClient();
    renderWithProviders(<QueryProbe label="fixture result" />, { queryClient });

    expect(await screen.findByText("fixture result")).toBeInTheDocument();
  });
});
