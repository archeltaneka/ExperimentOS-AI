import type { AskRequest, AskService } from "@/services/contracts";
import { ApiError, normalizeError } from "@/services/errors";
import { mapAskRequest, mapAskResponse, type AskResponseTransport } from "@/services/transport/ask";
import type { DataSource, RagAnswer } from "@/types/domain";

interface HttpAskServiceOptions { baseUrl: string; fetch?: typeof globalThis.fetch; timeoutMs?: number; }
const liveSource: DataSource = { kind: "live_backend", label: "Live backend", detail: "POST /ask" };

export class HttpAskService implements AskService {
  readonly source = liveSource; private readonly requestFetch: typeof globalThis.fetch; private readonly timeoutMs: number;
  constructor(private readonly options: HttpAskServiceOptions) { this.requestFetch = options.fetch ?? globalThis.fetch; this.timeoutMs = options.timeoutMs ?? 15_000; }
  async ask(request: AskRequest): Promise<RagAnswer> {
    const controller = new AbortController(); const timeout = setTimeout(() => controller.abort("timeout"), this.timeoutMs);
    const abort = () => controller.abort("aborted"); request.signal?.addEventListener("abort", abort, { once: true });
    try {
      const response = await this.requestFetch(`${this.options.baseUrl.replace(/\/$/, "")}/ask`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(mapAskRequest(request)), signal: controller.signal });
      if (!response.ok) throw await responseError(response);
      const payload: unknown = await response.json();
      if (!isAskResponse(payload)) throw new ApiError({ code: "invalid_response", message: "Invalid /ask response" });
      return mapAskResponse(payload);
    } catch (error) {
      if (controller.signal.aborted && controller.signal.reason === "timeout") throw new ApiError({ code: "timeout", message: "Request timed out" });
      throw normalizeError(error);
    } finally { clearTimeout(timeout); request.signal?.removeEventListener("abort", abort); }
  }
}
async function responseError(response: Response): Promise<ApiError> {
  const payload: unknown = await response.json().catch(() => undefined); const detail = typeof payload === "object" && payload !== null && "detail" in payload ? String(payload.detail) : undefined;
  if (response.status === 404) return new ApiError({ code: "not_found", message: "Experiment not found", status: 404, diagnostic: detail });
  if (response.status === 400 || response.status === 422) return new ApiError({ code: "validation", message: "Invalid ask request", status: response.status, diagnostic: detail });
  return new ApiError({ code: "server", message: "Ask request failed", status: response.status, diagnostic: detail });
}
function isAskResponse(value: unknown): value is AskResponseTransport { return typeof value === "object" && value !== null && "answer" in value && "citations" in value && "retrieved_chunks" in value && "retrieval_metrics" in value && "llm_metrics" in value && typeof (value as Record<string, unknown>).answer === "string" && Array.isArray((value as Record<string, unknown>).citations) && Array.isArray((value as Record<string, unknown>).retrieved_chunks); }
