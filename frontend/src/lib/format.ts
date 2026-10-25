import { t } from "@/copy/t";

/** Formatting with Intl and the browser locale (docs/06-frontend/02-design-system.md §4). */
const locale = typeof navigator !== "undefined" ? navigator.language : undefined;

let demoNow: number | null = null;
/** In demo mode relative dates are relative to the demo clock from /status. */
export function setDemoNow(iso: string | null | undefined): void {
  const v = iso ? Date.parse(iso) : NaN;
  demoNow = Number.isFinite(v) ? v : null;
}
export function isDemoClock(): boolean {
  return demoNow !== null;
}
export function now(): number {
  return demoNow ?? Date.now();
}

const nf = new Intl.NumberFormat(locale);
const nf1 = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
const nf2 = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 });

export function formatNumber(n: number | null | undefined, digits: 0 | 1 | 2 = 0): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return t("format.none");
  return (digits === 0 ? nf : digits === 1 ? nf1 : nf2).format(digits === 0 ? Math.round(n) : n);
}

/** 0.64 → "64%" (whole numbers in the UI). */
export function formatPercent(fraction: number | null | undefined): string {
  if (fraction === null || fraction === undefined || !Number.isFinite(fraction)) return t("format.none");
  return t("format.percent", { value: Math.round(fraction * 100) });
}

/** "(48–72)" from fractions. */
export function formatInterval(low: number | null | undefined, high: number | null | undefined): string {
  if (low === null || low === undefined || high === null || high === undefined) return "";
  return t("format.interval", { low: Math.round(low * 100), high: Math.round(high * 100) });
}

/** Signed percentage points: +31 points. */
export function formatPoints(fraction: number | null | undefined): string {
  if (fraction === null || fraction === undefined || !Number.isFinite(fraction)) return t("format.none");
  const v = Math.round(fraction * 100);
  return t("format.points", { value: v > 0 ? `+${v}` : String(v) });
}

const money = new Intl.NumberFormat(locale, { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const moneyFine = new Intl.NumberFormat(locale, { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 4 });

/** $0.03, or "< $0.01". */
export function formatMoney(usd: number | null | undefined, fine = false): string {
  if (usd === null || usd === undefined || !Number.isFinite(usd)) return t("format.none");
  if (usd > 0 && usd < 0.01 && !fine) return t("format.money.lessThan", { amount: money.format(0.01) });
  return (fine ? moneyFine : money).format(usd);
}

/** Minutes → "about 55 min" or "about 2 h 10 min". */
export function formatMinutes(minutes: number | null | undefined, approx = true): string {
  if (minutes === null || minutes === undefined || !Number.isFinite(minutes)) return t("format.none");
  const m = Math.max(0, Math.round(minutes));
  const h = Math.floor(m / 60);
  const rest = m % 60;
  const core = h > 0 ? t("format.hoursMinutes", { h, m: rest }) : t("format.minutes", { m });
  return approx ? t("format.about", { value: core }) : core;
}

/** Milliseconds → "2 s", "1 min 5 s". */
export function formatDurationMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms)) return t("format.none");
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return t("format.seconds", { s });
  return t("format.minutesSeconds", { m: Math.floor(s / 60), s: s % 60 });
}

const dateShort = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" });
const dateLong = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short", year: "numeric" });
const dateTime = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });
const monthYear = new Intl.DateTimeFormat(locale, { month: "short", year: "numeric" });
const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });

function toMs(at: string | number | Date | null | undefined): number | null {
  if (at === null || at === undefined) return null;
  const v = at instanceof Date ? at.getTime() : typeof at === "number" ? at : Date.parse(at);
  return Number.isFinite(v) ? v : null;
}

export function formatDate(at: string | number | Date | null | undefined, withYear = false): string {
  const v = toMs(at);
  if (v === null) return t("format.none");
  const sameYear = new Date(v).getFullYear() === new Date(now()).getFullYear();
  return (withYear || !sameYear ? dateLong : dateShort).format(v);
}
export function formatDateTime(at: string | number | Date | null | undefined): string {
  const v = toMs(at);
  return v === null ? t("format.none") : dateTime.format(v);
}
export function formatMonthYear(at: string | number | Date | null | undefined): string {
  const v = toMs(at);
  return v === null ? t("format.none") : monthYear.format(v);
}

/** Relative within 7 days ("2 days ago"), the date otherwise. */
export function formatRelative(at: string | number | Date | null | undefined, base: number = now()): string {
  const v = toMs(at);
  if (v === null) return t("format.none");
  // On the demo clock, Keeper's own runs happen after the frozen "now" of the demo world; show them as just now.
  const diff = isDemoClock() && base === now() ? Math.min(0, v - base) : v - base;
  const abs = Math.abs(diff);
  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (abs < minute) return rtf.format(0, "second");
  if (abs < hour) return rtf.format(Math.round(diff / minute), "minute");
  if (abs < day) return rtf.format(Math.round(diff / hour), "hour");
  if (abs < 7 * day) return rtf.format(Math.round(diff / day), "day");
  return formatDate(v);
}

export function personName(p: { display_name?: string | null; login?: string | null } | null | undefined): string {
  if (!p) return t("people.unknown");
  return p.display_name || p.login || t("people.unknown");
}

/** "auth_required" → used for keys; humanises snake_case only as a last resort for unknown enum values. */
export function humanise(key: string | null | undefined): string {
  if (!key) return "";
  const s = key.replace(/[_-]+/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}
