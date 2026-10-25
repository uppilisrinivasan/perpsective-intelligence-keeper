import { createStore, useStore } from "@/lib/store";
import { readLocal, writeLocal } from "@/lib/storage";

/** The guided tour. Progress is not persisted mid-way; only "seen" is (localStorage keeper.tour.v1). */
export const TOUR_STORAGE_KEY = "keeper.tour.v1";

export interface TourState {
  active: boolean;
  index: number;
  welcome: boolean;
  finished: boolean;
}

export const tourStore = createStore<TourState>({
  active: false,
  index: 0,
  welcome: readLocal<string | null>(TOUR_STORAGE_KEY, null) === null,
  finished: false,
});

export function useTour(): TourState {
  return useStore(tourStore);
}

function markSeen(outcome: "done" | "skipped" | "explore"): void {
  writeLocal(TOUR_STORAGE_KEY, { outcome, at: new Date().toISOString() });
}

export const tour = {
  start() {
    tourStore.set({ active: true, index: 0, welcome: false, finished: false });
  },
  explore() {
    markSeen("explore");
    tourStore.set({ active: false, index: 0, welcome: false, finished: false });
  },
  next(total: number) {
    tourStore.set((s) => {
      if (s.index + 1 >= total) {
        markSeen("done");
        return { active: false, index: 0, welcome: false, finished: true };
      }
      return { ...s, index: s.index + 1 };
    });
  },
  back() {
    tourStore.set((s) => ({ ...s, index: Math.max(0, s.index - 1) }));
  },
  skip() {
    markSeen("skipped");
    tourStore.set({ active: false, index: 0, welcome: false, finished: false });
  },
  clearFinished() {
    tourStore.set((s) => ({ ...s, finished: false }));
  },
};
