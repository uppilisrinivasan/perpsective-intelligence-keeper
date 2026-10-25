import * as RT from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";

export const TooltipProvider = ({ children }: { children: ReactNode }) => (
  <RT.Provider delayDuration={300} skipDelayDuration={200}>
    {children}
  </RT.Provider>
);

/** Radix tooltip: 300 ms delay, also on keyboard focus. The trigger must be focusable. */
export function Tooltip({ content, side = "top", children, disabled }: { content: ReactNode; side?: "top" | "bottom" | "left" | "right"; children: ReactNode; disabled?: boolean }) {
  if (disabled || content === null || content === undefined || content === "") return <>{children}</>;
  return (
    <RT.Root>
      <RT.Trigger asChild>{children}</RT.Trigger>
      <RT.Portal>
        <RT.Content
          side={side}
          sideOffset={6}
          collisionPadding={8}
          className="z-[60] max-w-[min(22rem,90vw)] rounded-md bg-text text-bg px-2.5 py-1.5 text-xs shadow-pop data-[state=delayed-open]:animate-[k-fade-in_var(--dur-fast)]"
        >
          {content}
          <RT.Arrow className="fill-text" />
        </RT.Content>
      </RT.Portal>
    </RT.Root>
  );
}
