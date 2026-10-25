import { useLayoutEffect, useRef, useState, type RefObject } from "react";

/** Observes an element's inline size (for layouts that must switch component trees, not just styles). */
export function useContainerWidth<T extends HTMLElement>(): [RefObject<T | null>, number] {
  const ref = useRef<T | null>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    setWidth(el.getBoundingClientRect().width);
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width;
      if (w !== undefined) setWidth(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width];
}

/** Converts rem to CSS pixels using the root font size (respects the user's browser font setting). */
export function remToPx(rem: number): number {
  if (typeof window === "undefined") return rem * 16;
  const fs = parseFloat(getComputedStyle(document.documentElement).fontSize);
  return rem * (Number.isFinite(fs) && fs > 0 ? fs : 16);
}
