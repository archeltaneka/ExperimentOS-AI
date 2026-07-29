import { describe, expect, it, vi } from "vitest";

import { createServices } from "@/services/adapters";
import { ApiError } from "@/services/errors";
import { HttpAskService } from "@/services/http-ask-service";
import { askQueryKeys } from "@/services/query-keys";
import { mapAskResponse } from "@/services/transport/ask";

const knownExperimentId = "8bb4bf4d-a372-4b6e-93a5-0dd9ad7c8750";

describe("typed data layer", () => {
  it("maps the verified /ask transport response without exposing raw dictionaries", () => {
    const answer = mapAskResponse({
      answer: "Treatment improved payment completion.",
      citations: [
        {
          experiment_id: knownExperimentId,
          document_id: "report-1",
          quote: "Completion rose by 4.2%.",
          section: "Results",
          metadata: { document_name: "Experiment report" },
        },
      ],
      retrieved_chunks: [
        {
          experiment_id: knownExperimentId,
          document_id: "report-1",
          document_name: "Experiment report",
          chunk_text: "Completion rose by 4.2%.",
          similarity: 0.92,
          metadata: { section: "Results" },
        },
      ],
      retrieval_metrics: { retrieved_chunks: 1, average_similarity: 0.92 },
      llm_metrics: { model: "agent-workflow", latency_ms: 0 },
      intent: "decision_support",
      required_agents: ["retrieval", "decision"],
      agent_trace: [{ node: "retrieval", event: "completed" }],
      agent_metrics: { retrieval: { retrieved_chunks: 1 } },
      approval_status: "pending",
    });

    expect(answer.citations[0]).toMatchObject({ documentName: "Experiment report", score: 0.92 });
    expect(answer.retrievedChunks[0]).toMatchObject({ similarity: 0.92, section: "Results" });
    expect(answer.requestMetadata).toMatchObject({ intent: "decision_support", approvalStatus: "pending" });
  });

  it("returns deterministic fixture ask responses", async () => {
    const services = createServices({ dataMode: "mock" });
    const request = { question: "What happened?", experimentId: knownExperimentId, topK: 3 };

    await expect(services.ask.ask(request)).resolves.toEqual(await services.ask.ask(request));
  });

  it("returns deterministic experiment summaries and a known detail", async () => {
    const services = createServices({ dataMode: "mock" });
    const experiments = await services.experiments.list();

    expect(experiments.map((experiment) => experiment.status)).toEqual(
      expect.arrayContaining(["completed", "running", "inconclusive", "stopped"]),
    );
    await expect(services.experiments.getById(knownExperimentId)).resolves.toMatchObject({
      id: knownExperimentId,
      status: "completed",
    });
  });

  it("normalizes missing fixture experiment details", async () => {
    const services = createServices({ dataMode: "mock" });

    await expect(services.experiments.getById("missing")).rejects.toMatchObject({
      code: "not_found",
      status: 404,
    });
  });

  it("returns stable evaluation history and honest capability statuses", async () => {
    const services = createServices({ dataMode: "mock" });
    const [summary, history] = await Promise.all([
      services.evaluations.getSummary(),
      services.evaluations.getHistory(),
    ]);

    expect(summary.metrics).toHaveLength(3);
    expect(history).toHaveLength(4);
    expect(
      summary.capabilities.filter((capability) =>
        ["Sequential testing", "Bayesian A/B testing", "Double Machine Learning"].includes(capability.name),
      ),
    ).not.toEqual(expect.arrayContaining([expect.objectContaining({ status: "completed" })]));
  });

  it("preserves completed, active, and future roadmap states", async () => {
    const phases = await createServices({ dataMode: "mock" }).roadmap.list();

    expect(phases.map((phase) => phase.status)).toEqual(
      expect.arrayContaining(["completed", "in_progress", "planned"]),
    );
  });

  it("uses explicit adapter selection and fails invalid configuration", () => {
    expect(createServices({ dataMode: "mock" }).ask.source.kind).toBe("deterministic_fixture");
    expect(() => createServices({ dataMode: "invalid" as "mock" })).toThrow(/NEXT_PUBLIC_DATA_MODE/);
    expect(() => createServices({ dataMode: "live" })).toThrow(/NEXT_PUBLIC_API_BASE_URL/);
  });

  it("normalizes HTTP validation, server, timeout, and abort failures", async () => {
    const validationFetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "question must not be empty" }), { status: 422 }),
    );
    const validationService = new HttpAskService({ baseUrl: "http://api.test", fetch: validationFetch });
    await expect(validationService.ask({ question: "Q", experimentId: knownExperimentId, topK: 3 })).rejects.toMatchObject({
      code: "validation",
      status: 422,
    });

    const timeoutFetch = vi.fn().mockRejectedValue(new DOMException("Aborted", "AbortError"));
    const timeoutService = new HttpAskService({ baseUrl: "http://api.test", fetch: timeoutFetch });
    await expect(timeoutService.ask({ question: "Q", experimentId: knownExperimentId, topK: 3 })).rejects.toMatchObject({
      code: "aborted",
    });

    expect(new ApiError({ code: "server", message: "safe", diagnostic: "detail" }).userMessage).toBe("The service could not complete the request.");
  });

  it("keeps query keys stable and parameterized", () => {
    expect(askQueryKeys.experimentDetail(knownExperimentId)).toEqual([
      "experiments",
      "detail",
      knownExperimentId,
    ]);
  });
});
