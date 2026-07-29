import type { RagAnswer } from "@/types/domain";

export const askFixture: RagAnswer = {
  answer: "The fixture indicates a 4.2% lift in payment completion and supports a controlled rollout.",
  citations: [{ experimentId: "8bb4bf4d-a372-4b6e-93a5-0dd9ad7c8750", documentId: "payment-report", documentName: "Payment recommendation report", quote: "Payment completion increased by 4.2%.", section: "Results", score: 0.92 }],
  retrievedChunks: [{ experimentId: "8bb4bf4d-a372-4b6e-93a5-0dd9ad7c8750", documentId: "payment-report", documentName: "Payment recommendation report", text: "Payment completion increased by 4.2% with no material checkout-error increase.", section: "Results", similarity: 0.92 }],
  requestMetadata: { intent: "decision_support", requiredAgents: ["retrieval", "experiment_analysis", "decision"], approvalStatus: "pending", workflow: { trace: [{ node: "retrieval", event: "completed", at: "2026-07-01T10:00:02Z" }], metrics: { retrieval: { retrieved_chunks: 1, average_similarity: 0.92 } } } },
};
