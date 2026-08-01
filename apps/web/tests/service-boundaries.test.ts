import { describe, expect, it, vi } from "vitest";

import { createServices } from "@/services/adapters";
import { HttpAskService } from "@/services/http-ask-service";
import { HttpExperimentService } from "@/services/http-experiment-service";

const experimentId = "8bb4bf4d-a372-4b6e-93a5-0dd9ad7c8750";

describe("service boundaries", () => {
  it("uses only verified live routes and preserves live source metadata", async () => {
    const fetch = vi.fn().mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const service = new HttpExperimentService({ baseUrl: "https://api.example.test/", fetch });

    await service.list();
    await service.getById(experimentId);

    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      "https://api.example.test/experiments",
      `https://api.example.test/experiments/${experimentId}`,
    ]);
    expect(service.source).toMatchObject({ kind: "live_backend", label: "Live backend" });
  });

  it("does not replace a live failure with fixture success", async () => {
    const fetch = vi.fn().mockRejectedValue(new TypeError("network unavailable"));
    const service = new HttpAskService({ baseUrl: "https://api.example.test", fetch });

    await expect(service.ask({ question: "What happened?", experimentId })).rejects.toMatchObject({
      code: "network",
    });
    expect(fetch).toHaveBeenCalledOnce();
  });

  it("centralizes source labels in adapters for mock and live modes", () => {
    expect(createServices({ dataMode: "mock" }).experiments.source).toMatchObject({
      kind: "deterministic_fixture",
      label: "Development fixture",
    });
    expect(
      createServices({ dataMode: "live", apiBaseUrl: "https://api.example.test" }).experiments.source,
    ).toMatchObject({ kind: "live_backend", label: "Live backend" });
  });
});
