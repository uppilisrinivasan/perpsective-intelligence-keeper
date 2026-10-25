import { CheckCircle2, CircleMinus, CircleX } from "lucide-react";
import type { Criterion, Falsifier, Metric } from "@/api/types";
import { Disclosure } from "@/components/ui/Disclosure";
import { Markdown } from "@/components/ui/Markdown";
import { Tooltip } from "@/components/ui/Tooltip";
import { t } from "@/copy/t";
import { cx } from "@/lib/cx";
import { formatInterval, formatPercent, formatPoints } from "@/lib/format";

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v));
}

/** A value bar with an interval whisker and an optional target tick. Values are fractions (0–1). */
export function MetricBar({ label, metric, target, tone = "primary", tooltip }: { label: string; metric: Metric | null | undefined; target?: number; tone?: "primary" | "edge" | "baseline" | "shared"; tooltip?: string }) {
  const v = metric?.value;
  const color = tone === "edge" ? "bg-edge-solid" : tone === "baseline" ? "bg-baseline-solid" : tone === "shared" ? "bg-shared-solid" : "bg-primary";
  const n = metric?.n;
  return (
    <div className="grid grid-cols-1 items-center gap-x-3 gap-y-1 @md:grid-cols-[minmax(10rem,14rem)_1fr_minmax(7rem,auto)]">
      <div className="text-sm">
        {tooltip ? (
          <Tooltip content={tooltip}>
            <span tabIndex={0} className="k-term">
              {label}
            </span>
          </Tooltip>
        ) : (
          label
        )}
      </div>
      <div
        className="relative h-4 rounded-sm bg-surface-2"
        role="img"
        aria-label={t("metric.aria", { label, value: formatPercent(v), interval: formatInterval(metric?.low, metric?.high) })}
      >
        {v !== null && v !== undefined ? <div className={cx("absolute inset-y-0 left-0 rounded-sm", color)} style={{ width: `${clamp01(v) * 100}%` }} /> : null}
        {metric?.low !== null && metric?.low !== undefined && metric?.high !== null && metric?.high !== undefined ? (
          <div className="absolute top-1/2 h-0.5 -translate-y-1/2 bg-text" style={{ left: `${clamp01(metric.low) * 100}%`, width: `${Math.max(0, clamp01(metric.high) - clamp01(metric.low)) * 100}%` }} aria-hidden>
            <span className="absolute -top-1 left-0 h-2.5 w-0.5 bg-text" />
            <span className="absolute -top-1 right-0 h-2.5 w-0.5 bg-text" />
          </div>
        ) : null}
        {target !== undefined ? <div className="absolute -inset-y-1 w-0.5 bg-warning" style={{ left: `${clamp01(target) * 100}%` }} aria-hidden /> : null}
      </div>
      <div className="text-sm tabular">
        <span className="font-semibold">{formatPercent(v)}</span> <span className="text-muted">{formatInterval(metric?.low, metric?.high)}</span>
        {n !== null && n !== undefined && n < 10 ? <span className="ml-1 text-xs text-muted">{t("format.smallSample")}</span> : null}
      </div>
    </div>
  );
}

export interface CompareBarRow {
  key: string;
  label: string;
  metric: Metric | null | undefined;
  tone: "primary" | "edge" | "baseline" | "shared";
}

/** Substantive recall per system with 95% whiskers, then the paired difference with its interval. */
export function CompareBars({ title, rows, difference, tooltip }: { title: string; rows: CompareBarRow[]; difference?: Metric | null; tooltip?: string }) {
  const diffAbove = difference?.low !== null && difference?.low !== undefined && difference.low > 0;
  return (
    <section className="@container space-y-2.5" aria-label={title} data-tour="compare_bars">
      <h3 className="text-base font-semibold">{title}</h3>
      {rows.map((r) => (
        <MetricBar key={r.key} label={r.label} metric={r.metric} tone={r.tone} tooltip={tooltip} />
      ))}
      {difference && difference.value !== null && difference.value !== undefined ? (
        <p className="flex flex-wrap items-center gap-1.5 text-sm">
          {diffAbove ? <CheckCircle2 className="size-4 text-success" aria-hidden /> : <CircleX className="size-4 text-danger" aria-hidden />}
          {t("proof.difference", { value: formatPoints(difference.value), interval: formatInterval(difference.low, difference.high) })}
          <span className="text-muted">{diffAbove ? t("proof.aboveZero") : t("proof.notAboveZero")}</span>
        </p>
      ) : null}
    </section>
  );
}

function PassIcon({ passed }: { passed: boolean | null }) {
  if (passed === true) return <CheckCircle2 className="size-4 shrink-0 text-success" aria-hidden />;
  if (passed === false) return <CircleX className="size-4 shrink-0 text-danger" aria-hidden />;
  return <CircleMinus className="size-4 shrink-0 text-muted" aria-hidden />;
}

function passWord(passed: boolean | null): string {
  return passed === true ? t("proof.pass") : passed === false ? t("proof.fail") : t("proof.notTested");
}

/** One line per pass criterion; a fail is never hidden. */
export function CriteriaList({ items }: { items: Criterion[] }) {
  if (!items.length) return null;
  return (
    <ul className="grid gap-x-6 gap-y-1.5 [grid-template-columns:repeat(auto-fit,minmax(min(100%,22rem),1fr))]">
      {items.map((c) => (
        <li key={c.key} className="flex items-start gap-2 text-sm">
          <PassIcon passed={c.passed} />
          <span>
            <span className="sr-only">{passWord(c.passed)}: </span>
            <span className="font-medium">{c.label}</span> <span className="text-muted">{c.detail}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Each falsifier as a plain question with its result: pass, fail or "not tested in this version". */
export function FalsifierList({ items }: { items: Falsifier[] }) {
  if (!items.length) return null;
  return (
    <ul className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(min(100%,20rem),1fr))]">
      {items.map((f) => (
        <li key={f.key} className={cx("k-card p-3", f.passed === false && "border-danger/60")}>
          <div className="flex items-start gap-2">
            <PassIcon passed={f.passed} />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{f.name}</p>
              <p className="text-xs text-muted">
                {passWord(f.passed)}
                {f.result ? ` · ${f.result}` : ""}
              </p>
            </div>
          </div>
          {f.description_md ? (
            <Disclosure summary={<span className="text-xs text-muted">{t("proof.falsifierMore")}</span>} className="mt-1.5">
              <Markdown source={f.description_md} className="text-sm" />
            </Disclosure>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
