import * as RP from "@radix-ui/react-popover";
import type { ReactNode } from "react";
import { cx } from "@/lib/cx";

export function Popover({ trigger, children, align = "start", side = "bottom", className, open, onOpenChange }: {
  trigger: ReactNode;
  children: ReactNode;
  align?: "start" | "center" | "end";
  side?: "top" | "bottom" | "left" | "right";
  className?: string;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  return (
    <RP.Root open={open} onOpenChange={onOpenChange}>
      <RP.Trigger asChild>{trigger}</RP.Trigger>
      <RP.Portal>
        <RP.Content
          align={align}
          side={side}
          sideOffset={6}
          collisionPadding={12}
          className={cx("z-50 rounded-lg border border-border bg-surface text-text shadow-pop p-3 w-[min(24rem,92vw)] max-h-[70dvh] overflow-y-auto", className)}
        >
          {children}
        </RP.Content>
      </RP.Portal>
    </RP.Root>
  );
}
