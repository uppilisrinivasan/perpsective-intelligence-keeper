import { GraduationCap, Inbox, Layers, MessageSquare, Settings, ShieldCheck, type LucideIcon } from "lucide-react";
import type { CopyKey } from "@/copy/t";

export interface NavItem {
  to: string;
  label: CopyKey;
  icon: LucideIcon;
  shortcut: string;
  key: "queue" | "ask" | "lens" | "proof" | "practice" | "settings";
}

export const NAV: NavItem[] = [
  { key: "queue", to: "/queue", label: "nav.queue", icon: Inbox, shortcut: "g q" },
  { key: "ask", to: "/ask", label: "nav.ask", icon: MessageSquare, shortcut: "g a" },
  { key: "lens", to: "/lens", label: "nav.lens", icon: Layers, shortcut: "g l" },
  { key: "proof", to: "/proof", label: "nav.proof", icon: ShieldCheck, shortcut: "g p" },
  { key: "practice", to: "/practice", label: "nav.practice", icon: GraduationCap, shortcut: "g r" },
];
export const SETTINGS_NAV: NavItem = { key: "settings", to: "/settings", label: "nav.settings", icon: Settings, shortcut: "g s" };
