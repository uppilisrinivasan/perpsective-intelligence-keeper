import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Copy, Download, FileJson, FileText } from "lucide-react";
import type { ReviewDraft, Schemas } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Menu } from "@/components/ui/Menu";
import { Markdown } from "@/components/ui/Markdown";
import { Segmented } from "@/components/ui/Segmented";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { Spinner } from "@/components/ui/Spinner";
import { t } from "@/copy/t";
import { copyText, downloadText } from "@/lib/clipboard";
import { toast } from "@/state/toasts";
import { InlineError } from "./States";

type ExportOut = Schemas["ReviewDraftExport"];
const AUTOSAVE_MS = 800;

/** The editable review draft ("Drafted by Keeper"), autosaved (PUT, debounced 800 ms), copy and export. */
export function ReviewDraftPanel({ draft, onSave, onExport, onLocate, readOnlyReason }: {
  draft: ReviewDraft;
  onSave: (body_md: string) => Promise<unknown>;
  onExport: (format: "md" | "github_json") => Promise<ExportOut>;
  onLocate?: (path: string, line: number) => void;
  readOnlyReason?: string;
}) {
  const [body, setBody] = useState(draft.body_md);
  const [mode, setMode] = useState<"edit" | "preview">("preview");
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [saveError, setSaveError] = useState<unknown>(null);
  const [gh, setGh] = useState<ExportOut | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSaved = useRef(draft.body_md);

  useEffect(() => {
    if (draft.body_md !== lastSaved.current && saveState !== "saving") {
      setBody(draft.body_md);
      lastSaved.current = draft.body_md;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft.body_md]);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const change = (v: string) => {
    setBody(v);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      setSaveState("saving");
      try {
        await onSave(v);
        lastSaved.current = v;
        setSaveState("saved");
      } catch (e) {
        setSaveError(e);
        setSaveState("error");
      }
    }, AUTOSAVE_MS);
  };

  const copyReview = async () => {
    try {
      const out = await onExport("md");
      if (await copyText(out.content)) toast({ tone: "success", title: t("draft.copiedToast") });
    } catch {
      if (await copyText(body)) toast({ tone: "success", title: t("draft.copiedToast") });
    }
  };

  return (
    <section className="space-y-3" aria-labelledby="draft-title">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="draft-title" className="text-lg font-semibold">
          {draft.header || t("draft.title")}
        </h2>
        <Badge tone="outline">{draft.label || t("common.drafted")}</Badge>
        <span className="text-xs text-muted" aria-live="polite">
          {saveState === "saving" ? (
            <span className="inline-flex items-center gap-1">
              <Spinner /> {t("common.saving")}
            </span>
          ) : saveState === "saved" ? (
            <span className="inline-flex items-center gap-1">
              <Check className="size-3" aria-hidden /> {t("common.saved")}
            </span>
          ) : draft.edited_by_user ? (
            t("draft.edited")
          ) : null}
        </span>
        <div className="ml-auto flex flex-wrap gap-2">
          <Segmented
            size="sm"
            label={t("draft.mode")}
            value={mode}
            onChange={(v) => setMode(v as "edit" | "preview")}
            options={[
              { value: "preview", label: t("draft.preview") },
              { value: "edit", label: t("common.edit"), disabled: Boolean(readOnlyReason) },
            ]}
          />
          <Button size="sm" variant="secondary" icon={Copy} onClick={copyReview}>
            {t("draft.copy")}
          </Button>
          <Menu
            label={t("draft.export")}
            trigger={
              <Button size="sm" iconEnd={ChevronDown} icon={Download}>
                {t("draft.export")}
              </Button>
            }
            items={[
              {
                key: "md",
                label: t("draft.export.md"),
                icon: FileText,
                onSelect: async () => {
                  const out = await onExport("md");
                  downloadText(out.filename, out.content, "text/markdown");
                },
              },
              {
                key: "gh",
                label: t("draft.export.github"),
                icon: FileJson,
                onSelect: async () => {
                  const out = await onExport("github_json");
                  setGh(out);
                },
              },
            ]}
          />
        </div>
      </div>
      {saveState === "error" ? <InlineError error={saveError} /> : null}
      {mode === "edit" && !readOnlyReason ? (
        <div>
          <label htmlFor="draft-body" className="sr-only">
            {t("draft.bodyLabel")}
          </label>
          <textarea
            id="draft-body"
            value={body}
            onChange={(e) => change(e.target.value)}
            rows={10}
            className="w-full rounded-md border border-border-strong bg-surface p-3 font-mono text-sm"
          />
        </div>
      ) : (
        <div className="rounded-md border border-border bg-surface p-3">
          <Markdown source={body} className="text-sm" />
        </div>
      )}
      {draft.comments.length ? (
        <div>
          <h3 className="text-sm font-semibold">{t("draft.comments", { n: draft.comments.length })}</h3>
          <ul className="mt-1 space-y-2">
            {draft.comments.map((c, i) => (
              <li key={`${c.path}:${c.line}:${i}`} className="rounded-md border border-border p-2.5 text-sm">
                <button type="button" className="font-mono text-xs text-primary hover:underline k-anywhere" onClick={() => onLocate?.(c.path, c.line)}>
                  {t("format.pathLine", { path: c.path, line: c.line })}
                </button>
                <Markdown source={c.body_md} className="mt-1 text-sm" />
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <Dialog open={gh !== null} onOpenChange={(o) => !o && setGh(null)} title={t("draft.ghTitle")} description={t("draft.ghBody")}
        footer={
          <>
            <Button onClick={() => gh && downloadText(gh.filename, gh.content, "application/json")} icon={Download}>
              {t("common.download")}
            </Button>
            <Button variant="primary" onClick={() => setGh(null)}>
              {t("common.close")}
            </Button>
          </>
        }
      >
        {gh?.gh_command ? (
          <>
            <p className="mb-1 text-sm font-medium">{t("draft.ghCommand")}</p>
            <CodeBlock code={gh.gh_command} lang="sh" />
            <p className="text-xs text-muted">{t("draft.ghNoToken")}</p>
          </>
        ) : null}
      </Dialog>
    </section>
  );
}
