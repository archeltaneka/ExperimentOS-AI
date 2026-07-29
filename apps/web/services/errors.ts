export type ApiErrorCode = "network" | "timeout" | "aborted" | "invalid_response" | "validation" | "server" | "not_found" | "configuration" | "unsupported";

export class ApiError extends Error {
  readonly code: ApiErrorCode; readonly status?: number; readonly diagnostic?: string;
  constructor({ code, message, status, diagnostic }: { code: ApiErrorCode; message: string; status?: number; diagnostic?: string }) {
    super(message); this.name = "ApiError"; this.code = code; this.status = status; this.diagnostic = diagnostic;
  }
  get userMessage(): string {
    if (this.code === "network") return "Unable to reach the service.";
    if (this.code === "timeout") return "The request timed out.";
    if (this.code === "aborted") return "The request was cancelled.";
    if (this.code === "validation") return "Please check the request and try again.";
    if (this.code === "not_found") return "The requested item was not found.";
    if (this.code === "configuration") return "The application is not configured for this data source.";
    if (this.code === "unsupported") return "This capability is not connected yet.";
    if (this.code === "invalid_response") return "The service returned an unexpected response.";
    return "The service could not complete the request.";
  }
}

export function normalizeError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  if (error instanceof DOMException && error.name === "AbortError") return new ApiError({ code: "aborted", message: "Request aborted", diagnostic: error.message });
  if (error instanceof Error) return new ApiError({ code: "network", message: "Network request failed", diagnostic: error.message });
  return new ApiError({ code: "network", message: "Network request failed" });
}
