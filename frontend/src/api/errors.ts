import { isObj, obj, str } from "@/lib/unknown";

/** The API error envelope `{error: {code, message, details, request_id}}` as a thrown value. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;
  readonly requestId: string | undefined;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}, requestId?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }

  static fromBody(status: number, body: unknown, requestId?: string | null): ApiError {
    if (isObj(body) && isObj(body.error)) {
      const e = body.error;
      return new ApiError(status, str(e.code) ?? fallbackCode(status), str(e.message) ?? "", obj(e.details), str(e.request_id) ?? requestId ?? undefined);
    }
    if (isObj(body) && Array.isArray(body.detail)) {
      return new ApiError(status, "validation_failed", "", { fields: body.detail }, requestId ?? undefined);
    }
    return new ApiError(status, fallbackCode(status), "", {}, requestId ?? undefined);
  }
}

function fallbackCode(status: number): string {
  if (status === 0) return "network";
  if (status === 401) return "auth_required";
  if (status === 403) return "forbidden";
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status === 429) return "rate_limited";
  if (status >= 500) return "server_error";
  return "unknown";
}

export function isApiError(e: unknown, code?: string): e is ApiError {
  return e instanceof ApiError && (code === undefined || e.code === code);
}

export function isNotFound(e: unknown): boolean {
  return e instanceof ApiError && (e.status === 404 || e.code === "not_found");
}
