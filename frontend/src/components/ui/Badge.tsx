import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { cx } from "@/lib/cx";

export type Tone = "neutral" | "info" | "success" | "warning" | "danger" | "edge" | "blind" | "shared" | "unknown" | "baseline" | "outline";

const tones: Record<Tone, string> = {
  neutral: "bg-surface-2 text-text border-border",
  outline: "bg-transparent text-muted border-border-strong",
  info: "bg-info-bg text-info-fg border-info/40",
  success: "bg-success-bg text-success-fg border-success/40",
  warning: "bg-warning-bg text-warning-fg border-warning/50",
  danger: "bg-danger-bg text-danger-fg border-danger/40",
  edge: "bg-edge-bg text-edge-fg border-edge-border",
  blind: "bg-blind-bg text-blind-fg border-blind-border",
  shared: "bg-shared-bg text-shared-fg border-shared-border",
  unknown: "bg-unknown-bg text-unknown-fg border-unknown-border",
  baseline: "bg-baseline-bg text-baseline-fg border-baseline-border",
};

export function badgeClass(tone: Tone = "neutral", size: "sm" | "md" = "sm"): string {
  return cx(
    "inline-flex items-center gap-1 rounded-full border font-medium whitespace-nowrap",
    size === "sm" ? "text-xs px-2 py-0.5" : "text-sm px-2.5 py-0.5",
    tones[tone],
  );
}

export function Badge({ tone = "neutral", icon: Icon, children, size = "sm", className }: { tone?: Tone; icon?: LucideIcon; children: ReactNode; size?: "sm" | "md"; className?: string }) {
  return (
    <span className={cx(badgeClass(tone, size), className)}>
      {Icon ? <Icon className="size-[1em] shrink-0" aria-hidden strokeWidth={1.75} /> : null}
      {children}
    </span>
  );
}

/** A squarer chip for metadata. */
export function Pill({ tone = "neutral", icon: Icon, children, className }: { tone?: Tone; icon?: LucideIcon; children: ReactNode; className?: string }) {
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-sm border px-1.5 py-px text-xs font-medium", tones[tone], className)}>
      {Icon ? <Icon className="size-[1em] shrink-0" aria-hidden strokeWidth={1.75} /> : null}
      {children}
    </span>
  );
}
