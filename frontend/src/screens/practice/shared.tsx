import { Link } from "react-router";
import { CheckCircle2, CircleX, Dot, MessageSquare, Star } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Markdown } from "@/components/ui/Markdown";
import { LensItemChip } from "@/components/keeper/LensItem";
import { t, tDynamic } from "@/copy/t";
import { formatPercent, formatPoints } from "@/lib/format";
import { num, obj, objs, str, strs, type Obj } from "@/lib/unknown";
import { ask } from "@/state/ask";

export function kindLabel(kind: string): string {
  return tDynamic(`practice.kind.${kind}`) || kind;
}

/** Notes kept locally until submit, so a refresh doesn't lose them. */
export interface LocalNotes {
  lines: Record<string, string>;
  general: string;
}
export const notesKey = (sid: string, n: number) => `keeper.practice.${sid}.${n}`;

function findingTitle(f: unknown): string {
  const o = obj(f);
  return str(o.title) ?? str(o.statement) ?? "";
}

/** The reveal: what the learner caught and missed, own-eye catches (never counted against them), and non-issues. */
export function Reveal({ reveal, maintainer, noteText, simulated }: { reveal: Obj; maintainer: string; noteText: (noteId: unknown) => string | undefined; simulated?: boolean }) {
  const caught = objs(reveal.caught);
  const missed = objs(reveal.missed);
  const own = objs(reveal.own_eye);
  const notIssue = objs(reveal.not_an_issue);
  const total = caught.length + missed.length;
  return (
    <section aria-labelledby="reveal-h" className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="reveal-h" className="text-lg font-semibold">
          {t("practice.reveal.summary", { k: caught.length, n: total, name: maintainer })}
        </h2>
        {simulated ? <Badge tone="warning">{t("practice.scoredSimulated")}</Badge> : null}
      </div>
      <ul className="space-y-2.5">
        {caught.map((c, i) => {
          const f = obj(c.finding);
          return (
            <li key={`c${i}`} className="flex gap-2">
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
              <div className="min-w-0 text-sm">
                <span className="sr-only">{t("practice.reveal.caughtSr")}</span>
                <p className="font-medium">{findingTitle(f)}</p>
                {noteText(c.note_id) ? <p className="text-muted">{t("practice.reveal.yourNote", { note: noteText(c.note_id) ?? "" })}</p> : null}
                <Attribution f={f} maintainer={maintainer} />
              </div>
            </li>
          );
        })}
        {missed.map((m, i) => {
          const f = obj(m.finding);
          const item = obj(m.lens_item);
          return (
            <li key={`m${i}`} className="flex gap-2">
              <CircleX className="mt-0.5 size-4 shrink-0 text-danger" aria-hidden />
              <div className="min-w-0 space-y-1 text-sm">
                <span className="sr-only">{t("practice.reveal.missedSr")}</span>
                <p className="font-medium">{findingTitle(f)}</p>
                {str(m.why_it_matters_md) ? <Markdown source={t("practice.reveal.why", { why: str(m.why_it_matters_md) ?? "" })} className="text-sm text-muted" /> : null}
                {str(item.id) ? <LensItemChip item={{ id: str(item.id)!, title: str(item.title) ?? "", support: num(item.support) }} /> : null}
                <Attribution f={f} maintainer={maintainer} />
              </div>
            </li>
          );
        })}
        {own.map((o, i) => (
          <li key={`o${i}`} className="flex gap-2">
            <Star className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
            <div className="text-sm">
              <p>{t("practice.reveal.ownEye", { note: noteText(o.note_id) ?? "", name: maintainer })}</p>
              {str(o.why) ? <p className="text-muted">{str(o.why)}</p> : null}
            </div>
          </li>
        ))}
        {notIssue.map((o, i) => (
          <li key={`n${i}`} className="flex gap-2 text-muted">
            <Dot className="size-4 shrink-0" aria-hidden />
            <p className="text-sm">{t("practice.reveal.notIssue", { note: noteText(o.note_id) ?? "" })}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Attribution({ f, maintainer }: { f: Obj; maintainer: string }) {
  const url = str(f.html_url);
  const by = str(f.person) ?? maintainer;
  const statement = str(f.statement);
  return (
    <p className="text-xs text-muted">
      {statement ? <q className="mr-1">{statement}</q> : null}
      {t("practice.reveal.by", { name: by })}
      {url ? (
        <a href={url} target="_blank" rel="noopener noreferrer" className="ml-1 text-primary hover:underline">
          {t("practice.reveal.link")}
        </a>
      ) : null}
    </p>
  );
}

export function Hints({ hints }: { hints: Obj[] }) {
  return (
    <section aria-labelledby="hints-h" className="space-y-2 rounded-md border border-info/40 bg-info-bg p-3 text-info-fg">
      <h2 id="hints-h" className="font-semibold">
        {t("practice.hints.title", { n: hints.length })}
      </h2>
      <ul className="list-disc space-y-1 pl-5 text-sm">
        {hints.map((h, i) => (
          <li key={i}>
            {str(h.text)}
            {str(h.path) ? <span className="ml-1 font-mono text-xs">{str(h.path)}</span> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Session and growth results, in plain words; the 5-PR caveat; the learner lens diff; "Keep your own eye too". */
export function SessionResult({ result, maintainer, kind }: { result: Obj; maintainer: string; kind: string }) {
  const growth = result.growth ? obj(result.growth) : null;
  const diff = result.learner_lens_diff ? obj(result.learner_lens_diff) : null;
  const ownFell = growth && (num(growth.own_eye) ?? 0) < 0 && (num(growth.recall) ?? 0) > 0;
  return (
    <section aria-labelledby="result-h" className="k-card space-y-3 p-4">
      <h2 id="result-h" className="text-lg font-semibold">
        {t("practice.result.title", { kind: kindLabel(kind) })}
      </h2>
      <dl className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(min(100%,10rem),1fr))]">
        <div>
          <dt className="text-xs text-muted">{t("practice.result.recall", { name: maintainer })}</dt>
          <dd className="text-xl font-semibold tabular">{formatPercent(num(result.recall))}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">{t("practice.result.costlyMisses")}</dt>
          <dd className="text-xl font-semibold tabular">{num(result.costly_misses) ?? t("format.none")}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">{t("practice.result.ownEye")}</dt>
          <dd className="text-xl font-semibold tabular">{num(result.own_eye) ?? t("format.none")}</dd>
        </div>
      </dl>
      {growth ? (
        <div className="space-y-1 border-t border-border pt-3">
          <p className="font-medium">{t("practice.result.growth")}</p>
          <p className="text-sm">{t("practice.result.growthLine", { recall: formatPoints(num(growth.recall)), misses: num(growth.costly_misses) ?? 0 })}</p>
          <p className="text-xs text-muted">{t("practice.result.caveat")}</p>
        </div>
      ) : null}
      {diff ? (
        <div className="space-y-1 text-sm">
          {strs(diff.started_catching).length ? <p>{t("practice.result.started", { list: strs(diff.started_catching).join(", ") })}</p> : null}
          {strs(diff.still_missing).length ? <p className="text-muted">{t("practice.result.still", { list: strs(diff.still_missing).join(", ") })}</p> : null}
        </div>
      ) : null}
      {ownFell ? <p className="rounded-md bg-info-bg p-2.5 text-sm text-info-fg">{t("practice.result.keepOwnEye")}</p> : null}
      {str(result.interpretation_md) ? <Markdown source={str(result.interpretation_md)} className="text-sm" /> : null}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" icon={MessageSquare} onClick={() => ask.open({ screen: "practice" }, t("practice.result.askPrompt"))}>
          {t("practice.result.ask")}
        </Button>
        <Link to="/lens" className="inline-flex items-center rounded-md px-3 py-1 text-sm font-medium text-primary hover:underline">
          {t("practice.result.seeLens", { name: maintainer })}
        </Link>
      </div>
    </section>
  );
}
