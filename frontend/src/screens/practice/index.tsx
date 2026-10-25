import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { ArrowRight, CheckCircle2, Clock, GraduationCap } from "lucide-react";
import { api, call } from "@/api/client";
import { usePracticeOverview } from "@/api/hooks/practice";
import { usePeople, useProjectId, useStatus } from "@/api/hooks/system";
import type { PracticeStart } from "@/api/types";
import { AnswerHeader } from "@/components/keeper/AnswerHeader";
import { EmptyState, InlineError, PageError } from "@/components/keeper/States";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Delayed, Skeleton } from "@/components/ui/Skeleton";
import { t } from "@/copy/t";
import { formatDate, formatPercent, personName } from "@/lib/format";
import { useViewer } from "@/state/role";
import { kindLabel, SessionResult } from "./shared";
import { obj } from "@/lib/unknown";

const GROWTH_KINDS = ["before", "learn", "after"] as const;

/** The learner is the selected persona, or "me" (a guest key in a cookie) for "Me (judge)". */
export function useLearner(): string {
  const viewer = useViewer();
  const [params] = useSearchParams();
  return params.get("learner") ?? viewer.personId ?? "me";
}

export default function PracticeScreen() {
  const pid = useProjectId();
  const status = useStatus();
  const learner = useLearner();
  const people = usePeople(pid);
  const navigate = useNavigate();
  const overview = usePracticeOverview(pid, learner);
  const [starting, setStarting] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  if (!pid || overview.isLoading)
    return (
      <div className="k-page">
        <Delayed>
          <Skeleton shape="block" className="mb-4 h-16" />
          <Skeleton lines={6} />
        </Delayed>
      </div>
    );
  if (overview.error) return <PageError error={overview.error} onRetry={() => void overview.refetch()} />;
  const o = overview.data!;
  const target = o.target ? personName(o.target) : t("people.unknown");
  const learnerName = o.learner ? personName(o.learner) : learner === "me" ? t("people.judge") : personName(people.data?.items.find((p) => p.id === learner));

  const start = async (kind: PracticeStart["kind"]) => {
    setStarting(kind);
    setError(null);
    try {
      const s = await call(api.POST("/api/v1/projects/{pid}/practice/sessions", { params: { path: { pid } }, body: { kind, target_person_id: o.target?.id ?? null, learner } }));
      navigate(`/practice/${s.id}/${s.current_index ?? 0}`);
    } catch (e) {
      setError(e);
    } finally {
      setStarting(null);
    }
  };

  const byKind = (k: string) => o.sessions.filter((s) => s.kind === k).sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))[0];
  const inProgress = o.sessions.find((s) => s.status !== "completed" && s.kind !== "taste");
  const returning = o.sessions.length > 0;
  const nextKind = (o.next_kind ?? "before") as PracticeStart["kind"];
  const growth = o.growth ? obj(o.growth) : null;

  if (o.bank_size === 0)
    return (
      <div className="k-page">
        <AnswerHeader title={t("practice.title", { name: target })} />
        <EmptyState title={t("practice.noItems")} />
      </div>
    );

  return (
    <div className="k-page mx-auto w-full max-w-[90rem] space-y-6">
      <AnswerHeader title={t("practice.title", { name: target })} subtitle={t("practice.subtitle", { name: target })} />
      {!o.scoring_available || !status.data?.live ? <p className="rounded-md bg-surface-2 p-3 text-sm text-muted">{t("practice.noKey", { provider: status.data?.provider ?? "" })}</p> : null}
      {error ? <InlineError error={error} /> : null}
      <div className="grid gap-4 [grid-template-columns:repeat(auto-fit,minmax(min(100%,22rem),1fr))]">
        <section className="k-card flex flex-col gap-3 p-5" data-tour="practice_taste" aria-labelledby="taste-h">
          <h2 id="taste-h" className="flex items-center gap-2 text-lg font-semibold">
            <Clock className="size-5 text-muted" aria-hidden />
            {t("practice.taste.title")}
          </h2>
          <p className="text-sm text-muted">{t("practice.taste.body")}</p>
          <div className="mt-auto">
            <Button variant={returning ? "secondary" : "primary"} loading={starting === "taste"} onClick={() => void start("taste")}>
              {t("practice.taste.start")}
            </Button>
          </div>
        </section>
        <section className="k-card flex flex-col gap-3 p-5" aria-labelledby="growth-h">
          <h2 id="growth-h" className="flex items-center gap-2 text-lg font-semibold">
            <GraduationCap className="size-5 text-muted" aria-hidden />
            {t("practice.growth.title")}
          </h2>
          <ol className="space-y-1 text-sm">
            {GROWTH_KINDS.map((k, i) => {
              const s = byKind(k);
              return (
                <li key={k} className="flex items-center gap-2">
                  {s?.status === "completed" ? <CheckCircle2 className="size-4 text-success" aria-hidden /> : <span className="flex size-4 items-center justify-center rounded-full border border-border-strong text-[0.6rem]" aria-hidden>{i + 1}</span>}
                  <span>{t(`practice.growth.step.${k}` as "practice.growth.step.before", { name: target })}</span>
                </li>
              );
            })}
          </ol>
          <div className="mt-auto flex flex-wrap gap-2">
            {inProgress ? (
              <Button variant={returning ? "primary" : "secondary"} iconEnd={ArrowRight} onClick={() => navigate(`/practice/${inProgress.id}/0`)}>
                {t("practice.continue", { kind: kindLabel(inProgress.kind) })}
              </Button>
            ) : (
              <Button variant={returning ? "primary" : "secondary"} loading={starting === nextKind} onClick={() => void start(nextKind)}>
                {t("practice.startKind", { kind: kindLabel(nextKind) })}
              </Button>
            )}
          </div>
        </section>
      </div>

      <section aria-labelledby="progress-h" className="space-y-2">
        <div className="flex flex-wrap items-baseline gap-x-3">
          <h2 id="progress-h" className="text-lg font-semibold">
            {t("practice.progress.title")}
          </h2>
          <p className="text-sm text-muted">{t("practice.learner", { name: learnerName })}</p>
        </div>
        {o.sessions.length === 0 ? (
          <p className="text-sm text-muted">{t("practice.progress.none")}</p>
        ) : (
          <ul className="divide-y divide-border rounded-md border border-border">
            {o.sessions.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 text-sm">
                <span className="font-medium">{kindLabel(s.kind)}</span>
                <span className="text-muted">{formatDate(s.created_at)}</span>
                <span className="text-muted">{t("practice.progress.items", { n: s.items })}</span>
                {s.recall !== null && s.recall !== undefined ? <span className="tabular">{t("practice.progress.recall", { pct: formatPercent(s.recall) })}</span> : null}
                {s.origin === "snapshot" ? <Badge>{t("common.saved_run")}</Badge> : null}
                <Badge tone={s.status === "completed" ? "success" : "outline"}>{s.status === "completed" ? t("practice.progress.done") : t("practice.progress.open")}</Badge>
                <Link to={`/practice/${s.id}/0`} className="ml-auto text-primary hover:underline">
                  {s.status === "completed" ? t("practice.progress.view") : t("practice.progress.resume")}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
      {growth ? <SessionResult result={growth} maintainer={target} kind="after" /> : null}
    </div>
  );
}
