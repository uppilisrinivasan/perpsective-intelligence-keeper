import { createStore, useStore } from "@/lib/store";

/**
 * The Ask drawer. The context is what the user is looking at; it is sent with each message as
 * ChatSend.context and used for GET /chat/suggestions?context=&number=.
 */
export interface AskContext {
  screen: "queue" | "pr" | "lens" | "proof" | "practice" | "ask";
  number?: number;
  finding_id?: string;
  finding_title?: string;
  lens_id?: string;
  item_id?: string;
  person_name?: string;
  run_id?: string;
  session_id?: string;
}

export interface AskDrawerState {
  open: boolean;
  context: AskContext | null;
  /** Thread per context key, so the drawer keeps its conversation while navigating in the same context. */
  threads: Record<string, string>;
  prefill?: string;
  /** A one-off message shown at the top of the drawer (the end of the tour). */
  intro?: string;
  hidden: boolean;
}

export const askStore = createStore<AskDrawerState>({ open: false, context: null, threads: {}, hidden: false });

export function useAsk(): AskDrawerState {
  return useStore(askStore);
}

export function contextKey(c: AskContext | null): string {
  if (!c) return "none";
  return [c.screen, c.number, c.finding_id, c.lens_id, c.item_id, c.run_id, c.session_id].filter((x) => x !== undefined).join(":");
}

export const ask = {
  open(context: AskContext | null, prefill?: string, intro?: string) {
    askStore.set((s) => ({ ...s, open: true, context, prefill, intro }));
  },
  close() {
    askStore.set((s) => ({ ...s, open: false, prefill: undefined, intro: undefined }));
  },
  setContext(context: AskContext | null) {
    askStore.set((s) => ({ ...s, context }));
  },
  setThread(key: string, tid: string) {
    askStore.set((s) => ({ ...s, threads: { ...s.threads, [key]: tid } }));
  },
  /** Practice "before"/"after" hide Ask ("test without the tool"). */
  setHidden(hidden: boolean) {
    askStore.set((s) => ({ ...s, hidden, open: hidden ? false : s.open }));
  },
};
