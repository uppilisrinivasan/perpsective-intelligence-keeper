import type { GrowthPeriod } from "@/api/types";
import { Tooltip } from "@/components/ui/Tooltip";
import { t, tDynamic } from "@/copy/t";
import { formatNumber } from "@/lib/format";
import { num } from "@/lib/unknown";

const MEASURES = ["r_plus_rate", "costly_r_minus_rate", "r_plus_hit", "g"] as const;

function measureValue(p: GrowthPeriod, key: string): number | undefined {
  const m = p.measures as Record<string, unknown>;
  return num(m[key]) ?? num(m[key.toUpperCase()]);
}

/** Small CSS bars per period for each measure, with tooltips defining each in plain words. */
export function GrowthTrend({ snapshots }: { snapshots: GrowthPeriod[] }) {
  if (!snapshots.length) return <p className="text-sm text-muted">{t("growth.noSnapshots")}</p>;
  return (
    <div className="grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(min(100%,16rem),1fr))]">
      {MEASURES.map((key) => {
        const values = snapshots.map((s) => measureValue(s, key));
        if (values.every((v) => v === undefined)) return null;
        const max = Math.max(...values.map((v) => Math.abs(v ?? 0)), 0.0001);
        return (
          <section key={key} className="k-card p-3" aria-label={tDynamic(`growth.measure.${key}`)}>
            <Tooltip content={tDynamic(`growth.measure.${key}.tip`)}>
              <h4 tabIndex={0} className="k-term inline text-sm font-semibold">
                {tDynamic(`growth.measure.${key}`)}
              </h4>
            </Tooltip>
            <ol className="mt-3 flex h-24 items-end gap-1.5">
              {snapshots.map((s, i) => {
                const v = values[i];
                const h = v === undefined ? 0 : (Math.abs(v) / max) * 100;
                return (
                  <li key={s.period} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1">
                    <span className="text-[0.7rem] text-muted tabular">{v === undefined ? t("format.none") : formatNumber(v, 2)}</span>
                    <div className="w-full rounded-t-sm bg-edge-solid" style={{ height: `${Math.max(h, v === undefined ? 0 : 3)}%` }} aria-hidden />
                    <span className="w-full truncate text-center text-[0.7rem] text-muted" title={s.period}>
                      {s.period}
                    </span>
                  </li>
                );
              })}
            </ol>
          </section>
        );
      })}
    </div>
  );
}
