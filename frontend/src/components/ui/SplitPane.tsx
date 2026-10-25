import { Group, Panel, Separator, useDefaultLayout } from "react-resizable-panels";
import type { ReactNode } from "react";
import { cx } from "@/lib/cx";
import { t } from "@/copy/t";

export interface Pane {
  id: string;
  /** Percent of the group, e.g. 38. */
  defaultSize: number;
  minSize?: number;
  content: ReactNode;
  className?: string;
  label?: string;
}

function safeStorage(): Storage | undefined {
  try {
    return window.localStorage;
  } catch {
    return undefined;
  }
}

/** Resizable split panes with sizes in percent, persisted per screen; keyboard-resizable separators. */
export function SplitPane({ id, panes, className }: { id: string; panes: Pane[]; className?: string }) {
  const storage = safeStorage();
  const { defaultLayout, onLayoutChanged } = useDefaultLayout({
    id: `keeper.split.${id}`,
    panelIds: panes.map((p) => p.id),
    ...(storage ? { storage } : {}),
  });
  return (
    <Group orientation="horizontal" id={`keeper-split-${id}`} defaultLayout={defaultLayout} onLayoutChanged={onLayoutChanged} className={cx("min-h-0", className)}>
      {panes.map((p, i) => (
        <PaneWithSeparator key={p.id} pane={p} last={i === panes.length - 1} />
      ))}
    </Group>
  );
}

function PaneWithSeparator({ pane, last }: { pane: Pane; last: boolean }) {
  return (
    <>
      <Panel id={pane.id} defaultSize={`${pane.defaultSize}%`} minSize={`${pane.minSize ?? 20}%`} className={cx("min-w-0 h-full", pane.className)}>
        {pane.content}
      </Panel>
      {!last ? (
        <Separator
          className="group relative w-1.5 shrink-0 bg-transparent outline-none focus-visible:bg-focus/40 hover:bg-border"
          aria-label={t("common.resize")}
        >
          <span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-border group-hover:bg-border-strong" aria-hidden />
        </Separator>
      ) : null}
    </>
  );
}
