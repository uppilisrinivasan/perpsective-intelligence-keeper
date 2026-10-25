import { Link } from "react-router";
import { AlertTriangle, Layers } from "lucide-react";
import type { LensItem, LensItemRef } from "@/api/types";
import { badgeClass, Pill } from "@/components/ui/Badge";
import { Tooltip } from "@/components/ui/Tooltip";
import { Markdown } from "@/components/ui/Markdown";
import { t, tDynamic } from "@/copy/t";
import { cx } from "@/lib/cx";
import { formatInterval, formatPercent } from "@/lib/format";
import { laneDef } from "@/lib/lanes";

/** Lens item type → lane colour (edge orange, blind spot blue, the rest neutral). */
export function itemLane(type: string | null | undefined): string {
  if (type === "edge") return "edge";
  if (type === "blind_spot") return "blind_spot";
  return "baseline_only";
}

export function itemTypeLabel(type: string): string {
  return tDynamic(`lens.itemType.${type}`) || type;
}

export function itemStatusLabel(status: string): string {
  return tDynamic(`lens.itemStatus.${status}`) || status;
}

/** A small clickable chip → Lens with the item open. */
export function LensItemChip({ item, lane }: { item: Pick<LensItemRef, "id" | "title"> & { support?: number | null }; lane?: string }) {
  const def = laneDef(lane ?? "edge");
  return (
    <Tooltip content={item.support ? t("lens.item.seenIn", { n: item.support }) : undefined}>
      <Link to={`/lens?tab=items&item=${encodeURIComponent(item.id)}`} className={cx(badgeClass(def.tone), "hover:underline")}>
        <Layers className="size-[1em]" aria-hidden strokeWidth={1.75} />
        <span className="k-anywhere">{item.title}</span>
      </Link>
    </Tooltip>
  );
}

/** "seen in 9 reviews · right 82% of the time (65–93%)" */
export function SupportMeter({ support, precision, ci }: { support: number | null | undefined; precision: number | null | undefined; ci?: { low: number; high: number } | null }) {
  const pct = precision !== null && precision !== undefined ? Math.max(0, Math.min(1, precision)) : null;
  const small = (support ?? 0) < 10;
  return (
    <div className="space-y-1">
      <p className="text-xs text-muted tabular">
        {t("lens.item.seenIn", { n: support ?? 0 })}
        {pct !== null ? (
          <>
            {" · "}
            {t("lens.item.right", { pct: formatPercent(pct) })} {ci ? formatInterval(ci.low, ci.high) : ""}
          </>
        ) : null}
        {small ? ` ${t("format.smallSample")}` : ""}
      </p>
      {pct !== null ? (
        <div className="relative h-1.5 w-full rounded-full bg-surface-2" aria-hidden>
          {ci ? <div className="absolute inset-y-0 rounded-full bg-border-strong/60" style={{ left: `${ci.low * 100}%`, width: `${Math.max(0, ci.high - ci.low) * 100}%` }} /> : null}
          <div className="absolute inset-y-0 left-0 rounded-full bg-edge-solid" style={{ width: `${pct * 100}%` }} />
        </div>
      ) : null}
    </div>
  );
}

export function LensItemCard({ item, onOpen }: { item: LensItem; onOpen: (id: string) => void }) {
  const lane = itemLane(item.type);
  const def = laneDef(lane);
  const triggers = [...(item.triggers.paths ?? []), ...(item.triggers.code_patterns ?? [])].slice(0, 5);
  const biasWarn = item.status === "bias_suspected" || Boolean(item.bias && (item.bias as Record<string, unknown>).verdict === "bias_suspected");
  return (
    <article className={cx("k-card flex flex-col gap-2 border-l-4 p-3.5", def.border)} data-item={item.id}>
      <div className="flex flex-wrap items-center gap-1.5 text-xs">
        <Pill tone={def.tone}>{itemTypeLabel(item.type)}</Pill>
        <span className="text-muted">{item.category_label || item.category}</span>
        {item.status !== "validated" && item.status !== "active" ? <Pill tone="outline">{itemStatusLabel(item.status)}</Pill> : null}
      </div>
      <h3 className="text-base font-semibold leading-snug">
        <button type="button" className="text-left hover:underline k-anywhere" onClick={() => onOpen(item.id)}>
          {item.title}
        </button>
      </h3>
      <Markdown source={item.statement_md} className="text-sm text-muted line-clamp-3" />
      <SupportMeter support={item.stats.support} precision={item.stats.posterior_mean} ci={item.stats.ci90} />
      {triggers.length ? (
        <ul className="flex flex-wrap gap-1" aria-label={t("lens.item.triggers")}>
          {triggers.map((tr) => (
            <li key={tr}>
              <code className="rounded-sm bg-surface-2 px-1.5 py-px text-xs k-anywhere">{tr}</code>
            </li>
          ))}
        </ul>
      ) : null}
      {biasWarn ? (
        <p className="flex items-center gap-1 text-xs text-warning-fg">
          <AlertTriangle className="size-3.5" aria-hidden />
          {t("lens.item.biasWarning")}
        </p>
      ) : null}
    </article>
  );
}
