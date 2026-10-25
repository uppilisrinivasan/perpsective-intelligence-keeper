/**
 * Readers for the API fields typed as free-form objects in the OpenAPI document
 * (Card.data, PracticeFeedback.reveal, FidelityRunOut.holdout, …). They never invent values:
 * a missing or mistyped field reads as undefined and the screen shows its empty state.
 */
export type Obj = Record<string, unknown>;

export function isObj(v: unknown): v is Obj {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}
export function obj(v: unknown): Obj {
  return isObj(v) ? v : {};
}
export function str(v: unknown): string | undefined {
  return typeof v === "string" ? v : typeof v === "number" ? String(v) : undefined;
}
export function num(v: unknown): number | undefined {
  return typeof v === "number" && Number.isFinite(v) ? v : undefined;
}
export function bool(v: unknown): boolean | undefined {
  return typeof v === "boolean" ? v : undefined;
}
export function arr(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}
export function objs(v: unknown): Obj[] {
  return arr(v).filter(isObj);
}
export function strs(v: unknown): string[] {
  return arr(v).filter((x): x is string => typeof x === "string");
}
export function pick(o: Obj, ...keys: string[]): unknown {
  for (const k of keys) if (o[k] !== undefined && o[k] !== null) return o[k];
  return undefined;
}
