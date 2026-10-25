import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, LogOut, Trash2 } from "lucide-react";
import { api, call } from "@/api/client";
import { isApiError } from "@/api/errors";
import { isFeedbackPending, usePracticeFeedback, usePracticeItem, usePracticeSession } from "@/api/hooks/practice";
import { useStatus } from "@/api/hooks/system";
import { keys } from "@/api/keys";
import type { PracticeFeedback, PracticeNote } from "@/api/types";
import { AnswerHeader } from "@/components/keeper/AnswerHeader";
import { DiffView } from "@/components/keeper/DiffView";
import { InlineError, KeyRequired, PageError } from "@/components/keeper/States";
import { Badge } from "@/components/ui/Badge";
import { Button, buttonClass } from "@/components/ui/Button";
import { Disclosure } from "@/components/ui/Disclosure";
import { TextArea } from "@/components/ui/Field";
import { Markdown } from "@/components/ui/Markdown";
import { Delayed, Skeleton } from "@/components/ui/Skeleton";
import { Spinner } from "@/components/ui/Spinner";
import { t } from "@/copy/t";
import { personName } from "@/lib/format";
import { readLocal, removeLocal, writeLocal } from "@/lib/storage";
import { num, obj, objs, str } from "@/lib/unknown";
import { ask } from "@/state/ask";
import { useKeyEnvVar } from "@/shell/AppShell";
import { Hints, kindLabel, notesKey, Reveal, SessionResult, type LocalNotes } from "./shared";

function NoteEditor({ initial, onSave, onDelete, line }: { initial: string; onSave: (v: string) => void; onDelete: () => void; line: number }) {
  const [v, setV] = useState(initial);
  return (
    <div className="k-card max-w-[40rem] space-y-2 p-2.5">
      <TextArea label={t("practice.note.label", { n: line })} value={v} onChange={(e) => setV(e.target.value)} rows={2} autoFocus={!initial} />
      <div className="flex gap-2">
        <Button size="sm" variant="secondary" onClick={() => onSave(v)} disabled={!v.trim()}>
          {t("common.save")}
        </Button>
        <Button size="sm" variant="ghost" icon={Trash2} onClick={onDelete}>
          {t("common.delete")}
        </Button>
      </div>
    </div>
  );
}

/** One practice item: the diff with gutter notes (kept locally until submit), then hints or the reveal. */
export default function PracticeItemScreen() {
  const { sessionId = "", index = "0" } = useParams();
  const n = Number(index);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const status = useStatus();
  const envVar = useKeyEnvVar();
  const session = usePracticeSession(sessionId);
  const item = usePracticeItem(sessionId, n);
  const key = notesKey(sessionId, n);
  const [notes, setNotes] = useState<LocalNotes>(() => readLocal<LocalNotes>(key, { lines: {}, general: "" }));
  const [openLines, setOpenLines] = useState<Set<string>>(new Set());
  const [submitted, setSubmitted] = useState<PracticeFeedback | null>(null);
  const [submittedNotes, setSubmittedNotes] = useState<PracticeNote[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const kind = session.data?.kind ?? "";
  const alreadySubmitted = Boolean(item.data?.saved_notes?.length);
  const feedback = usePracticeFeedback(sessionId, n, Boolean(submitted) || alreadySubmitted);
  const fb = feedback.data ?? submitted;

  // "Test without the tool": Ask is hidden during before and after.
  useEffect(() => {
    ask.setHidden(kind === "before" || kind === "after");
    return () => ask.setHidden(false);
  }, [kind]);

  useEffect(() => {
    setNotes(readLocal<LocalNotes>(key, { lines: {}, general: "" }));
    setSubmitted(null);
    setOpenLines(new Set());
  }, [key]);

  useEffect(() => {
    if (session.data?.status === "completed" && session.data.result) setResult(session.data.result);
  }, [session.data]);

  const save = (next: LocalNotes) => {
    setNotes(next);
    writeLocal(key, next);
  };

  const noteLines = useMemo(() => new Set([...Object.keys(notes.lines), ...openLines]), [notes.lines, openLines]);
  const allNotes: PracticeNote[] = useMemo(() => {
    const list: PracticeNote[] = Object.entries(notes.lines).map(([k, text]) => {
      const i = k.lastIndexOf(":");
      return { scope: "line", path: k.slice(0, i), line: Number(k.slice(i + 1)), text };
    });
    if (notes.general.trim()) list.push({ scope: "pr", text: notes.general.trim() });
    return list;
  }, [notes]);

  if (session.isLoading || item.isLoading)
    return (
      <div className="k-page">
        <Delayed>
          <Skeleton shape="block" className="mb-4 h-16" />
          <Skeleton lines={10} />
        </Delayed>
      </div>
    );
  if (session.error) return <PageError error={session.error} onRetry={() => void session.refetch()} />;
  if (item.error) return <PageError error={item.error} onRetry={() => void item.refetch()} />;
  const s = session.data!;
  const it = item.data!;
  const target = s.target ? personName(s.target) : t("people.unknown");
  const total = it.total || s.items.length;
  const last = n + 1 >= total;
  const attempt = fb?.attempt ?? it.attempt;
  const hints = objs(fb?.hints);
  const reveal = fb?.reveal ? obj(fb.reveal) : null;
  const pending = isFeedbackPending(fb?.status);
  const showHints = kind === "learn" && hints.length > 0 && !reveal;
  const done = Boolean(fb) && !pending;
  const savedOnly = (kind === "before" || kind === "after") && done;

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await call(api.POST("/api/v1/practice/sessions/{sid}/items/{n}/answers", { params: { path: { sid: sessionId, n } }, body: { notes: allNotes } }));
      setSubmittedNotes(allNotes);
      setSubmitted(res);
      qc.setQueryData(keys.practiceFeedback(sessionId, n), res);
      removeLocal(key);
      void qc.invalidateQueries({ queryKey: keys.practiceSession(sessionId) });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const next = async () => {
    if (!last) {
      navigate(`/practice/${sessionId}/${n + 1}`);
      return;
    }
    setBusy(true);
    try {
      const r = await call(api.POST("/api/v1/practice/sessions/{sid}/complete", { params: { path: { sid: sessionId } } }));
      setResult(r.result);
      void qc.invalidateQueries({ queryKey: ["practice"] });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const tryAgain = () => {
    setSubmitted(null);
    void qc.removeQueries({ queryKey: keys.practiceFeedback(sessionId, n) });
    const restored: LocalNotes = { lines: {}, general: "" };
    for (const note of submittedNotes) {
      if (note.scope === "pr") restored.general = note.text;
      else if (note.path && note.line) restored.lines[`${note.path}:${note.line}`] = note.text;
    }
    save(restored);
  };

  const noteText = (noteId: unknown): string | undefined => {
    const source = submittedNotes.length ? submittedNotes : (it.saved_notes ?? []).map((x) => ({ text: str(obj(x).text) ?? "", id: str(obj(x).id) }));
    const idx = num(noteId);
    if (idx !== undefined) return source[idx]?.text;
    const id = str(noteId);
    const match = (it.saved_notes ?? []).find((x) => str(obj(x).id) === id);
    return match ? str(obj(match).text) : id;
  };

  if (result)
    return (
      <div className="k-page mx-auto w-full max-w-[60rem] space-y-4">
        <AnswerHeader title={t("practice.item.complete", { kind: kindLabel(kind) })} />
        <SessionResult result={result} maintainer={target} kind={kind} />
        <Link to="/practice" className={buttonClass("primary")}>
          {t("practice.item.backToPractice")}
        </Link>
      </div>
    );

  return (
    <div className="k-page mx-auto w-full max-w-[110rem] space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
        <Badge tone="outline">{kindLabel(kind)}</Badge>
        <span>{t("practice.item.position", { i: n + 1, total })}</span>
        {s.origin === "snapshot" ? <Badge>{t("common.saved_run")}</Badge> : null}
        <Link to="/practice" className="ml-auto inline-flex items-center gap-1 hover:text-text">
          <LogOut className="size-4" aria-hidden />
          {t("practice.item.exit")}
        </Link>
      </div>
      <AnswerHeader title={<><span className="mr-2 text-muted tabular">{t("format.prNumber", { n: it.pr_number })}</span>{it.title}</>} />
      {it.body_md ? (
        <Disclosure summary={t("practice.item.description")} defaultOpen>
          <Markdown source={it.body_md} className="text-sm" />
        </Disclosure>
      ) : null}
      {!done ? <p className="text-sm text-muted">{t("practice.item.instructions")}</p> : null}
      <DiffView
        files={it.diff}
        mode="practice"
        noteLines={done ? new Set() : noteLines}
        onLineClick={
          done
            ? undefined
            : (path, line) => {
                const k = `${path}:${line}`;
                setOpenLines((o) => new Set(o).add(k));
              }
        }
        renderNote={(path, line) => {
          const k = `${path}:${line}`;
          return (
            <NoteEditor
              key={k}
              line={line}
              initial={notes.lines[k] ?? ""}
              onSave={(v) => save({ ...notes, lines: { ...notes.lines, [k]: v } })}
              onDelete={() => {
                const lines = { ...notes.lines };
                delete lines[k];
                save({ ...notes, lines });
                setOpenLines((o) => {
                  const nx = new Set(o);
                  nx.delete(k);
                  return nx;
                });
              }}
            />
          );
        }}
      />
      {!done ? (
        <div className="space-y-3">
          <TextArea label={t("practice.item.general")} value={notes.general} onChange={(e) => save({ ...notes, general: e.target.value })} rows={3} />
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary" loading={busy || pending} disabled={pending} onClick={() => void submit()}>
              {attempt > 1 ? t("practice.item.submitAgain") : t("practice.item.submit")}
            </Button>
            <span className="text-xs text-muted">{t("practice.item.notesCount", { n: allNotes.length })}</span>
          </div>
        </div>
      ) : null}
      {pending ? (
        <p className="flex items-center gap-2 text-sm text-muted" role="status">
          <Spinner /> {t("practice.item.scoring")}
        </p>
      ) : null}
      {error ? (
        isApiError(error, "no_api_key") ? (
          <KeyRequired what={t("practice.item.needsKey", { provider: status.data?.provider ?? "" })} provider={status.data?.provider ?? ""} envVar={envVar} />
        ) : (
          <InlineError error={error} />
        )
      ) : null}
      {savedOnly ? (
        <div className="flex flex-wrap items-center gap-3 rounded-md bg-success-bg p-3 text-success-fg">
          <span>{t("practice.item.saved")}</span>
          <Button variant="primary" iconEnd={ArrowRight} loading={busy} onClick={() => void next()}>
            {last ? t("practice.item.finish") : t("practice.item.next")}
          </Button>
        </div>
      ) : null}
      {showHints ? (
        <div className="space-y-3">
          <Hints hints={hints} />
          <Button variant="primary" onClick={tryAgain}>
            {t("practice.item.tryAgain")}
          </Button>
        </div>
      ) : null}
      {reveal && !savedOnly ? (
        <div className="space-y-3">
          <Reveal reveal={reveal} maintainer={target} noteText={noteText} simulated={fb?.scoring_simulated} />
          {kind !== "taste" || !last ? (
            <Button variant="primary" iconEnd={ArrowRight} loading={busy} onClick={() => void next()}>
              {last ? t("practice.item.finish") : t("practice.item.next")}
            </Button>
          ) : (
            <Link to="/practice" className={buttonClass("primary")}>
              {t("practice.item.backToPractice")}
            </Link>
          )}
        </div>
      ) : null}
      {done && !reveal && !showHints && !savedOnly ? <p className="text-sm text-muted">{t("practice.item.noFeedback")}</p> : null}
    </div>
  );
}
