import { CheckCircle2, Eye, List, ScanSearch, UserRoundSearch, CircleDashed, type LucideIcon } from "lucide-react";
import type { Tone } from "@/components/ui/Badge";
import { tDynamic } from "@/copy/t";

/** The lane language (docs/06-frontend/02-design-system.md §1.2): colour + icon + label, never colour alone. */
export type LaneKey = "edge" | "blind_spot" | "shared" | "unknown" | "baseline_only" | "unsorted";

interface LaneDef {
  tone: Tone;
  icon: LucideIcon;
  solid: string;
  bg: string;
  fg: string;
  border: string;
}

const DEFS: Record<LaneKey, LaneDef> = {
  edge: { tone: "edge", icon: Eye, solid: "bg-edge-solid", bg: "bg-edge-bg", fg: "text-edge-fg", border: "border-edge-border" },
  blind_spot: { tone: "blind", icon: ScanSearch, solid: "bg-blind-solid", bg: "bg-blind-bg", fg: "text-blind-fg", border: "border-blind-border" },
  shared: { tone: "shared", icon: CheckCircle2, solid: "bg-shared-solid", bg: "bg-shared-bg", fg: "text-shared-fg", border: "border-shared-border" },
  unknown: { tone: "unknown", icon: UserRoundSearch, solid: "bg-unknown-solid", bg: "bg-unknown-bg", fg: "text-unknown-fg", border: "border-unknown-border" },
  baseline_only: { tone: "baseline", icon: List, solid: "bg-baseline-solid", bg: "bg-baseline-bg", fg: "text-baseline-fg", border: "border-baseline-border" },
  unsorted: { tone: "outline", icon: CircleDashed, solid: "bg-baseline-solid", bg: "bg-surface-2", fg: "text-muted", border: "border-border" },
};

/** Queue order for "attention" grouping and the findings pane order. */
export const QUEUE_LANES = ["unknown", "edge", "blind_spot", "shared"] as const;
export const FINDING_LANES = ["edge", "blind_spot", "shared", "baseline_only"] as const;
export const FILTER_LANES = ["edge", "blind_spot", "unknown", "shared"] as const;

export function laneKey(lane: string | null | undefined): LaneKey {
  return lane && lane in DEFS ? (lane as LaneKey) : "unsorted";
}

export function laneDef(lane: string | null | undefined): LaneDef {
  return DEFS[laneKey(lane)];
}

export function laneLabel(lane: string | null | undefined): string {
  return tDynamic(`lane.${laneKey(lane)}.label`);
}

export function laneMeaning(lane: string | null | undefined, vars?: Record<string, string>): string {
  return tDynamic(`lane.${laneKey(lane)}.meaning`, vars);
}
