import type { z } from "zod";

/** Browser → FastAPI. Never call model/provider APIs from the frontend. */
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Structured job-source error: {code, message, retryable} (PRD §65). */
export function errorCode(error: unknown): string | null {
  if (!(error instanceof ApiError)) return null;
  const detail = error.detail as { code?: unknown } | undefined;
  return typeof detail?.code === "string" ? detail.code : null;
}

function errorMessage(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    const message = (detail as { message: unknown }).message;
    if (typeof message === "string") return message;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown; loc?: unknown[] };
    const field = Array.isArray(first.loc) ? first.loc.at(-1) : undefined;
    if (typeof first.msg === "string") return field ? `${String(field)}: ${first.msg}` : first.msg;
  }
  return `Request failed (${status})`;
}

export async function apiFetch<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    // JSON bodies are strings; FormData (file uploads) must set its own multipart boundary.
    const headers = new Headers(init?.headers);
    if (typeof init?.body === "string" && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    response = await fetch(`${API_BASE_URL}/api/v1${path}`, { ...init, headers });
  } catch {
    throw new ApiError("Cannot reach the RoleRadarAI API", 0);
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail;
    throw new ApiError(errorMessage(detail, response.status), response.status, detail);
  }
  return schema.parse(body);
}
