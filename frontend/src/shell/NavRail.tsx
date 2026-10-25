import { NavLink } from "react-router";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { Kbd } from "@/components/ui/Kbd";
import { Tooltip } from "@/components/ui/Tooltip";
import { t } from "@/copy/t";
import { cx } from "@/lib/cx";
import { setPref, usePrefs } from "@/state/prefs";
import { NAV, SETTINGS_NAV, type NavItem } from "./nav";

export interface NavBadges {
  queue?: number;
  lensDot?: boolean;
}

function Item({ item, collapsed, badges, onNavigate }: { item: NavItem; collapsed: boolean; badges: NavBadges; onNavigate?: () => void }) {
  const Icon = item.icon;
  const label = t(item.label);
  const count = item.key === "queue" ? badges.queue : undefined;
  const dot = item.key === "lens" && badges.lensDot;
  const link = (
    <NavLink
      to={item.to}
      onClick={onNavigate}
      className={({ isActive }) =>
        cx(
          "group relative flex items-center gap-3 rounded-md px-2.5 py-2 text-sm font-medium",
          isActive ? "bg-surface-2 text-text" : "text-muted hover:bg-surface-2 hover:text-text",
        )
      }
      aria-label={collapsed ? label : undefined}
    >
      <Icon className="size-5 shrink-0" aria-hidden strokeWidth={1.75} />
      <span className={cx("flex-1 truncate", collapsed && "sr-only")}>{label}</span>
      {count ? <span className={cx("rounded-full bg-edge-bg px-1.5 text-xs text-edge-fg tabular", collapsed && "absolute -right-0.5 -top-0.5")}>{count}</span> : null}
      {dot ? <span className={cx("size-2 rounded-full bg-edge-solid", collapsed && "absolute right-1.5 top-1.5")} aria-label={t("nav.lensUpdate")} /> : null}
    </NavLink>
  );
  return collapsed ? (
    <Tooltip side="right" content={<span className="inline-flex items-center gap-2">{label} <Kbd keys={item.shortcut} /></span>}>
      {link}
    </Tooltip>
  ) : (
    link
  );
}

/** The left rail at ≥ lg: icons and labels, collapsible to icons (persisted); auto-collapses below 72rem. */
export function NavRail({ badges, forceExpanded, onNavigate }: { badges: NavBadges; forceExpanded?: boolean; onNavigate?: () => void }) {
  const prefs = usePrefs();
  const collapsed = !forceExpanded && prefs.railCollapsed;
  return (
    <nav aria-label={t("nav.label")} className="flex h-full flex-col gap-1 p-2">
      <ul className="flex flex-col gap-0.5">
        {NAV.map((item) => (
          <li key={item.key}>
            <Item item={item} collapsed={collapsed} badges={badges} onNavigate={onNavigate} />
          </li>
        ))}
      </ul>
      <div className="mt-auto flex flex-col gap-0.5 border-t border-border pt-2">
        <Item item={SETTINGS_NAV} collapsed={collapsed} badges={badges} onNavigate={onNavigate} />
        {!forceExpanded ? (
          <button
            type="button"
            onClick={() => setPref("railCollapsed", !prefs.railCollapsed)}
            className="flex items-center gap-3 rounded-md px-2.5 py-2 text-sm text-muted hover:bg-surface-2 hover:text-text"
            aria-label={collapsed ? t("nav.expand") : t("nav.collapse")}
            aria-pressed={collapsed}
          >
            {collapsed ? <PanelLeftOpen className="size-5" aria-hidden /> : <PanelLeftClose className="size-5" aria-hidden />}
            <span className={cx(collapsed && "sr-only")}>{t("nav.collapse")}</span>
          </button>
        ) : null}
      </div>
    </nav>
  );
}

/** Below sm: a bottom tab bar with Queue, Ask, Lens, Proof and More. */
export function BottomTabs({ onMore, badges }: { onMore: () => void; badges: NavBadges }) {
  return (
    <nav aria-label={t("nav.label")} className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface sm:hidden">
      <ul className="grid grid-cols-5">
        {NAV.slice(0, 4).map((item) => {
          const Icon = item.icon;
          return (
            <li key={item.key}>
              <NavLink to={item.to} className={({ isActive }) => cx("relative flex min-h-11 flex-col items-center justify-center gap-0.5 py-1.5 text-xs", isActive ? "text-text" : "text-muted")}>
                <Icon className="size-5" aria-hidden strokeWidth={1.75} />
                {t(item.label)}
                {item.key === "queue" && badges.queue ? <span className="absolute right-3 top-1 rounded-full bg-edge-bg px-1 text-[0.65rem] text-edge-fg">{badges.queue}</span> : null}
              </NavLink>
            </li>
          );
        })}
        <li>
          <button type="button" onClick={onMore} className="flex min-h-11 w-full flex-col items-center justify-center gap-0.5 py-1.5 text-xs text-muted">
            <span aria-hidden className="text-lg leading-5">⋯</span>
            {t("nav.more")}
          </button>
        </li>
      </ul>
    </nav>
  );
}
