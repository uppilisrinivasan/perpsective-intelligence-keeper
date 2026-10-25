import * as RC from "@radix-ui/react-collapsible";
import { ChevronRight } from "lucide-react";
import { useState, type ReactNode } from "react";
import { cx } from "@/lib/cx";

/** A collapsible section with a button header. */
export function Disclosure({ summary, children, defaultOpen = false, className, open, onOpenChange, headerClassName }: {
  summary: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  className?: string;
  open?: boolean;
  onOpenChange?: (v: boolean) => void;
  headerClassName?: string;
}) {
  const [inner, setInner] = useState(defaultOpen);
  const isOpen = open ?? inner;
  return (
    <RC.Root open={isOpen} onOpenChange={(v) => (onOpenChange ? onOpenChange(v) : setInner(v))} className={className}>
      <RC.Trigger className={cx("group flex w-full items-center gap-1.5 text-left text-sm font-medium", headerClassName)}>
        <ChevronRight className="size-4 shrink-0 text-muted transition-transform duration-(--dur-fast) group-data-[state=open]:rotate-90" aria-hidden />
        <span className="flex-1 min-w-0">{summary}</span>
      </RC.Trigger>
      <RC.Content className="pt-2">{children}</RC.Content>
    </RC.Root>
  );
}
