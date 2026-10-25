import { useEffect, useRef } from "react";

/** Global keyboard shortcuts: g q / g a / g l / g p / g r / g s, "/" and "?". Disabled while typing. */
export const SEQUENCES: Record<string, string> = {
  q: "/queue",
  a: "/ask",
  l: "/lens",
  p: "/proof",
  r: "/practice",
  s: "/settings",
};

export function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
}

export function useGlobalShortcuts(opts: { enabled: boolean; navigate: (to: string) => void; onSlash: () => void; onHelp: () => void }) {
  const pendingG = useRef<number>(0);
  const ref = useRef(opts);
  ref.current = opts;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const o = ref.current;
      if (!o.enabled || e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey) return;
      if (isTypingTarget(e.target)) return;
      if (document.querySelector("[role=dialog][aria-modal=true]") && e.key !== "?") return;
      const now = Date.now();
      if (pendingG.current && now - pendingG.current < 1200) {
        pendingG.current = 0;
        const to = SEQUENCES[e.key.toLowerCase()];
        if (to) {
          e.preventDefault();
          o.navigate(to);
        }
        return;
      }
      if (e.key === "g") {
        pendingG.current = now;
        return;
      }
      if (e.key === "/") {
        e.preventDefault();
        o.onSlash();
      } else if (e.key === "?") {
        e.preventDefault();
        o.onHelp();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
