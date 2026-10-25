import { Link } from "react-router";
import { CheckCircle2, CircleX, Hand, LoaderCircle, Wrench } from "lucide-react";
import type { MouseEvent } from "react";
import type { QueueRow as Row } from "@/api/types";
import { Pill } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { t } from "@/copy/t";
import { cx } from "@/lib/cx";
import { formatMinutes, personName } from "@/lib/format";
import { laneKey, laneLabel } from "@/lib/lanes";
import { LaneBadge, LaneDot } from "./Lane";
import { ReasonLine } from "./ReasonLine";

export interface QueueRowProps {
  row: Row;
  selected?: boolean;
  /** When set (wide layouts with a preview pane), a pointer click selects instead of opening. */
  onSelect?: (n: number) => void;
  onPrefetch?: (n: number) => void;
  onHandoff?: (row: Row) => void;
  handoffDisabledReason?: string;
  maintainer?: string;
  flash?: boolean;
  href: string;
}

export function rowAccessibleName(row: Row): string {
  const lane = row.analysis_id ? laneLabel(row.lane) : laneLabel("unsorted");
  return t("queue.row.aria", { n: row.number, title: row.title, lane: lane.toLowerCase(), minutes: row.attention_minutes });
}

function FixChip({ fix }: { fix: NonNullable<Row["fix"]> }) {
  const s = fix.status;
  if (s === "passed" || s === "succeeded" || s === "completed" || s === "ready")
    return (
      <Pill tone="success" icon={CheckCircle2}>
        {t("queue.row.fixReady")}
      </Pill>
    );
  if (s === "running" || s === "queued")
    return (
      <Pill tone="info" icon={LoaderCircle}>
        {t("queue.row.fixRunning")}
      </Pill>
    );
  if (s === "failed" || s === "no_fix")
    return (
      <Pill tone="danger" icon={CircleX}>
        {t("queue.row.fixFailed")}
      </Pill>
    );
  return (
    <Pill icon={Wrench}>
      {t("queue.row.fixStatus", { status: s })}
    </Pill>
  );
}

/** Container-query layout: stacked when narrow, a right-aligned meta column from container md. */
export function QueueRow({ row, selected, onSelect, onPrefetch, onHandoff, handoffDisabledReason, maintainer, flash, href }: QueueRowProps) {
  const sorted = Boolean(row.analysis_id);
  const lane = sorted ? row.lane : "unsorted";
  const findings = (row.counts.edge ?? 0) + (row.counts.blind_spot ?? 0);
  const handoffName = row.handoff ? row.handoff.display_name || row.handoff.login : null;
  const onClick = (e: MouseEvent<HTMLAnchorElement>) => {
    // Pointer clicks select (preview pane); Enter (detail 0) and modified clicks open the PR.
    if (onSelect && e.detail > 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && e.button === 0) {
      e.preventDefault();
      onSelect(row.number);
    }
  };
  return (
    <li
      className={cx(
        "@container group relative border-b border-border px-3 py-3 transition-colors duration-(--dur-fast)",
        selected ? "bg-surface-2" : "hover:bg-surface-2/60",
        flash && "k-flash",
      )}
      data-tour={laneKey(row.lane) === "unknown" ? "queue_row" : undefined}
      data-tour-id={String(row.number)}
      aria-current={selected || undefined}
      onMouseEnter={() => onPrefetch?.(row.number)}
    >
      <div className="flex flex-col gap-1.5 @md:flex-row @md:items-start @md:gap-4">
        <div className="flex min-w-0 flex-1 gap-2.5">
          <LaneDot lane={lane} className="mt-2" />
          <div className="min-w-0 flex-1 space-y-1">
            <Link
              to={href}
              onClick={onClick}
              onFocus={() => onPrefetch?.(row.number)}
              aria-label={rowAccessibleName(row)}
              className="block font-medium leading-snug k-anywhere after:absolute after:inset-0 after:content-[''] focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:outline-focus focus-visible:after:-outline-offset-2"
              data-row-link={row.number}
            >
              <span className="mr-1.5 tabular text-muted">{t("format.prNumber", { n: row.number })}</span>
              {row.title}
            </Link>
            <p className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-sm text-muted">
              <span>{personName(row.author)}</span>
              {row.author.first_time ? <Pill tone="outline">{t("queue.row.firstTime")}</Pill> : null}
              {row.areas?.[0] ? <span className="k-anywhere">{t("queue.row.touches", { area: row.areas[0] })}</span> : null}
              {row.signals.slice(0, 2).map((s) => (
                <Pill key={s.key} tone="unknown">
                  {s.label}
                </Pill>
              ))}
              {row.slop?.label ? <Pill tone="warning">{row.slop.label}</Pill> : null}
            </p>
            <div className="relative z-10 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
              {sorted ? <ReasonLine reasons={row.reasons} /> : <span className="text-muted">{t("lane.unsorted.meaning", { maintainer: maintainer ?? "" })}</span>}
              {findings > 0 ? <span className="text-muted">{t("queue.row.findings", { n: findings })}</span> : null}
              {row.fix ? <FixChip fix={row.fix} /> : null}
            </div>
          </div>
        </div>
        <div className="relative z-10 flex flex-wrap items-center gap-2 pl-5 @md:flex-col @md:items-end @md:pl-0 @md:text-right">
          <LaneBadge lane={lane} savedAt={row.provenance.origin === "snapshot" ? row.provenance.computed_at : undefined} maintainer={maintainer} />
          {sorted && row.attention_minutes > 0 ? <span className="text-sm text-muted tabular">{t("format.approxMinutes", { m: row.attention_minutes })}</span> : null}
          {sorted && laneKey(row.lane) === "unknown" && handoffName && onHandoff ? (
            <Button size="sm" icon={Hand} onClick={() => onHandoff(row)} disabled={Boolean(handoffDisabledReason)} title={handoffDisabledReason}>
              {t("queue.row.handTo", { name: handoffName })}
            </Button>
          ) : null}
        </div>
      </div>
      <span className="sr-only">{formatMinutes(row.attention_minutes)}</span>
    </li>
  );
}
