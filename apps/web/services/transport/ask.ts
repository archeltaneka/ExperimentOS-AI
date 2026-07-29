import type { Citation, RagAnswer, RetrievedChunk, RequestMetadata } from "@/types/domain";

export interface AskRequestTransport { question: string; experiment_id: string; top_k: number; }
export interface AskResponseTransport {
  answer: string; citations: unknown[]; retrieved_chunks: unknown[]; retrieval_metrics: Record<string, unknown>; llm_metrics: Record<string, unknown>;
  prompt_metadata?: { prompt_id: string; prompt_version: string } | null; intent?: string | null; required_agents?: string[];
  agent_trace?: unknown[]; agent_metrics?: Record<string, unknown>; approval_status?: string | null;
}

const record = (value: unknown): Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const string = (value: unknown): string | undefined => typeof value === "string" ? value : undefined;
const number = (value: unknown): number | undefined => typeof value === "number" && Number.isFinite(value) ? value : undefined;

export function mapAskRequest(request: { question: string; experimentId: string; topK?: number }): AskRequestTransport {
  return { question: request.question, experiment_id: request.experimentId, top_k: request.topK ?? 5 };
}

export function mapAskResponse(response: AskResponseTransport): RagAnswer {
  const chunks = response.retrieved_chunks.map(mapChunk);
  return { answer: response.answer, citations: response.citations.map((citation) => mapCitation(citation, chunks)), retrievedChunks: chunks, requestMetadata: mapMetadata(response) };
}

function mapChunk(value: unknown): RetrievedChunk {
  const item = record(value); const metadata = record(item.metadata);
  return { experimentId: string(item.experiment_id) ?? "", documentId: string(item.document_id) ?? "", documentName: string(item.document_name) ?? string(metadata.document_name) ?? "Untitled document", text: string(item.chunk_text) ?? string(item.content) ?? "", similarity: number(item.similarity) ?? number(item.score), section: string(metadata.section), experimentName: string(item.experiment_name), chunkType: string(metadata.chunk_type) };
}
function mapCitation(value: unknown, chunks: readonly RetrievedChunk[]): Citation {
  const item = record(value); const metadata = record(item.metadata); const documentId = string(item.document_id);
  const matching = chunks.find((chunk) => chunk.documentId === documentId);
  return { experimentId: string(item.experiment_id) ?? matching?.experimentId ?? "", documentId, documentName: string(item.document) ?? string(metadata.document_name) ?? matching?.documentName ?? "Untitled document", quote: string(item.quote), section: string(item.section) ?? string(metadata.section), score: number(item.similarity) ?? matching?.similarity };
}
function mapMetadata(response: AskResponseTransport): RequestMetadata {
  const retrieval = response.retrieval_metrics;
  const llm = response.llm_metrics;
  return { intent: response.intent ?? undefined, requiredAgents: response.required_agents ?? [], approvalStatus: response.approval_status ?? undefined, prompt: response.prompt_metadata ? { id: response.prompt_metadata.prompt_id, version: response.prompt_metadata.prompt_version } : undefined, model: string(llm.model), latencyMs: number(llm.latency_ms), retrievedChunkCount: number(retrieval.retrieved_chunks), averageSimilarity: number(retrieval.average_similarity), workflow: response.agent_trace || response.agent_metrics ? { trace: response.agent_trace?.map((item) => { const event = record(item); return { node: string(event.node) ?? "unknown", event: string(event.event) ?? "unknown", at: string(event.at) }; }) ?? [], metrics: response.agent_metrics ?? {} } : undefined };
}
