import { useSyncExternalStore } from "react";

/** Subscribes to a CSS media query (rem-based queries respect the user's font size). */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (cb) => {
      if (typeof window === "undefined" || !window.matchMedia) return () => undefined;
      const mq = window.matchMedia(query);
      mq.addEventListener("change", cb);
      return () => mq.removeEventListener("change", cb);
    },
    () => (typeof window !== "undefined" && window.matchMedia ? window.matchMedia(query).matches : false),
    () => false,
  );
}

export const MQ = {
  sm: "(min-width: 40rem)",
  lg: "(min-width: 64rem)",
  rail: "(min-width: 72rem)",
  xl: "(min-width: 90rem)",
  xxl: "(min-width: 120rem)",
};
