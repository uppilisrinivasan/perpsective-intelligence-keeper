import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, LoaderCircle, Plus } from "lucide-react";
import { api, call } from "@/api/client";
import { keys } from "@/api/keys";
import type { AnalysisResponse, DiffFile, HandoffOut, RoutedFinding } from "@/api/types";
import type { JobState } from "@/api/jobs";
import { FindingCard } from "@/components/keeper/FindingCard";
import type { FeedbackPayload } from "@/components/keeper/FeedbackActions";
import { HandoffCard } from "@/components/keeper/HandoffCard";
import { LaneIcon } from "@/components/keeper/Lane";
import { InlineError } from "@/components/keeper/States";
import { Button } from "@/components/ui/Button";
import { Disclosure } from "@/components/ui/Disclosure";
import { SelectField, TextArea, TextField } from "@/components/ui/Field";
import { t, tDynamic } from "@/copy/t";
import { laneLabel, laneMeaning } from "@/lib/lanes";
import { obj, str } from "@/lib/unknown";
import { toast } from "@/state/toasts";

const STAGES = ["context", "baseline", "lens_recall", "lens_review", "match", "route", "triage", "draft"] as const;

/** While analysis runs: the stage list from analysis.step events. */
export function AnalysisStages({ job }: { job: JobState }) {
  const seen = job.events.filter((e) => e.type === "analysis.step").map((e) => str(obj(e.data).stage));
  const current = seen[seen.length - 1];
  return (
    <ol className="space-y-1.5" aria-live="polite">
      {STAGES.map((s) => {
        const reached = seen.includes(s);
        const active = s === current && job.phase === "running";
        return (
          <li key={s} className="flex items-center gap-2 text-sm">
            {active ? <LoaderCircle className="size-4 animate-spin text-muted motion-reduce:animate-none" aria-hidden /> : reached ? <CheckCircle2 className="size-4 text-success" aria-hidden /> : <span className="size-4 rounded-full border border-border" aria-hidden />}
            <span className={reached ? "" : "text-muted"}>{tDynamic(`analysis.stage.${s}`)}</span>
          </li>
        );
      })}
    </ol>
  );
}

function AddMissed({ pid, n, files, categories, disabledReason }: { pid: string; n: number; files: DiffFile[]; categories: Array<{ value: string; label: string }>; disabledReason?: string }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [path, setPath] = useState("");
  const [line, setLine] = useState("");
  const [text, setText] = useState("");
  const [category, setCategory] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  if (!open)
    return (
      <Button variant="ghost" icon={Plus} onClick={() => setOpen(true)} disabled={Boolean(disabledReason)} title={disabledReason}>
        {t("pr.missed.button")}
      </Button>
    );
  return (
    <form
      className="k-card space-y-2.5 p-3"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!text.trim()) return;
        setBusy(true);
        setError(null);
        try {
          await call(
            api.POST("/api/v1/projects/{pid}/pulls/{n}/notes", {
              params: { path: { pid, n } },
              body: { path: path || null, line: line ? Number(line) : null, text, category: category || null },
            }),
          );
          void qc.invalidateQueries({ queryKey: keys.pullPart(pid, n, "analysis") });
          toast({ tone: "success", title: t("pr.missed.saved") });
          setOpen(false);
          setText("");
          setLine("");
        } catch (err) {
          setError(err);
        } finally {
          setBusy(false);
        }
      }}
    >
      <h3 className="text-sm font-semibold">{t("pr.missed.title")}</h3>
      <div className="grid gap-2 [grid-template-columns:repeat(auto-fit,minmax(min(100%,12rem),1fr))]">
        <SelectField label={t("pr.missed.file")} value={path} onChange={(e) => setPath(e.target.value)} options={[{ value: "", label: t("pr.missed.wholePr") }, ...files.map((f) => ({ value: f.filename, label: f.filename }))]} />
        <TextField label={t("pr.missed.line")} type="number" min={1} inputMode="numeric" value={line} onChange={(e) => setLine(e.target.value)} disabled={!path} />
        <SelectField label={t("pr.missed.category")} value={category} onChange={(e) => setCategory(e.target.value)} options={[{ value: "", label: t("common.optional") }, ...categories]} />
      </div>
      <TextArea label={t("pr.missed.text")} value={text} onChange={(e) => setText(e.target.value)} required rows={3} />
      {error ? <InlineError error={error} /> : null}
      <div className="flex gap-2">
        <Button type="submit" variant="primary" size="sm" loading={busy}>
          {t("common.save")}
        </Button>
        <Button size="sm" onClick={() => setOpen(false)}>
          {t("common.cancel")}
        </Button>
      </div>
    </form>
  );
}

export interface FindingsPaneProps {
  pid: string;
  n: number;
  analysis: AnalysisResponse;
  handoff?: HandoffOut | null;
  handoffSlot?: React.ReactNode;
  files: DiffFile[];
  maintainer: string;
  showBaselineOnly: boolean;
  onFeedback: (f: RoutedFinding, p: FeedbackPayload) => void;
  onFix: (f: RoutedFinding) => void;
  onAsk: (f: RoutedFinding) => void;
  onLocate: (path: string, line: number | null) => void;
  feedbackGate?: string;
  fixGate?: string;
  highlighted?: string | null;
  fixPrimaryId?: string;
}

/** Findings grouped by lane: edge, blind spot, (hand-off for unknown PRs), shared (collapsed), other model notes (collapsed). */
export function FindingsPane(props: FindingsPaneProps) {
  const { analysis, maintainer } = props;
  const by = (lane: string) => analysis.findings.filter((f) => f.lane === lane);
  const card = (f: RoutedFinding) => (
    <li key={f.id}>
      <FindingCard
        finding={f}
        maintainer={maintainer}
        onFeedback={(p) => props.onFeedback(f, p)}
        onFix={() => props.onFix(f)}
        onAsk={() => props.onAsk(f)}
        onLocate={props.onLocate}
        canFix
        disabledReason={props.feedbackGate}
        fixDisabledReason={props.fixGate}
        fixPrimary={props.fixPrimaryId === f.id}
        highlighted={props.highlighted === f.id}
      />
    </li>
  );
  const categories = [...new Map(analysis.findings.map((f) => [f.category, f.category_label || f.category])).entries()].map(([value, label]) => ({ value, label }));
  const group = (lane: string, collapsed: boolean) => {
    const items = by(lane);
    if (!items.length) return null;
    const header = (
      <span className="inline-flex items-center gap-1.5">
        <LaneIcon lane={lane} />
        {t("pr.findings.group", { lane: laneLabel(lane), n: items.length })}
      </span>
    );
    return (
      <section key={lane} aria-label={laneLabel(lane)}>
        {collapsed ? (
          <Disclosure summary={header} headerClassName="text-base font-semibold py-1">
            <p className="mb-2 text-xs text-muted">{laneMeaning(lane, { maintainer })}</p>
            <ul className="space-y-2.5">{items.map(card)}</ul>
          </Disclosure>
        ) : (
          <>
            <h2 className="py-1 text-base font-semibold">{header}</h2>
            <p className="mb-2 text-xs text-muted">{laneMeaning(lane, { maintainer })}</p>
            <ul className="space-y-2.5">{items.map(card)}</ul>
          </>
        )}
      </section>
    );
  };
  const nothing = analysis.findings.length === 0;
  return (
    <div className="space-y-5">
      {analysis.lane === "unknown" ? <div id="handoff">{props.handoffSlot}</div> : null}
      {analysis.lens_paused ? <p className="rounded-md bg-warning-bg p-2.5 text-sm text-warning-fg">{t("pr.lensPaused")}</p> : null}
      {analysis.baseline_unavailable ? <p className="rounded-md bg-warning-bg p-2.5 text-sm text-warning-fg">{t("pr.baselineUnavailable")}</p> : null}
      {group("edge", false)}
      {group("blind_spot", false)}
      {group("shared", true)}
      {group("baseline_only", !props.showBaselineOnly)}
      {nothing ? <p className="text-sm text-muted">{t("pr.findings.none")}</p> : null}
      <AddMissed pid={props.pid} n={props.n} files={props.files} categories={categories} disabledReason={props.feedbackGate} />
      {props.handoff && analysis.lane !== "unknown" ? <HandoffCard handoff={props.handoff} primary={false} /> : null}
    </div>
  );
}
