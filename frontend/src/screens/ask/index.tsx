import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Check, GitPullRequest, Layers, List, Pencil, Plus, Trash2, X } from "lucide-react";
import { api, call } from "@/api/client";
import { useChatExamples, useThread, useThreads } from "@/api/hooks/chat";
import { isSimulated, useStatus } from "@/api/hooks/system";
import { keys } from "@/api/keys";
import type { ChatThread } from "@/api/types";
import { AnswerHeader } from "@/components/keeper/AnswerHeader";
import { InlineError } from "@/components/keeper/States";
import { Button } from "@/components/ui/Button";
import { Dialog, Sheet } from "@/components/ui/Dialog";
import { IconButton } from "@/components/ui/IconButton";
import { Skeleton } from "@/components/ui/Skeleton";
import { SplitPane } from "@/components/ui/SplitPane";
import { t } from "@/copy/t";
import { cx } from "@/lib/cx";
import { cardId } from "@/lib/markers";
import { MQ, useMediaQuery } from "@/lib/useMedia";
import { obj, str } from "@/lib/unknown";
import type { AskContext } from "@/state/ask";
import { AskChat, SavedExample, contextLabel } from "./AskChat";

const DAY = 24 * 60 * 60 * 1000;

function groupThreads(items: ChatThread[]): Array<{ key: string; label: string; items: ChatThread[] }> {
  const now = Date.now();
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const today: ChatThread[] = [];
  const week: ChatThread[] = [];
  const earlier: ChatThread[] = [];
  for (const th of [...items].sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at))) {
    const at = Date.parse(th.updated_at);
    if (at >= startOfToday.getTime()) today.push(th);
    else if (now - at < 7 * DAY) week.push(th);
    else earlier.push(th);
  }
  return [
    { key: "today", label: t("ask.threads.today"), items: today },
    { key: "week", label: t("ask.threads.week"), items: week },
    { key: "earlier", label: t("ask.threads.earlier"), items: earlier },
  ].filter((g) => g.items.length);
}

function toAskContext(c: Record<string, unknown> | undefined): AskContext | null {
  const o = obj(c);
  const screen = str(o.screen);
  if (!screen) return null;
  return { ...(o as unknown as AskContext) };
}

function ThreadItem({ th, active, onRename, onDelete }: { th: ChatThread; active: boolean; onRename: (title: string) => void; onDelete: () => void }) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(th.title);
  const ctx = toAskContext(th.context);
  if (editing)
    return (
      <form
        className="flex items-center gap-1 px-1"
        onSubmit={(e) => {
          e.preventDefault();
          onRename(title.trim() || th.title);
          setEditing(false);
        }}
      >
        <label htmlFor={`rename-${th.id}`} className="sr-only">
          {t("ask.threads.rename")}
        </label>
        <input id={`rename-${th.id}`} autoFocus value={title} onChange={(e) => setTitle(e.target.value)} className="min-w-0 flex-1 rounded-sm border border-border-strong bg-surface px-1.5 py-0.5 text-sm" />
        <IconButton size="sm" icon={Check} label={t("common.save")} type="submit" />
        <IconButton size="sm" icon={X} label={t("common.cancel")} onClick={() => setEditing(false)} />
      </form>
    );
  return (
    <div className={cx("group flex items-center gap-1 rounded-md", active ? "bg-surface-2" : "hover:bg-surface-2")}>
      <Link to={`/ask/${th.id}`} className="flex min-w-0 flex-1 items-center gap-1.5 px-2 py-1.5 text-sm" aria-current={active ? "page" : undefined}>
        {ctx?.screen === "pr" ? <GitPullRequest className="size-3.5 shrink-0 text-muted" aria-label={contextLabel(ctx)} /> : ctx?.screen === "lens" ? <Layers className="size-3.5 shrink-0 text-muted" aria-label={contextLabel(ctx)} /> : null}
        <span className="truncate">{th.title || t("ask.threads.untitled")}</span>
      </Link>
      {th.origin !== "snapshot" ? (
        <div className="flex opacity-0 group-hover:opacity-100 group-focus-within:opacity-100">
          <IconButton size="sm" icon={Pencil} label={t("ask.threads.rename")} onClick={() => setEditing(true)} />
          <IconButton size="sm" icon={Trash2} label={t("common.delete")} onClick={onDelete} />
        </div>
      ) : null}
    </div>
  );
}

function ThreadsRail({ activeId, onNew }: { activeId?: string; onNew: () => void }) {
  const threads = useThreads();
  const status = useStatus();
  const examples = useChatExamples(Boolean(status.data && !status.data.live));
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [confirmDelete, setConfirmDelete] = useState<ChatThread | null>(null);
  const groups = useMemo(() => groupThreads(threads.data?.items ?? []), [threads.data]);
  const live = status.data?.live ?? false;
  return (
    <nav aria-label={t("ask.threads.label")} className="flex h-full flex-col gap-3 p-3">
      <Button icon={Plus} onClick={onNew} disabled={!live} title={!live ? t("common.needsKey") : undefined}>
        {t("ask.threads.new")}
      </Button>
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto">
        {threads.isLoading ? <Skeleton lines={5} /> : null}
        {threads.error ? <InlineError error={threads.error} onRetry={() => void threads.refetch()} /> : null}
        {groups.map((g) => (
          <section key={g.key}>
            <h2 className="mb-1 px-2 text-xs font-medium text-muted">{g.label}</h2>
            <ul className="space-y-0.5">
              {g.items.map((th) => (
                <li key={th.id}>
                  <ThreadItem
                    th={th}
                    active={th.id === activeId}
                    onRename={async (title) => {
                      await call(api.PATCH("/api/v1/chat/threads/{tid}", { params: { path: { tid: th.id } }, body: { title } }));
                      void qc.invalidateQueries({ queryKey: keys.threads() });
                    }}
                    onDelete={() => setConfirmDelete(th)}
                  />
                </li>
              ))}
            </ul>
          </section>
        ))}
        {!live && examples.data?.items.length ? (
          <section>
            <h2 className="mb-1 px-2 text-xs font-medium text-muted">{t("ask.examples.title")}</h2>
            <ul className="space-y-0.5">
              {examples.data.items.map((ex) => (
                <li key={ex.id}>
                  <Link to={`/ask/example:${encodeURIComponent(ex.id)}`} className={cx("block truncate rounded-md px-2 py-1.5 text-sm hover:bg-surface-2", activeId === `example:${ex.id}` && "bg-surface-2")}>
                    {ex.question}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>
      <Dialog
        open={confirmDelete !== null}
        onOpenChange={(o) => !o && setConfirmDelete(null)}
        role="alertdialog"
        title={t("ask.threads.deleteTitle")}
        description={confirmDelete?.title}
        footer={
          <>
            <Button onClick={() => setConfirmDelete(null)}>{t("common.cancel")}</Button>
            <Button
              variant="danger"
              onClick={async () => {
                const th = confirmDelete;
                setConfirmDelete(null);
                if (!th) return;
                await call(api.DELETE("/api/v1/chat/threads/{tid}", { params: { path: { tid: th.id } } }));
                void qc.invalidateQueries({ queryKey: keys.threads() });
                if (th.id === activeId) navigate("/ask");
              }}
            >
              {t("common.delete")}
            </Button>
          </>
        }
      />
    </nav>
  );
}

function ContextPanel({ threadId }: { threadId?: string }) {
  const thread = useThread(threadId);
  const cards = (thread.data?.messages ?? []).flatMap((m) => m.cards ?? []).filter((c) => c.type !== "action");
  const seen = new Set<string>();
  const unique = cards.filter((c) => {
    const k = `${c.type}:${cardId(c)}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  return (
    <aside aria-label={t("ask.context.panel")} className="h-full overflow-y-auto p-3">
      <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
        <List className="size-4" aria-hidden />
        {t("ask.context.panel")}
      </h2>
      {unique.length === 0 ? (
        <p className="text-sm text-muted">{t("ask.context.empty")}</p>
      ) : (
        <ul className="space-y-1.5 text-sm">
          {unique.map((c, i) => {
            const d = obj(c.data);
            const n = d.number ?? d.pr_number;
            const href = c.type === "pull" ? `/pr/${String(n)}` : c.type === "lens_item" ? `/lens?tab=items&item=${str(d.id) ?? ""}` : c.type === "finding" && n ? `/pr/${String(n)}?finding=${str(d.id) ?? ""}` : undefined;
            const label = str(d.title) ?? str(d.label) ?? str(d.excerpt) ?? cardId(c) ?? "";
            return (
              <li key={i} className="rounded-md border border-border p-2">
                <p className="text-xs text-muted">{t(`ask.card.${c.type}` as "ask.card.pull")}</p>
                {href ? (
                  <Link to={href} className="text-primary hover:underline k-anywhere">
                    {label}
                  </Link>
                ) : (
                  <span className="k-anywhere">{label}</span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </aside>
  );
}

/** Ask: threads rail, the chat column (max --measure-chat) and, at ≥ 90rem, the context panel. */
export default function AskScreen() {
  const { threadId } = useParams();
  const navigate = useNavigate();
  const status = useStatus();
  const isLg = useMediaQuery(MQ.lg);
  const isXl = useMediaQuery(MQ.xl);
  const [threadsOpen, setThreadsOpen] = useState(false);
  const [context, setContext] = useState<AskContext | null>(null);
  const live = status.data?.live ?? false;
  const examples = useChatExamples(Boolean(status.data && !live));
  const exampleId = threadId?.startsWith("example:") ? decodeURIComponent(threadId.slice("example:".length)) : undefined;
  const example = exampleId ? examples.data?.items.find((e) => e.id === exampleId) : undefined;
  const realThread = exampleId ? undefined : threadId;
  const thread = useThread(realThread);
  const threadContext = toAskContext(thread.data?.context);

  const chat = example ? (
    <div className="mx-auto w-full max-w-(--measure-chat) overflow-y-auto py-4">
      <SavedExample example={example} simulated={Boolean(examples.data?.simulated) || isSimulated(status.data)} />
    </div>
  ) : !live && !realThread ? (
    <div className="mx-auto w-full max-w-(--measure-chat) space-y-4 py-6">
      <p className="text-base">{t("ask.noKey.body", { provider: status.data?.provider ?? "" })}</p>
      {examples.isLoading ? <Skeleton lines={4} /> : null}
      <ul className="grid gap-2 [grid-template-columns:repeat(auto-fit,minmax(min(100%,16rem),1fr))]">
        {(examples.data?.items ?? []).map((ex) => (
          <li key={ex.id}>
            <Link to={`/ask/example:${encodeURIComponent(ex.id)}`} className="block h-full rounded-md border border-border bg-surface p-3 text-sm hover:bg-surface-2">
              {ex.question}
            </Link>
          </li>
        ))}
      </ul>
      {examples.data && !examples.data.items.length ? <p className="text-sm text-muted">{t("ask.examples.none")}</p> : null}
    </div>
  ) : (
    <AskChat
      key={realThread ?? "new"}
      threadId={realThread}
      context={realThread ? threadContext : context}
      onContextChange={realThread ? undefined : setContext}
      onThreadCreated={(id) => navigate(`/ask/${id}`, { replace: true })}
      autoFocus
    />
  );

  const rail = <ThreadsRail activeId={threadId} onNew={() => navigate("/ask")} />;

  return (
    <div className="flex h-[calc(100dvh-var(--topbar-height))] flex-col">
      <div className="flex items-center gap-2 px-(--gutter) pt-3">
        {!isLg ? <Button size="sm" icon={List} onClick={() => setThreadsOpen(true)}>{t("ask.threads.label")}</Button> : null}
        <AnswerHeader title={thread.data?.title || example?.question || t("ask.title")} className="flex-1 [&_h1]:text-xl" />
      </div>
      <div className="min-h-0 flex-1 px-(--gutter) pb-2">
        {isLg ? (
          <SplitPane
            id={isXl ? "ask3" : "ask"}
            className="h-full"
            panes={[
              { id: "threads", defaultSize: isXl ? 18 : 24, minSize: 14, content: <div className="h-full border-r border-border">{rail}</div> },
              { id: "chat", defaultSize: isXl ? 62 : 76, minSize: 40, content: <div className="flex h-full flex-col px-4">{chat}</div> },
              ...(isXl ? [{ id: "context", defaultSize: 20, minSize: 14, content: <div className="h-full border-l border-border"><ContextPanel threadId={realThread} /></div> }] : []),
            ]}
          />
        ) : (
          <div className="flex h-full flex-col">{chat}</div>
        )}
      </div>
      {!isLg ? (
        <Sheet open={threadsOpen} onOpenChange={setThreadsOpen} title={t("ask.threads.label")} side="left" width="nav">
          {rail}
        </Sheet>
      ) : null}
    </div>
  );
}
