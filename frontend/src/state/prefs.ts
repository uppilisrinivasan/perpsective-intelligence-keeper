import { createStore, useStore } from "@/lib/store";
import { readLocal, writeLocal } from "@/lib/storage";

/** Per-browser preferences (server-side editable settings live in Settings → Preferences). */
export interface LocalPrefs {
  railCollapsed: boolean;
  shortcuts: boolean;
  diffWrap: boolean | null;
  diffSplit: boolean | null;
}

const KEY = "keeper.prefs.v1";
const defaults: LocalPrefs = { railCollapsed: false, shortcuts: true, diffWrap: null, diffSplit: null };

export const prefsStore = createStore<LocalPrefs>({ ...defaults, ...readLocal<Partial<LocalPrefs>>(KEY, {}) }, (v) =>
  writeLocal(KEY, v),
);

export function usePrefs(): LocalPrefs {
  return useStore(prefsStore);
}

export function setPref<K extends keyof LocalPrefs>(key: K, value: LocalPrefs[K]): void {
  prefsStore.set((p) => ({ ...p, [key]: value }));
}

/** Applies the theme, density and motion settings to the document root. */
export function applyAppearance(theme: string | undefined, motion: string | undefined, density: string | undefined): void {
  const root = document.documentElement;
  if (theme === "light" || theme === "dark") root.dataset.theme = theme;
  else delete root.dataset.theme;
  if (motion === "on" || motion === "reduced") root.dataset.motion = "reduced";
  else delete root.dataset.motion;
  if (density === "compact") root.dataset.density = "compact";
  else delete root.dataset.density;
}
