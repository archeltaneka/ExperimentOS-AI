import type { ExperimentService } from "@/services/contracts";
import { ApiError, normalizeError } from "@/services/errors";
import type { Experiment, ExperimentDetail } from "@/types/domain";

interface Options { baseUrl: string; fetch?: typeof globalThis.fetch; }
const source = { kind: "live_backend" as const, label: "Live backend" as const, detail: "Live experiment API" };
const fallback = { owner: { id: "", name: "", team: "" }, startedAt: "", primaryMetric: { name: "", value: 0, unit: "", direction: "neutral" as const }, decision: { status: "not_required" as const, recommendation: "", rationale: "" }, analysisStatus: "unavailable" as const, businessImpact: "unavailable" as const };

export class HttpExperimentService implements ExperimentService {
  readonly source = source;
  private readonly requestFetch: typeof globalThis.fetch;
  constructor(private readonly options: Options) { this.requestFetch = options.fetch ?? globalThis.fetch.bind(globalThis); }
  async list(): Promise<readonly Experiment[]> { return this.request<Experiment[]>("/experiments"); }
  async getById(id: string): Promise<ExperimentDetail> { return this.request<ExperimentDetail>(`/experiments/${id}`); }
  private async request<T extends Experiment | ExperimentDetail | Experiment[]>(path: string): Promise<T> {
    try {
      const response = await this.requestFetch(`${this.options.baseUrl.replace(/\/$/, "")}${path}`);
      if (!response.ok) throw new ApiError({ code: response.status === 404 ? "not_found" : "server", message: "Experiment request failed", status: response.status });
      const payload = await response.json() as unknown;
      return Array.isArray(payload)
        ? (payload.map(mapExperiment) as unknown as T)
        : (mapExperiment(payload) as T);
    } catch (error) { throw normalizeError(error); }
  }
}
function mapExperiment(value: unknown): ExperimentDetail {
  const item = value as Record<string, unknown>;
  const report = typeof item.report === "string"
    ? { source: "Live backend experiment report", executiveSummary: item.report }
    : undefined;
  return { ...fallback, id: String(item.id ?? ""), name: String(item.name ?? ""), status: String(item.status ?? "draft") as Experiment["status"], summary: String(item.description ?? ""), metrics: [], capabilities: [], report };
}
