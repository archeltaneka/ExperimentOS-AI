import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SourceDisclosure } from "@/components/source-disclosure";
import { StatusBadge } from "@/components/status-badge";

describe("shared UI accessibility", () => {
  it("renders a data-source label and explanatory text together", () => {
    render(
      <SourceDisclosure
        source={{
          kind: "deterministic_fixture",
          label: "Development fixture",
          detail: "Fixed portfolio development data; not live telemetry.",
        }}
      />,
    );

    expect(screen.getByText("Development fixture")).toBeInTheDocument();
    expect(screen.getByText(/not live telemetry/i)).toBeInTheDocument();
  });

  it("renders capability status as text rather than colour alone", () => {
    render(<StatusBadge status="planned" />);

    expect(screen.getByText("Planned")).toBeInTheDocument();
  });
});
