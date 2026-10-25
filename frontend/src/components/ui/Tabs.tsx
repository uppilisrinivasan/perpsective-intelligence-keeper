import * as RTabs from "@radix-ui/react-tabs";
import type { ReactNode } from "react";
import { cx } from "@/lib/cx";

export interface TabDef {
  value: string;
  label: ReactNode;
  disabled?: boolean;
}

export function Tabs({ value, onValueChange, tabs, children, label, className, listClassName }: {
  value: string;
  onValueChange: (v: string) => void;
  tabs: TabDef[];
  children: ReactNode;
  label: string;
  className?: string;
  listClassName?: string;
}) {
  return (
    <RTabs.Root value={value} onValueChange={onValueChange} className={className} activationMode="manual">
      <RTabs.List aria-label={label} className={cx("flex gap-1 overflow-x-auto border-b border-border", listClassName)}>
        {tabs.map((tab) => (
          <RTabs.Trigger
            key={tab.value}
            value={tab.value}
            disabled={tab.disabled}
            className={cx(
              "relative -mb-px whitespace-nowrap border-b-2 border-transparent px-3 py-2 text-sm font-medium text-muted",
              "hover:text-text data-[state=active]:border-primary data-[state=active]:text-text disabled:opacity-50",
            )}
          >
            {tab.label}
          </RTabs.Trigger>
        ))}
      </RTabs.List>
      {children}
    </RTabs.Root>
  );
}

export const TabPanel = ({ value, children, className }: { value: string; children: ReactNode; className?: string }) => (
  <RTabs.Content value={value} className={cx("outline-none", className)}>
    {children}
  </RTabs.Content>
);
