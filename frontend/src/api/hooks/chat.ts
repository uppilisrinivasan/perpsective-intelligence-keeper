import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, call, notifyAuthRequired, urls } from "../client";
import { ApiError } from "../errors";
import { buildHeaders } from "../headers";
import { keys } from "../keys";
import { parseData, readSseStream } from "../sse";
import type { Card, ChatEventDone, ChatEventToolStep } from "../types";
import type { AskContext } from "@/state/ask";
import { obj, str } from "@/lib/unknown";

export function useThreads() {
  return useQuery({ queryKey: keys.threads(), queryFn: () => call(api.GET("/api/v1/chat/threads")) });
}

export function useThread(tid: string | undefined) {
  return useQuery({
    queryKey: keys.thread(tid ?? ""),
    queryFn: () => call(api.GET("/api/v1/chat/threads/{tid}", { params: { path: { tid: tid! } } })),
    enabled: Boolean(tid),
  });
}

export function useSuggestions(context: AskContext | null) {
  const ctx = context?.screen ?? "default";
  return useQuery({
    queryKey: keys.suggestions(ctx, context?.number),
    queryFn: () =>
      call(api.GET("/api/v1/chat/suggestions", { params: { query: { context: ctx, number: context?.number ?? null } } })),
    staleTime: 5 * 60_000,
  });
}

export function useChatExamples(enabled: boolean) {
  return useQuery({ queryKey: keys.examples(), queryFn: () => call(api.GET("/api/v1/chat/examples")), enabled, staleTime: Infinity });
}

export function createThread(context: AskContext | null) {
  return call(api.POST("/api/v1/chat/threads", { body: { context: context ? { ...context } : null } }));
}

export interface StreamingAnswer {
  userText: string;
  context: AskContext | null;
  text: string;
  steps: ChatEventToolStep[];
  cards: Card[];
  done?: ChatEventDone;
  error?: { code: string; message: string };
  streaming: boolean;
}

/**
 * Sends a message and streams the answer (POST returns text/event-stream; docs/05-api/03 §4).
 * Chat answers are not resumed: after the stream ends the persisted thread is refetched.
 */
export function useChat(threadId: string | undefined) {
  const qc = useQueryClient();
  const [answer, setAnswer] = useState<StreamingAnswer | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  useEffect(() => {
    setAnswer(null);
  }, [threadId]);

  const send = useCallback(
    async (text: string, context: AskContext | null, tidOverride?: string) => {
      const tid = tidOverride ?? threadId;
      if (!tid || !text.trim()) return;
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;
      let state: StreamingAnswer = { userText: text, context, text: "", steps: [], cards: [], streaming: true };
      const push = (patch: Partial<StreamingAnswer>) => {
        state = { ...state, ...patch };
        setAnswer(state);
      };
      push({});
      try {
        const res = await fetch(urls.chatMessages(tid), {
          method: "POST",
          credentials: "same-origin",
          headers: { ...buildHeaders("POST"), "Content-Type": "application/json", Accept: "text/event-stream" },
          body: JSON.stringify({ text, context: context ? { ...context } : null }),
          signal: ac.signal,
        });
        if (res.status === 401) notifyAuthRequired();
        const type = res.headers.get("content-type") ?? "";
        if (!res.ok || !type.includes("text/event-stream") || !res.body) {
          let body: unknown = null;
          try {
            body = await res.json();
          } catch {
            body = null;
          }
          const err = ApiError.fromBody(res.ok ? 500 : res.status, body, res.headers.get("x-request-id"));
          push({ streaming: false, error: { code: err.code, message: err.message } });
          if (err.code === "spend_cap_reached") void qc.invalidateQueries({ queryKey: keys.status() });
          return;
        }
        await readSseStream(
          res.body,
          (m) => {
            const d = parseData<Record<string, unknown>>(m) ?? {};
            switch (m.event) {
              case "chat.delta":
                push({ text: state.text + (str(d.text) ?? "") });
                break;
              case "chat.tool_step": {
                const step = d as unknown as ChatEventToolStep;
                const exists = state.steps.some((s) => s.call_id === step.call_id);
                push({ steps: exists ? state.steps.map((s) => (s.call_id === step.call_id ? { ...s, ...step } : s)) : [...state.steps, step] });
                break;
              }
              case "chat.card": {
                const card = obj(d.card) as unknown as Card;
                if (card && typeof card.type === "string") push({ cards: [...state.cards, card] });
                break;
              }
              case "chat.done":
                push({ done: d as unknown as ChatEventDone, streaming: false });
                break;
              case "chat.error":
                push({ error: { code: str(d.code) ?? "unknown", message: str(d.message) ?? "" }, streaming: false });
                if (str(d.code) === "spend_cap_reached") void qc.invalidateQueries({ queryKey: keys.status() });
                break;
              default:
                break;
            }
          },
          ac.signal,
        );
        if (state.streaming) push({ streaming: false });
      } catch (e) {
        if (ac.signal.aborted) {
          push({ streaming: false });
        } else {
          push({ streaming: false, error: { code: "network", message: e instanceof Error ? e.message : "" } });
        }
      } finally {
        void qc.invalidateQueries({ queryKey: keys.thread(tid) });
        void qc.invalidateQueries({ queryKey: keys.threads() });
      }
    },
    [threadId, qc],
  );

  const stop = useCallback(async () => {
    abortRef.current?.abort();
    if (threadId) {
      try {
        await call(api.POST("/api/v1/chat/threads/{tid}/stop", { params: { path: { tid: threadId } } }));
      } catch {
        /* the stream is already closed locally */
      }
    }
  }, [threadId]);

  const clear = useCallback(() => setAnswer(null), []);

  return { answer, send, stop, clear };
}
