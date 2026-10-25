import * as RG from "@radix-ui/react-radio-group";
import { cx } from "@/lib/cx";
import { FILTER_LANES, laneDef, laneLabel } from "@/lib/lanes";
import { t } from "@/copy/t";
import { LaneDot } from "./Lane";

const ALL = "all";

export type LaneCounts = Partial<Record<string, number>>;

/** A radio group (segmented control) with lane colour dots and counts. "" means all lanes. */
export function LaneFilter({ counts, total, value, onChange }: { counts: LaneCounts; total: number; value: string; onChange: (v: string) => void }) {
  const options = [{ value: ALL, label: t("queue.filter.all"), count: total }, ...FILTER_LANES.map((l) => ({ value: l, label: laneLabel(l), count: counts[l] ?? 0 }))];
  return (
    <RG.Root value={value || ALL} onValueChange={(v) => onChange(v === ALL ? "" : v)} aria-label={t("queue.filter.label")} orientation="horizontal" className="flex flex-wrap gap-1.5">
      {options.map((o) => {
        const def = o.value !== ALL ? laneDef(o.value) : null;
        const Icon = def?.icon;
        return (
          <RG.Item
            key={o.value}
            value={o.value}
            className={cx(
              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-medium",
              "border-border bg-surface text-text hover:bg-surface-2",
              "data-[state=checked]:border-text data-[state=checked]:bg-surface-2",
            )}
          >
            {o.value !== ALL ? <LaneDot lane={o.value} /> : null}
            {Icon ? <Icon className={cx("size-[1em]", def?.fg)} aria-hidden strokeWidth={1.75} /> : null}
            <span>{o.label}</span>
            <span className="tabular text-muted">{o.count}</span>
          </RG.Item>
        );
      })}
    </RG.Root>
  );
}
