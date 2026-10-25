import { useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router";
import { CheckCircle2, ChevronRight, CircleX, Copy, FileText, GitPullRequest, Layers, MessageSquareQuote, RotateCcw, Sparkles, Wrench } from "lucide-react";
import type { Card, ChatEventToolStep } from "@/api/types";
import { rawRequest } from "@/api/client";
import { useConfirmableAction } from "@/api/hooks/confirm";
import { badgeClass } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { IconButton } from "@/components/ui/IconButton";
import { Markdown } from "@/components/ui/Markdown";
import { Spinner } from "@/components/ui/Spinner";
import { Tooltip } from "@/components/ui/Tooltip";
import { t } from "@/copy/t";
import { cx } from "@/lib/cx";
import { copyText } from "@/lib/clipboard";
import { formatDate, formatDurationMs, formatInterval, formatMoney, formatPercent } from "@/lib/format";
import { laneDef } from "@/lib/lanes";
import { cardKey, indexCards, prepareMarkers } from "@/lib/markers";
import { bool, num, obj, str } from "@/lib/unknown";
import { InlineError } from "./States";
import { JobProgress } from "./JobProgress";
import { errorMessage } from "@/lib/errors";
import { ApiError } from "@/api/errors";

function cardHref(card: Card): string | undefined {
  const d = obj(card.data);
  const n = num(d.number) ?? num(d.pr_number);
  switch (card.type) {
    case "pull":
      return n ? `/pr/${n}` : undefined;
    case "finding":
      return n ? `/pr/${n}?finding=${encodeURIComponent(str(d.id) ?? "")}` : undefined;
    case "lens_item":
      return `/lens?tab=items&item=${encodeURIComponent(str(d.id) ?? "")}`;
    case "comment":
      return n ? `/pr/${n}` : undefined;
    default:
      return str(d.href);
  }
}

/** An inline chip for a citation marker, colour-coded by lane, with a hover preview. */
export function CitationChip({ type, card }: { type: string; id: string; card: Card | undefined }) {
  if (!card) return <span className="mx-0.5 inline-block h-4 w-10 rounded-full k-skeleton align-middle" aria-label={t("chat.citationLoading")} />;
  const d = obj(card.data);
  const lane = str(d.lane) ?? (type === "lens_item" ? (str(d.kind) === "blind_spot" ? "blind_spot" : "edge") : undefined);
  const def = laneDef(lane ?? "baseline_only");
  const n = num(d.number) ?? num(d.pr_number);
  const label =
    type === "pull" ? t("format.prNumber", { n: n ?? "" }) : type === "comment" ? t("chat.commentChip", { author: str(d.author) ?? "", n: n ?? "" }) : (str(d.title) ?? str(d.label) ?? str(d.name) ?? "");
  const Icon = type === "pull" ? GitPullRequest : type === "lens_item" ? Layers : type === "comment" ? MessageSquareQuote : FileText;
  const href = cardHref(card);
  const preview = (
    <span className="block max-w-[20rem] space-y-0.5">
      {str(d.title) ? <span className="block font-semibold">{str(d.title)}</span> : null}
      {str(d.reason) ? <span className="block">{str(d.reason)}</span> : null}
      {str(d.excerpt) ? <span className="block italic">{str(d.excerpt)}</span> : null}
      {num(d.support) ? <span className="block">{t("lens.item.seenIn", { n: num(d.support) ?? 0 })}</span> : null}
    </span>
  );
  const cls = cx(badgeClass(def.tone), "mx-0.5 align-baseline no-underline hover:underline");
  const body = (
    <>
      <Icon className="size-[1em]" aria-hidden strokeWidth={1.75} />
      <span className="max-w-[16rem] truncate">{label}</span>
    </>
  );
  return (
    <Tooltip content={preview}>
      {href ? (
        <Link to={href} className={cls}>
          {body}
        </Link>
      ) : (
        <span tabIndex={0} className={cls}>
          {body}
        </span>
      )}
    </Tooltip>
  );
}

/** Collapsed into one line while running; "Used N sources" after, expandable into a step list with durations. */
export function ToolSteps({ steps, running }: { steps: ChatEventToolStep[]; running: boolean }) {
  const [open, setOpen] = useState(false);
  if (!steps.length) return null;
  const active = steps.filter((s) => s.status === "running");
  if (running && active.length)
    return (
      <p className="flex items-center gap-2 text-sm text-muted">
        <Spinner />
        <span className="truncate">{active.map((s) => s.label).join(t("format.listSeparator"))}…</span>
      </p>
    );
  return (
    <div className="text-sm text-muted">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} className="inline-flex items-center gap-1 hover:text-text">
        <ChevronRight className={cx("size-4 transition-transform duration-(--dur-fast)", open && "rotate-90")} aria-hidden />
        {t("chat.usedSources", { n: steps.length })}
      </button>
      {open ? (
        <ol className="mt-1 space-y-0.5 pl-5">
          {steps.map((s) => (
            <li key={s.call_id} className="flex items-center gap-1.5">
              {s.status === "error" ? <CircleX className="size-3.5 text-danger" aria-hidden /> : s.status === "done" ? <CheckCircle2 className="size-3.5 text-success" aria-hidden /> : <Spinner />}
              <span>{s.label}</span>
              {s.duration_ms ? <span className="tabular">· {formatDurationMs(s.duration_ms)}</span> : null}
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}

export function MetricCard({ card }: { card: Card }) {
  const d = obj(card.data);
  const value = num(d.value);
  const pass = bool(d.pass);
  const ci = obj(d.interval ?? d.ci);
  return (
    <div className="inline-flex items-center gap-2 rounded-md border border-border bg-surface-2 px-3 py-1.5 text-sm">
      {pass === true ? <CheckCircle2 className="size-4 text-success" aria-hidden /> : pass === false ? <CircleX className="size-4 text-danger" aria-hidden /> : null}
      <span className="text-muted">{str(d.label) ?? str(d.name)}</span>
      <span className="font-semibold tabular">{value !== undefined && value <= 1 ? formatPercent(value) : (str(d.value) ?? "")}</span>
      <span className="text-muted tabular">{formatInterval(num(ci.low), num(ci.high))}</span>
    </div>
  );
}

export function CommentCard({ card }: { card: Card }) {
  const d = obj(card.data);
  const n = num(d.pr_number) ?? num(d.number);
  return (
    <figure className="border-l-2 border-edge-border pl-3 text-sm">
      <blockquote className="k-anywhere">{str(d.excerpt)}</blockquote>
      <figcaption className="mt-0.5 text-xs text-muted">
        {str(d.author)}
        {str(d.at) ? ` · ${formatDate(str(d.at))}` : ""}
        {n ? (
          <>
            {" · "}
            <Link to={`/pr/${n}`} className="text-primary hover:underline">
              {t("format.prNumber", { n })}
            </Link>
          </>
        ) : null}
      </figcaption>
    </figure>
  );
}

/** The confirmation card for a proposed action. Confirm calls the regular API endpoint, then shows JobProgress. */
export function ActionCard({ card, disabledReason }: { card: Card; disabledReason?: string }) {
  const d = obj(card.data);
  const navigate = useNavigate();
  const [cancelled, setCancelled] = useState(false);
  const method = str(d.method) ?? "POST";
  const path = str(d.path) ?? str(d.endpoint);
  const body = obj(d.body ?? d.params);
  const estimate = num(d.estimate_usd) ?? num(d.estimate);
  const expires = str(d.expires_at);
  const expired = expires ? Date.parse(expires) < Date.now() : false;
  const label = str(d.label) ?? str(d.title) ?? "";
  const action = useConfirmableAction<void>((_v, token) => rawRequest(method, path ?? "", token ? { ...body, confirm_token: token } : body), { title: label, description: str(d.description) });
  if (cancelled) return <p className="text-xs text-muted">{t("chat.action.cancelled")}</p>;
  const reason = disabledReason ?? (expired ? t("chat.action.expired") : !path ? t("chat.action.unavailable") : undefined);
  return (
    <div className="rounded-md border border-border-strong bg-surface p-3">
      <div className="flex items-start gap-2">
        <Wrench className="mt-0.5 size-4 shrink-0 text-muted" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="font-medium">{label}</p>
          {str(d.description) ? <p className="text-sm text-muted">{str(d.description)}</p> : null}
          {estimate !== undefined ? <p className="text-sm text-muted tabular">{t("chat.action.estimate", { amount: formatMoney(estimate) })}</p> : null}
        </div>
      </div>
      {action.jobId ? (
        <div className="mt-2 space-y-1.5">
          <JobProgress jobId={action.jobId} compact />
          {str(d.href) ? (
            <Button size="sm" variant="ghost" onClick={() => navigate(str(d.href)!)}>
              {t("chat.action.openFull")}
            </Button>
          ) : null}
        </div>
      ) : (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Tooltip content={reason}>
            <span>
              <Button size="sm" variant="primary" disabled={Boolean(reason)} loading={action.pending} onClick={() => void action.run()}>
                {t("common.confirm")}
              </Button>
            </span>
          </Tooltip>
          <Button size="sm" onClick={() => setCancelled(true)}>
            {t("common.cancel")}
          </Button>
        </div>
      )}
      {action.error ? <InlineError className="mt-2" error={action.error} message={action.error instanceof ApiError ? errorMessage(action.error) : undefined} /> : null}
    </div>
  );
}

export interface ChatMessageView {
  id: string;
  role: "user" | "assistant";
  text: string;
  cards: Card[];
  steps: ChatEventToolStep[];
  streaming?: boolean;
  done?: boolean;
  model?: string | null;
  costUsd?: number | null;
  contextLabel?: string;
  error?: { code: string; message: string };
  suggestions?: string[];
}

export function toolTraceToSteps(trace: Array<Record<string, unknown>> | undefined): ChatEventToolStep[] {
  return (trace ?? []).map((s, i) => ({
    call_id: str(s.call_id) ?? `t${i}`,
    name: str(s.name) ?? "",
    label: str(s.label) ?? str(s.name) ?? "",
    status: (str(s.status) as ChatEventToolStep["status"]) ?? "done",
    duration_ms: num(s.duration_ms) ?? null,
  }));
}

/** User messages are right-aligned bubbles; assistant answers are full-width markdown with chips and cards. */
export function ChatMessage({ m, onRetry, actionDisabledReason, onSuggestion }: { m: ChatMessageView; onRetry?: () => void; actionDisabledReason?: string; onSuggestion?: (s: string) => void }) {
  const cardIndex = useMemo(() => indexCards(m.cards), [m.cards]);
  const text = useMemo(() => prepareMarkers(m.text, cardIndex, Boolean(m.done)), [m.text, cardIndex, m.done]);
  if (m.role === "user")
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-lg bg-surface-2 px-3.5 py-2 text-base whitespace-pre-wrap k-anywhere">
          {m.contextLabel ? <span className={cx(badgeClass("outline"), "mb-1")}>{m.contextLabel}</span> : null}
          <p>{m.text}</p>
        </div>
      </div>
    );
  const actions = m.cards.filter((c) => c.type === "action");
  const metrics = m.cards.filter((c) => c.type === "metric");
  const comments = m.cards.filter((c) => c.type === "comment" && !m.text.includes(`[[comment:`));
  const renderCitation = (type: string, id: string): ReactNode => <CitationChip type={type} id={id} card={cardIndex.get(cardKey(type, id))} />;
  return (
    <div className="space-y-2" aria-busy={m.streaming || undefined}>
      <ToolSteps steps={m.steps} running={Boolean(m.streaming)} />
      {text ? (
        <div className={cx(m.streaming && "k-caret")}>
          <Markdown source={text} renderCitation={renderCitation} className="text-base" />
        </div>
      ) : m.streaming && !m.steps.length ? (
        <p className="text-sm text-muted">
          <Spinner /> {t("chat.thinking")}
        </p>
      ) : null}
      {metrics.length ? (
        <div className="flex flex-wrap gap-2">
          {metrics.map((c, i) => (
            <MetricCard key={i} card={c} />
          ))}
        </div>
      ) : null}
      {comments.map((c, i) => (
        <CommentCard key={i} card={c} />
      ))}
      {actions.map((c, i) => (
        <ActionCard key={i} card={c} disabledReason={actionDisabledReason} />
      ))}
      {m.error ? <InlineError error={new ApiError(0, m.error.code, m.error.message)} onRetry={onRetry} /> : null}
      {m.done && !m.streaming ? (
        <div className="flex items-center gap-1 text-muted">
          <IconButton size="sm" icon={Copy} label={t("common.copy")} onClick={() => void copyText(m.text.replace(/\[\[[^\]]+\]\]/g, ""))} />
          {m.model || m.costUsd ? (
            <Tooltip content={[m.model, m.costUsd !== null && m.costUsd !== undefined ? formatMoney(m.costUsd) : null].filter(Boolean).join(t("format.listSeparator"))}>
              <span tabIndex={0} className="inline-flex size-7 items-center justify-center rounded-md hover:bg-surface-2" aria-label={t("chat.modelInfo")}>
                <Sparkles className="size-4" aria-hidden />
              </span>
            </Tooltip>
          ) : null}
          {onRetry ? <IconButton size="sm" icon={RotateCcw} label={t("common.retry")} onClick={onRetry} /> : null}
        </div>
      ) : null}
      {m.suggestions?.length && onSuggestion ? (
        <div className="flex flex-wrap gap-1.5">
          {m.suggestions.slice(0, 3).map((s) => (
            <button key={s} type="button" onClick={() => onSuggestion(s)} className="rounded-full border border-border px-3 py-1 text-sm hover:bg-surface-2">
              {s}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
