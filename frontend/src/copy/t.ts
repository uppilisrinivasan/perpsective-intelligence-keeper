import { IntlMessageFormat } from "intl-messageformat";
import messages from "./en.json";

/** Every user-facing string lives in en.json (docs/06-frontend/06-copy-guide.md). */
export type CopyKey = keyof typeof messages;
export type CopyVars = Record<string, string | number | boolean | null | undefined | Date>;

const LOCALE = "en";
const cache = new Map<string, IntlMessageFormat>();
const table: Record<string, string> = messages;

function compile(key: string): IntlMessageFormat | null {
  const hit = cache.get(key);
  if (hit) return hit;
  const source = table[key];
  if (source === undefined) return null;
  const fmt = new IntlMessageFormat(source, LOCALE, undefined, { ignoreTag: true });
  cache.set(key, fmt);
  return fmt;
}

/**
 * Formats a copy string with ICU MessageFormat (plurals: `{n, plural, one {# PR} other {# PRs}}`).
 * Missing variables render as an empty string rather than throwing, so a partial API object never
 * blanks a screen; the unit tests cover the plural and select forms.
 */
export function t(key: CopyKey, vars?: CopyVars): string {
  return format(key, vars);
}

/** For keys built at runtime (lanes, error codes, health states). Falls back to `fallback`. */
export function tDynamic(key: string, vars?: CopyVars, fallback?: CopyKey): string {
  if (key in table) return format(key, vars);
  if (fallback) return format(fallback, vars);
  return "";
}

export function hasCopy(key: string): boolean {
  return key in table;
}

function format(key: string, vars?: CopyVars): string {
  const fmt = compile(key);
  if (!fmt) return key;
  const values: Record<string, string | number | boolean | Date> = {};
  const names = argumentNames(table[key] ?? "");
  for (const name of names) {
    const v = vars?.[name];
    values[name] = v === null || v === undefined ? "" : v;
  }
  try {
    const out = fmt.format(values);
    return Array.isArray(out) ? out.join("") : String(out);
  } catch {
    return table[key] ?? key;
  }
}

const argCache = new Map<string, string[]>();
function argumentNames(source: string): string[] {
  const hit = argCache.get(source);
  if (hit) return hit;
  const names = new Set<string>();
  const re = /\{\s*([a-zA-Z_][\w]*)\s*(?:[,}])/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(source))) if (m[1]) names.add(m[1]);
  const list = [...names];
  argCache.set(source, list);
  return list;
}
