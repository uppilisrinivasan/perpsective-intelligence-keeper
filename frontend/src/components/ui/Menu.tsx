import * as DM from "@radix-ui/react-dropdown-menu";
import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { cx } from "@/lib/cx";
import { Tooltip } from "./Tooltip";

export interface MenuItem {
  key: string;
  label: string;
  icon?: LucideIcon;
  onSelect: () => void;
  disabled?: boolean;
  disabledReason?: string;
  danger?: boolean;
  checked?: boolean;
}

export function Menu({ trigger, items, align = "end", label }: { trigger: ReactNode; items: Array<MenuItem | "separator">; align?: "start" | "end"; label?: string }) {
  return (
    <DM.Root>
      <DM.Trigger asChild>{trigger}</DM.Trigger>
      <DM.Portal>
        <DM.Content align={align} sideOffset={6} collisionPadding={12} aria-label={label} className="z-50 min-w-[12rem] rounded-lg border border-border bg-surface p-1 shadow-pop">
          {items.map((it, i) =>
            it === "separator" ? (
              <DM.Separator key={`s${i}`} className="my-1 h-px bg-border" />
            ) : (
              <Tooltip key={it.key} content={it.disabled ? it.disabledReason : undefined} side="left">
                <DM.Item
                  disabled={it.disabled}
                  onSelect={it.onSelect}
                  className={cx(
                    "flex items-center gap-2 rounded-md px-2.5 py-1.5 text-sm outline-none select-none",
                    "data-[highlighted]:bg-surface-2 data-[disabled]:opacity-50",
                    it.danger && "text-danger-fg",
                  )}
                >
                  {it.icon ? <it.icon className="size-4 text-muted" aria-hidden strokeWidth={1.75} /> : null}
                  <span className="flex-1">{it.label}</span>
                  {it.checked ? <span aria-hidden>✓</span> : null}
                </DM.Item>
              </Tooltip>
            ),
          )}
        </DM.Content>
      </DM.Portal>
    </DM.Root>
  );
}
