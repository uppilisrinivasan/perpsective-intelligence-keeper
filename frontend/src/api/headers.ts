/**
 * Request headers shared by the typed client, chat streaming and raw action calls.
 * The role picker store pushes the viewer here; /status pushes the auth mode.
 */
export type ViewerRole = "maintainer" | "reviewer" | "contributor" | "judge";

let viewerRole: ViewerRole = "judge";
let viewerPerson: string | null = null;
let authMode = "none";

export function setViewer(role: ViewerRole, personId: string | null): void {
  viewerRole = role;
  viewerPerson = personId;
}
export function setAuthMode(mode: string | null | undefined): void {
  authMode = mode ?? "none";
}
export function getAuthMode(): string {
  return authMode;
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  for (const part of document.cookie.split(";")) {
    const [k, ...rest] = part.trim().split("=");
    if (k === name) return decodeURIComponent(rest.join("="));
  }
  return null;
}

function requestId(): string {
  const c = globalThis.crypto;
  if (c && "randomUUID" in c) return `req_${c.randomUUID().replace(/-/g, "").slice(0, 20)}`;
  return `req_${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
}

export function buildHeaders(method: string): Record<string, string> {
  const h: Record<string, string> = {
    "X-Keeper-Role": viewerRole,
    "X-Request-ID": requestId(),
  };
  if (viewerPerson) h["X-Keeper-Person"] = viewerPerson;
  if (authMode === "access_code" && !["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase())) {
    const csrf = readCookie("keeper_csrf");
    if (csrf) h["X-Keeper-CSRF"] = csrf;
  }
  return h;
}
