import type { RagAnswer } from "@/types/domain";
import type { AskSample } from "@/services/contracts";
import { paymentRecommendationExperiment } from "@/mock/experiments";

export const askFixture: RagAnswer = {
  answer: "The saved payment report records a 4.2% lift in payment completion with no material checkout-error increase [1]. These are descriptive fixture values, not a causal estimate. The recorded recommendation is a controlled rollout with guardrail monitoring; this sample answer does not authorize a rollout.",
  citations: [{ experimentId: "8bb4bf4d-a372-4b6e-93a5-0dd9ad7c8750", documentId: "payment-report", documentName: "Payment recommendation report", quote: "Payment completion increased by 4.2%.", section: "Results", score: 0.92 }],
  retrievedChunks: [{ experimentId: "8bb4bf4d-a372-4b6e-93a5-0dd9ad7c8750", documentId: "payment-report", documentName: "Payment recommendation report", text: "Payment completion increased by 4.2% with no material checkout-error increase.", section: "Results", similarity: 0.92 }],
  requestMetadata: { intent: "decision_support", requiredAgents: ["retrieval", "experiment_analysis", "decision"], approvalStatus: "pending", workflow: { trace: [{ node: "retrieval", event: "completed", at: "2026-07-01T10:00:02Z" }], metrics: { retrieval: { retrieved_chunks: 1, average_similarity: 0.92 } } } },
};

const limitations = paymentRecommendationExperiment.report!.limitations!;
export const askSamples: readonly (AskSample & { answer: RagAnswer })[] = [
  {
    experimentId: paymentRecommendationExperiment.id,
    question: "What evidence supported the payment experiment recommendation?",
    answer: askFixture,
  },
  {
    experimentId: paymentRecommendationExperiment.id,
    question: "What are the limitations of this payment experiment record?",
    answer: {
      answer: `${limitations} [1] The saved record cannot establish causal impact or authorize a rollout.`,
      citations: [{ experimentId: paymentRecommendationExperiment.id, documentId: "payment-report", documentName: "Payment recommendation report", quote: limitations, section: "Limitations" }],
      retrievedChunks: [{ experimentId: paymentRecommendationExperiment.id, documentId: "payment-report", documentName: "Payment recommendation report", text: limitations, section: "Limitations" }],
      requestMetadata: { intent: "evidence_review", requiredAgents: [], approvalStatus: "pending" },
    },
  },
];
