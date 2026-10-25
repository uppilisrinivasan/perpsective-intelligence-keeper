import { ApiError } from "@/api/errors";
import { hasCopy, t, tDynamic } from "@/copy/t";
import { num, str } from "./unknown";

/** API error code → plain message (screens/08 §3). Strings live under errors.* in en.json. */
export function errorMessage(e: unknown, vars: Record<string, string> = {}): string {
  if (!(e instanceof ApiError)) return t("errors.unknown");
  const d = e.details;
  const values: Record<string, string | number> = {
    model: str(d.model_display) ?? str(d.model) ?? t("errors.theModel"),
    fallback: str(d.fallback_display) ?? str(d.fallback) ?? t("errors.anotherModel"),
    reason: str(d.reason) ?? e.message,
    n: num(d.retry_after) ?? num(d.retry_after_seconds) ?? 0,
    name: str(d.name) ?? str(d.person) ?? "",
    ...vars,
  };
  const key = `errors.${e.code}`;
  if (hasCopy(key)) return tDynamic(key, values);
  if (e.status >= 500) return t("errors.server");
  return t("errors.unknown");
}

export function errorCode(e: unknown): string | undefined {
  return e instanceof ApiError ? e.code : undefined;
}
