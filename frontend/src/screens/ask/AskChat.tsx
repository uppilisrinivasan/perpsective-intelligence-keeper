import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { MessageSquare } from "lucide-react";
import { createThread, useChat, useSuggestions, useThread } from "@/api/hooks/chat";
import { isSimulated, useProjectId, useStatus } from "@/api/hooks/system";
import { useQueue } from "@/api/hooks/queue";
import { keys } from "@/api/keys";
import type { ChatExample } from "@/api/types";
import { ChatInput, type MentionOption } from "@/components/keeper/ChatInput";
import { ChatMessage, toolTraceToSteps, type ChatMessageView } from "@/components/keeper/Chat";
import { InlineError } from "@/components/keeper/States";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { t } from "@/copy/t";
import { cx } from "@/lib/cx";
import { formatMoney } from "@/lib/format";
import type { AskContext } from "@/state/ask";
import { useCapReason } from "@/screens/shared/permissions";

export function contextLabel(c: AskContext | null): string | undefined {
  if (!c) return undefined;
  switch (c.screen) {
    case "pr":
      return c.finding_title ? t("ask.context.finding", { n: c.number ?? "", title: c.finding_title }) : t("ask.context.pr", { n: c.number ?? "" });
    case "queue":
      return t("ask.context.queue");
    case "lens":
      return c.person_name ? t("ask.context.lensOf", { name: c.person_name }) : t("ask.context.lens");
    case "proof":
      return t("ask.context.proof");
    case "practice":
      return t("ask.context.practice");
    default:
      return undefined;
  }
}

function SuggestionGrid({ items, onPick }: { items: string[]; onPick: (s: string) => void }) {
  if (!items.length) return null;
  return (
    <ul className="grid gap-2 [grid-template-columns:repeat(auto-fit,minmax(min(100%,14rem),1fr))]">
      {items.map((s) => (
        <li key={s}>
          <button type="button" onClick={() => onPick(s)} className="h-full w-full rounded-md border border-border bg-surface p-3 text-left text-sm hover:bg-surface-2">
            {s}
          </button>
        </li>
      ))}
    </ul>
  );
}

/** A saved example thread (no-key mode), read-only and labelled "Saved". */
export function SavedExample({ example, simulated }: { example: ChatExample; simulated: boolean }) {
  const q: ChatMessageView = { id: `${example.id}-q`, role: "user", text: example.question, cards: [], steps: [] };
  const a: ChatMessageView = { id: `${example.id}-a`, role: "assistant", text: example.answer_md, cards: example.cards ?? [], steps: toolTraceToSteps(example.tool_trace), done: true };
  return (
    <div className="space-y-4">
      <Badge tone={simulated ? "warning" : "neutral"}>{simulated ? t("ask.savedSimulated") : t("ask.saved")}</Badge>
      <ChatMessage m={q} />
      <ChatMessage m={a} actionDisabledReason={t("ask.savedActions")} />
    </div>
  );
}

export interface AskChatProps {
  threadId?: string;
  context: AskContext | null;
  onContextChange?: (c: AskContext | null) => void;
  onThreadCreated?: (tid: string) => void;
  compact?: boolean;
  prefill?: string;
  autoFocus?: boolean;
}

/** The chat column shared by the Ask page and the Ask drawer. */
export function AskChat({ threadId, context, onContextChange, onThreadCreated, compact, prefill, autoFocus }: AskChatProps) {
  const status = useStatus();
  const pid = useProjectId();
  const qc = useQueryClient();
  const live = status.data?.live ?? false;
  const capReason = useCapReason();
  const thread = useThread(threadId);
  const { answer, send, stop } = useChat(threadId);
  const suggestions = useSuggestions(context);
  const queue = useQueue(live ? pid : undefined, "attention");
  const [createError, setCreateError] = useState<unknown>(null);
  const [pendingTid, setPendingTid] = useState<string | undefined>(undefined);
  const bottomRef = useRef<HTMLDivElement>(null);
  const announced = useRef<string | null>(null);
  const [announce, setAnnounce] = useState("");
  const tid = threadId ?? pendingTid;

  const persisted: ChatMessageView[] = useMemo(
    () =>
      (thread.data?.messages ?? []).map((m) => ({
        id: m.id,
        role: m.role === "user" ? "user" : "assistant",
        text: m.content_md,
        cards: m.cards ?? [],
        steps: toolTraceToSteps(m.tool_trace),
        done: true,
        model: m.model,
        costUsd: m.cost_usd,
      })),
    [thread.data],
  );

  const doneId = answer?.done?.message_id;
  const persistedHasAnswer = Boolean(doneId && persisted.some((m) => m.id === doneId));
  const showStreaming = answer && !persistedHasAnswer;
  const lastUserText = answer?.userText;

  const views: ChatMessageView[] = [...persisted];
  if (showStreaming && answer) {
    if (!persisted.some((m) => m.role === "user" && m.text === answer.userText && persisted.indexOf(m) >= persisted.length - 2))
      views.push({ id: "pending-user", role: "user", text: answer.userText, cards: [], steps: [], contextLabel: contextLabel(answer.context) });
    views.push({
      id: "pending-answer",
      role: "assistant",
      text: answer.text,
      cards: answer.cards,
      steps: answer.steps,
      streaming: answer.streaming,
      done: Boolean(answer.done) || (!answer.streaming && !answer.error),
      model: answer.done?.model_display ?? null,
      costUsd: answer.done?.cost_usd ?? null,
      error: answer.error,
      suggestions: answer.done?.suggestions,
    });
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end", behavior: "auto" });
  }, [views.length, answer?.text]);

  useEffect(() => {
    if (answer && !answer.streaming && answer.done && announced.current !== (doneId ?? "x")) {
      announced.current = doneId ?? "x";
      setAnnounce(t("chat.answerReady"));
    }
  }, [answer, doneId]);

  const onSend = async (text: string) => {
    setCreateError(null);
    let id = tid;
    if (!id) {
      try {
        const created = await createThread(context);
        id = created.id;
        setPendingTid(id);
        qc.setQueryData(keys.thread(id), created);
        void qc.invalidateQueries({ queryKey: keys.threads() });
        onThreadCreated?.(id);
      } catch (e) {
        setCreateError(e);
        return;
      }
    }
    await send(text, context, id);
  };

  const mentions: MentionOption[] = (queue.data?.items ?? []).map((r) => ({ key: `pr:${r.number}`, label: `#${r.number} ${r.title}`, hint: t("ask.mention.pr") }));
  const onMention = (key: string) => {
    const [kind, value] = key.split(":");
    if (kind === "pr" && value) onContextChange?.({ screen: "pr", number: Number(value) });
  };

  const empty = views.length === 0;
  const model = status.data?.models.find((m) => m.role === "assistant") ?? status.data?.models.find((m) => m.role === "judge");
  const estimate = status.data?.estimates?.ask_answer;
  const disabledReason = !live
    ? t("ask.noKeyInput", { provider: status.data?.provider ?? "" })
    : capReason;

  return (
    <div className={cx("flex h-full min-h-0 flex-col", compact ? "" : "mx-auto w-full max-w-(--measure-chat)")}>
      <div className="flex-1 overflow-y-auto px-1 py-4" aria-live="off">
        {thread.isLoading && threadId ? (
          <Skeleton lines={4} />
        ) : empty ? (
          <div className="flex flex-col items-center gap-5 py-6 text-center">
            <MessageSquare className="size-8 text-muted" aria-hidden />
            <p className="text-base text-muted">{t("ask.empty")}</p>
            <div className="w-full text-left">
              <SuggestionGrid items={(suggestions.data?.items ?? []).map((s) => s.text)} onPick={(s) => void onSend(s)} />
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {views.map((m, i) => (
              <ChatMessage
                key={m.id}
                m={m}
                actionDisabledReason={!live ? t("common.needsKey") : capReason}
                onSuggestion={i === views.length - 1 ? (s) => void onSend(s) : undefined}
                onRetry={m.id === "pending-answer" && lastUserText && live ? () => void onSend(lastUserText) : undefined}
              />
            ))}
          </div>
        )}
        {createError ? <InlineError error={createError} /> : null}
        {thread.error && threadId ? <InlineError error={thread.error} onRetry={() => void thread.refetch()} /> : null}
        <div ref={bottomRef} />
      </div>
      <div className="sr-only" aria-live="polite">
        {announce}
      </div>
      <div className="border-t border-border pt-3 pb-2">
        <ChatInput
          onSend={(s) => void onSend(s)}
          onStop={() => void stop()}
          streaming={Boolean(answer?.streaming)}
          disabled={Boolean(disabledReason)}
          disabledReason={disabledReason}
          contextLabel={contextLabel(context)}
          onRemoveContext={onContextChange ? () => onContextChange(null) : undefined}
          mentions={mentions}
          onMention={onMention}
          autoFocus={autoFocus}
          prefill={prefill}
        />
        <p className="mt-1.5 text-xs text-muted">
          {model ? (estimate !== undefined ? t("ask.footer", { model: model.display, cost: formatMoney(estimate) }) : t("ask.footerNoCost", { model: model.display })) : t("ask.footerNoModel")}
          {isSimulated(status.data) ? ` ${t("ask.footerSimulated")}` : ""}
        </p>
      </div>
    </div>
  );
}
