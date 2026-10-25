import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "./schema";
import { ApiError } from "./errors";
import { buildHeaders } from "./headers";

/** Typed client for /api/v1 (same origin; Vite proxies /api in development). */
export const api = createClient<paths>({
  baseUrl: typeof window !== "undefined" ? window.location.origin : "",
  // Resolve fetch at call time (lets tests stub it; keeps one code path for the browser).
  fetch: (input: Request) => globalThis.fetch(input),
});

const authListeners = new Set<() => void>();
/** Called when any request answers 401 auth_required (cloud mode without a session). */
export function onAuthRequired(listener: () => void): () => void {
  authListeners.add(listener);
  return () => authListeners.delete(listener);
}
export function notifyAuthRequired(): void {
  authListeners.forEach((l) => l());
}

const headerMiddleware: Middleware = {
  onRequest({ request }) {
    for (const [k, v] of Object.entries(buildHeaders(request.method))) request.headers.set(k, v);
    return request;
  },
  onResponse({ response }) {
    if (response.status === 401) notifyAuthRequired();
    return response;
  },
};
api.use(headerMiddleware);

interface FetchResult<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/** Awaits an openapi-fetch call and returns data, or throws ApiError from the error envelope. */
export async function call<T>(request: Promise<FetchResult<T>>): Promise<T> {
  let result: FetchResult<T>;
  try {
    result = await request;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError(0, "network", e instanceof Error ? e.message : "");
  }
  const { data, error, response } = result;
  if (!response.ok || error !== undefined) {
    throw ApiError.fromBody(response.status, error, response.headers.get("x-request-id"));
  }
  return data as T;
}

/**
 * A raw same-origin request for endpoints named by the server at runtime (assistant action cards).
 * Only paths under /api/v1/ are allowed.
 */
export async function rawRequest(method: string, path: string, body?: unknown): Promise<unknown> {
  if (!path.startsWith("/api/v1/") || path.includes("..")) {
    throw new ApiError(400, "validation_failed", "");
  }
  const m = method.toUpperCase();
  let res: Response;
  try {
    res = await fetch(path, {
      method: m,
      credentials: "same-origin",
      headers: { ...buildHeaders(m), ...(body !== undefined ? { "Content-Type": "application/json" } : {}) },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    throw new ApiError(0, "network", e instanceof Error ? e.message : "");
  }
  const text = await res.text();
  let parsed: unknown = undefined;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }
  if (res.status === 401) notifyAuthRequired();
  if (!res.ok) throw ApiError.fromBody(res.status, parsed, res.headers.get("x-request-id"));
  return parsed;
}

/** Same-origin URL helpers for things the browser fetches directly (images, downloads, streams). */
export const urls = {
  avatar: (personId: string) => `/api/v1/avatars/${encodeURIComponent(personId)}.svg`,
  jobEvents: (jobId: string) => `/api/v1/jobs/${encodeURIComponent(jobId)}/events`,
  fixPatch: (fixId: string) => `/api/v1/fixes/${encodeURIComponent(fixId)}/patch`,
  lensExport: (lensId: string) => `/api/v1/lenses/${encodeURIComponent(lensId)}/export`,
  chatMessages: (threadId: string) => `/api/v1/chat/threads/${encodeURIComponent(threadId)}/messages`,
  apiDocs: "/api/docs",
};

/**
 * Downloads a same-origin file with Keeper's headers (role, person, CSRF), which a plain <a download> can't send.
 * The filename comes from Content-Disposition when present.
 */
export async function downloadWithHeaders(path: string, fallbackName: string): Promise<void> {
  const res = await fetch(path, { credentials: "same-origin", headers: buildHeaders("GET") });
  if (res.status === 401) notifyAuthRequired();
  if (!res.ok) {
    const body: unknown = await res.json().catch(() => null);
    throw ApiError.fromBody(res.status, body, res.headers.get("x-request-id"));
  }
  const disposition = res.headers.get("content-disposition") ?? "";
  const name = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition)?.[1];
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name ? decodeURIComponent(name) : fallbackName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
