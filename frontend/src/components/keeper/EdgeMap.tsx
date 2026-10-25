import { useMemo, useState } from "react";
import { Link } from "react-router";
import { CheckCircle2, Eye, EyeOff } from "lucide-react";
import type { EdgeCell, EdgeMap as EdgeMapData } from "@/api/types";
import { Disclosure } from "@/components/ui/Disclosure";
import { t } from "@/copy/t";
import { cx } from "@/lib/cx";
import { formatNumber, formatPercent } from "@/lib/format";
import { obj, str, num } from "@/lib/unknown";
import { LensItemChip } from "./LensItem";

const TINTS = ["bg-edge-1", "bg-edge-2", "bg-edge-3", "bg-edge-4", "bg-edge-5"] as const;

function multiplierText(c: EdgeCell): string | null {
  if (c.multiplier === null || c.multiplier === undefined) return null;
  return t("edge.multiplier", { x: formatNumber(c.multiplier, 1) });
}

/** The top cells (≤ 6): area, category, multiplier, bad outcomes, lens items, open PRs touching it. */
export function EdgeTopList({ cells, maintainer }: { cells: EdgeCell[]; maintainer: string }) {
  if (!cells.length) return <p className="text-sm text-muted">{t("edge.noTop", { name: maintainer })}</p>;
  return (
    <ol className="space-y-2.5" data-tour="edge_top">
      {cells.slice(0, 6).map((c) => {
        const mult = multiplierText(c);
        const bad = c.bad_outcomes ?? [];
        return (
          <li key={`${c.area}|${c.category}`} className="k-card border-l-4 border-l-edge-solid p-3">
            <div className="flex flex-wrap items-baseline gap-2">
              <p className="min-w-0 flex-1 font-mono text-sm font-medium k-anywhere">{c.area}</p>
              <span className="text-sm text-muted">{c.category_label || c.category}</span>
              <span className="inline-flex items-center gap-1 text-xs font-medium text-edge-fg">
                <Eye className="size-3.5" aria-hidden />
                {formatNumber(c.value, 2)}
              </span>
            </div>
            {mult ? <p className="mt-1 text-sm">{mult}</p> : null}
            {bad.length ? (
              <Disclosure summary={<span className="text-sm text-muted">{t("edge.badOutcomes", { n: bad.length })}</span>} className="mt-1">
                <ul className="space-y-0.5 text-sm">
                  {bad.map((b, i) => {
                    const o = obj(b);
                    const pr = num(o.pr_number) ?? num(o.number);
                    return (
                      <li key={i} className="text-muted">
                        {str(o.kind) ? `${str(o.kind)} · ` : ""}
                        {pr ? (
                          <Link to={`/pr/${pr}`} className="text-primary hover:underline">
                            {t("format.prNumber", { n: pr })}
                          </Link>
                        ) : null}
                        {str(o.title) ? ` · ${str(o.title)}` : ""}
                      </li>
                    );
                  })}
                </ul>
              </Disclosure>
            ) : null}
            {c.items?.length ? (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {c.items.map((it) => (
                  <LensItemChip key={it.id} item={it} />
                ))}
              </div>
            ) : null}
            {c.open_prs?.length ? (
              <p className="mt-1.5 text-sm">
                {t("edge.openPrs")}{" "}
                {c.open_prs.map((n) => (
                  <Link key={n} to={`/pr/${n}`} className="mr-1.5 text-primary hover:underline">
                    {t("format.prNumber", { n })}
                  </Link>
                ))}
              </p>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

export function CellList({ cells, kind, empty }: { cells: EdgeCell[]; kind: "enough" | "gap"; empty: string }) {
  if (!cells.length) return <p className="text-sm text-muted">{empty}</p>;
  return (
    <ul className={cx("divide-y divide-border rounded-md border border-border", kind === "enough" && "k-enough-pattern")}>
      {cells.map((c) => (
        <li key={`${c.area}|${c.category}`} className="flex flex-wrap items-center gap-2 bg-surface/90 px-3 py-2 text-sm">
          {kind === "enough" ? <CheckCircle2 className="size-4 text-shared-fg" aria-hidden /> : <EyeOff className="size-4 text-muted" aria-hidden />}
          <span className="min-w-0 flex-1 font-mono k-anywhere">{c.area}</span>
          <span className="text-muted">{c.category_label || c.category}</span>
          {kind === "gap" ? <span className="text-xs text-muted">{t("edge.gapDetail", { volume: c.volume, findings: c.findings ?? 0 })}</span> : <span className="text-xs text-shared-fg">{t("edge.enoughLabel")}</span>}
        </li>
      ))}
    </ul>
  );
}

/** Areas (rows) × categories (columns); 5 stepped edge tints + the value as text on hover or focus + a pattern for "enough". */
export function EdgeMap({ map }: { map: EdgeMapData }) {
  const [focus, setFocus] = useState<string | null>(null);
  const lookup = useMemo(() => new Map(map.cells.map((c) => [`${c.area}|${c.category}`, c])), [map.cells]);
  const max = Math.max(...map.cells.map((c) => c.value), 0.0001);
  const labels = new Map(map.cells.map((c) => [c.category, c.category_label || c.category]));
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <div role="grid" aria-label={t("edge.mapLabel")} className="grid min-w-max text-xs" style={{ gridTemplateColumns: `minmax(10rem, max-content) repeat(${map.categories.length}, minmax(5.5rem, 1fr))` }}>
        <div role="row" className="contents">
          <div role="columnheader" className="sticky left-0 top-0 z-[2] bg-surface-2 p-2 font-medium">
            {t("edge.area")}
          </div>
          {map.categories.map((cat) => (
            <div key={cat} role="columnheader" className="sticky top-0 z-[1] bg-surface-2 p-2 text-center font-medium">
              {labels.get(cat) ?? cat}
            </div>
          ))}
        </div>
        {map.areas.map((area) => (
          <div key={area} role="row" className="contents">
            <div role="rowheader" className="sticky left-0 z-[1] border-t border-border bg-surface p-2 font-mono k-anywhere">
              {area}
            </div>
            {map.categories.map((cat) => {
              const c = lookup.get(`${area}|${cat}`);
              const key = `${area}|${cat}`;
              if (!c)
                return (
                  <div key={cat} role="gridcell" className="border-t border-l border-border bg-surface">
                    <span className="sr-only">{t("edge.noData")}</span>
                  </div>
                );
              const step = Math.min(4, Math.floor((c.value / max) * 5));
              const enough = c.kind === "enough";
              const showValue = focus === key;
              const label = t("edge.cellAria", { area, category: labels.get(cat) ?? cat, value: formatNumber(c.value, 2), kind: enough ? t("edge.enoughLabel") : "" });
              return (
                <div key={cat} role="gridcell" className="border-t border-l border-border">
                  <button
                    type="button"
                    aria-label={label}
                    onFocus={() => setFocus(key)}
                    onBlur={() => setFocus(null)}
                    onMouseEnter={() => setFocus(key)}
                    onMouseLeave={() => setFocus(null)}
                    className={cx("flex size-full min-h-9 items-center justify-center p-1 tabular", enough ? "bg-shared-bg k-enough-pattern" : TINTS[step], step >= 3 && !enough ? "text-(--edge-ink-dark)" : "text-text")}
                  >
                    <span className={cx(showValue ? "opacity-100" : "opacity-0", "font-medium")}>{enough ? formatPercent(c.shared_rate) : formatNumber(c.value, 2)}</span>
                  </button>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
