import { Clock } from "lucide-react";
import { cx } from "@/lib/cx";
import { badgeClass } from "@/components/ui/Badge";
import { Tooltip } from "@/components/ui/Tooltip";
import { laneDef, laneLabel, laneMeaning } from "@/lib/lanes";
import { t } from "@/copy/t";
import { formatDate } from "@/lib/format";

/** Icon + label + colour from tokens; tooltip with the lane meaning. */
export function LaneBadge({ lane, size = "sm", showLabel = true, savedAt, maintainer }: { lane: string | null | undefined; size?: "sm" | "md"; showLabel?: boolean; savedAt?: string | null; maintainer?: string }) {
  const def = laneDef(lane);
  const Icon = def.icon;
  const label = laneLabel(lane);
  const meaning = laneMeaning(lane, maintainer ? { maintainer } : undefined);
  return (
    <Tooltip content={savedAt ? `${meaning} ${t("lane.savedAt", { date: formatDate(savedAt) })}` : meaning}>
      <span tabIndex={0} className={badgeClass(def.tone, size)} data-lane={lane ?? "unsorted"}>
        <Icon className="size-[1em] shrink-0" aria-hidden strokeWidth={1.75} />
        {showLabel ? <span>{label}</span> : <span className="sr-only">{label}</span>}
        {savedAt ? <Clock className="size-[0.85em] opacity-70" aria-hidden strokeWidth={1.75} /> : null}
      </span>
    </Tooltip>
  );
}

/** For dense lists; always paired with text nearby. */
export function LaneDot({ lane, className }: { lane: string | null | undefined; className?: string }) {
  const def = laneDef(lane);
  return <span className={cx("inline-block size-2.5 shrink-0 rounded-full", def.solid, className)} aria-hidden />;
}

export function LaneIcon({ lane, className }: { lane: string | null | undefined; className?: string }) {
  const def = laneDef(lane);
  const Icon = def.icon;
  return <Icon className={cx("size-[1em] shrink-0", def.fg, className)} aria-hidden strokeWidth={1.75} />;
}
