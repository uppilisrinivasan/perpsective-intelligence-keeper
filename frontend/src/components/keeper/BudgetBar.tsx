import { AlertTriangle } from "lucide-react";
import { QUEUE_LANES, laneDef, laneLabel } from "@/lib/lanes";
import { t } from "@/copy/t";
import { cx } from "@/lib/cx";
import { formatMinutes } from "@/lib/format";

/** Attention stacked by lane against the weekly budget; over budget shows a warning and a hand-off hint. */
export function BudgetBar({ byLane, total, budget, overBudget, handoffSuggestion }: {
  byLane: Partial<Record<string, number>>;
  total: number;
  budget: number;
  overBudget: boolean;
  handoffSuggestion?: number | null;
}) {
  const scale = Math.max(budget, total, 1);
  const segments = QUEUE_LANES.map((l) => ({ lane: l, minutes: byLane[l] ?? 0 })).filter((s) => s.minutes > 0);
  const over = Math.max(0, total - budget);
  return (
    <div className="space-y-1.5">
      <div
        className={cx("relative flex h-3 w-full overflow-hidden rounded-full bg-surface-2", overBudget && "ring-2 ring-warning")}
        role="img"
        aria-label={t("queue.budget.aria", { total, budget })}
      >
        {segments.map((s) => (
          <div key={s.lane} className={cx("h-full", laneDef(s.lane).solid)} style={{ width: `${(s.minutes / scale) * 100}%` }} title={`${laneLabel(s.lane)}: ${formatMinutes(s.minutes, false)}`} />
        ))}
        <div className="absolute inset-y-0 w-0.5 bg-text" style={{ left: `${(budget / scale) * 100}%` }} aria-hidden />
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
        <span className="tabular font-medium text-text">{t("queue.budget.value", { total, budget })}</span>
        {segments.map((s) => (
          <span key={s.lane} className="inline-flex items-center gap-1">
            <span className={cx("inline-block size-2 rounded-full", laneDef(s.lane).solid)} aria-hidden />
            {laneLabel(s.lane)} <span className="tabular">{formatMinutes(s.minutes, false)}</span>
          </span>
        ))}
        {overBudget ? (
          <span className="inline-flex items-center gap-1 font-medium text-warning-fg">
            <AlertTriangle className="size-3.5" aria-hidden />
            {handoffSuggestion ? t("queue.budget.overHandoff", { over, n: handoffSuggestion }) : t("queue.budget.over", { over })}
          </span>
        ) : null}
      </div>
    </div>
  );
}
