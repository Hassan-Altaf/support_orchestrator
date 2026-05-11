/**
 * Typed fetch wrapper for the Support Orchestrator API.
 *
 * Resolves the base URL from `VITE_API_BASE_URL`; falls back to `""` so that
 * Vite's dev-server proxy at `/api/*` -> `http://localhost:8000` handles
 * cross-origin during development.
 */

import type {
  ErrorResponse,
  HealthResponse,
  ProcessRequest,
  TicketProcessingResult,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  status: number;
  body: ErrorResponse | null;

  constructor(status: number, body: ErrorResponse | null, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

async function request<T>(
  path: string,
  init: RequestInit & { jsonBody?: unknown } = {},
): Promise<T> {
  const { jsonBody, headers, ...rest } = init;
  const response = await fetch(`${BASE_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...headers,
    },
    body: jsonBody !== undefined ? JSON.stringify(jsonBody) : init.body,
  });

  if (!response.ok) {
    let body: ErrorResponse | null = null;
    try {
      body = (await response.json()) as ErrorResponse;
    } catch {
      // body wasn't JSON; leave null
    }
    const detail = body?.detail ?? body?.error ?? response.statusText;
    throw new ApiError(response.status, body, `${response.status}: ${detail}`);
  }

  return (await response.json()) as T;
}

export const api = {
  health: () => request<HealthResponse>("/api/v1/health"),

  processSupport: (payload: ProcessRequest) =>
    request<TicketProcessingResult>("/api/v1/support/process", {
      method: "POST",
      jsonBody: payload,
    }),
};
