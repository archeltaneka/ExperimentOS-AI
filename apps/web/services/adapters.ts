import { HttpAskService } from "@/services/http-ask-service";
import { LocalRoadmapService, MockAskService, MockEvaluationService, MockExperimentService } from "@/services/mock-services";
import type { Services } from "@/services/contracts";
import { ApiError } from "@/services/errors";

export type DataMode = "mock" | "live";
export interface ServiceConfiguration { dataMode: DataMode; apiBaseUrl?: string; fetch?: typeof globalThis.fetch; }
export function getServiceConfiguration(
  env: { NEXT_PUBLIC_DATA_MODE?: string; NEXT_PUBLIC_API_BASE_URL?: string } = {
    NEXT_PUBLIC_DATA_MODE: process.env.NEXT_PUBLIC_DATA_MODE,
    NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
  },
): ServiceConfiguration {
  const dataMode = env.NEXT_PUBLIC_DATA_MODE ?? "mock";
  if (dataMode !== "mock" && dataMode !== "live") throw new ApiError({ code: "configuration", message: "NEXT_PUBLIC_DATA_MODE must be 'mock' or 'live'.", diagnostic: dataMode });
  if (dataMode === "live" && !env.NEXT_PUBLIC_API_BASE_URL?.trim()) throw new ApiError({ code: "configuration", message: "NEXT_PUBLIC_API_BASE_URL is required when NEXT_PUBLIC_DATA_MODE=live." });
  return { dataMode, apiBaseUrl: env.NEXT_PUBLIC_API_BASE_URL };
}
export function createServices(configuration: ServiceConfiguration = getServiceConfiguration()): Services {
  if (configuration.dataMode !== "mock" && configuration.dataMode !== "live") throw new ApiError({ code: "configuration", message: "NEXT_PUBLIC_DATA_MODE must be 'mock' or 'live'.", diagnostic: configuration.dataMode });
  if (configuration.dataMode === "live" && !configuration.apiBaseUrl?.trim()) throw new ApiError({ code: "configuration", message: "NEXT_PUBLIC_API_BASE_URL is required when NEXT_PUBLIC_DATA_MODE=live." });
  return { ask: configuration.dataMode === "live" ? new HttpAskService({ baseUrl: configuration.apiBaseUrl!, fetch: configuration.fetch }) : new MockAskService(), experiments: new MockExperimentService(), evaluations: new MockEvaluationService(), roadmap: new LocalRoadmapService() };
}
