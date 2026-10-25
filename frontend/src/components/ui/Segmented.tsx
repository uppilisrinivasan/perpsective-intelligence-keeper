import * as TG from "@radix-ui/react-toggle-group";
import type { ReactNode } from "react";
import { cx } from "@/lib/cx";

export interface SegmentOption {
  value: string;
  label: ReactNode;
  disabled?: boolean;
}

/** A single-choice toggle group (view modes, periods). */
export function Segmented({ value, onChange, options, label, size = "md" }: { value: string; onChange: (v: string) => void; options: SegmentOption[]; label: string; size?: "sm" | "md" }) {
  return (
    <TG.Root
      type="single"
      value={value}
      onValueChange={(v) => v && onChange(v)}
      aria-label={label}
      className="inline-flex rounded-md border border-border bg-surface-2 p-0.5"
    >
      {options.map((o) => (
        <TG.Item
          key={o.value}
          value={o.value}
          disabled={o.disabled}
          className={cx(
            "rounded-sm font-medium text-muted data-[state=on]:bg-surface data-[state=on]:text-text data-[state=on]:shadow-card",
            "hover:text-text disabled:opacity-50",
            size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm",
          )}
        >
          {o.label}
        </TG.Item>
      ))}
    </TG.Root>
  );
}
