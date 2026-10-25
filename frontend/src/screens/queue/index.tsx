import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { ArrowRight, MessageSquare, RefreshCw, Search } from "lucide-react";
import { startRefresh, useQueue, useQueueDigest, usePrefetchPull, type QueueSort } from "@/api/hooks/queue";
import { useAnalysis } from "@/api/hooks/pull";
import { useProject, useProjectId, useStatus } from "@/api/hooks/system";
import { useConfirmableAction } from "@/api/hooks/confirm";
import { useJob } from "@/api/hooks/jobs";
import type { QueueRow as Row } from "@/api/types";
import { AnswerHeader } from "@/components/keeper/AnswerHeader";
import { BudgetBar } from "@/components/keeper/BudgetBar";
import { LaneBadge } from "@/components/keeper/Lane";
import { LaneFilter } from "@/components/keeper/LaneFilter";
import { ProvenanceBadge } from "@/components/keeper/Provenance";
import { QueueRow } from "@/components/keeper/QueueRow";
import { EmptyState, InlineError, KeyRequired } from "@/components/keeper/States";
import { JobProgress } from "@/components/keeper/JobProgress";
import { Button, buttonClass } from "@/components/ui/Button";
import { Disclosure } from "@/components/ui/Disclosure";
import { SelectField } from "@/components/ui/Field";
import { Markdown } from "@/components/ui/Markdown";
import { Delayed, Skeleton } from "@/components/ui/Skeleton";
import { Tooltip } from "@/components/ui/Tooltip";
import { t } from "@/copy/t";
import { cx } from "@/lib/cx";
import { formatMoney } from "@/lib/format";
import { FINDING_LANES, QUEUE_LANES, laneKey, laneLabel, laneMeaning } from "@/lib/lanes";
import { obj, num } from "@/lib/unknown";
import { remToPx, useContainerWidth } from "@/lib/useContainerWidth";
import { writeSession } from "@/lib/storage";
import { ask } from "@/state/ask";
import { useGate } from "@/screens/shared/permissions";
import { maintainerName } from "@/screens/shared/lens";
import { useKeyEnvVar } from "@/shell/AppShell";

export const QUEUE_RETURN_KEY = "keeper.queue.return";

function QueueSkeleton() {
  return (
    <Delayed>
      <div className="space-y-4">
        <Skeleton shape="block" className="h-16" />
        <Skeleton lines={2} />
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} shape="row" />
        ))}
      </div>
    </Delayed>
  );
}

function PreviewPane({ pid, row, maintainer }: { pid: string; row: Row; maintainer: string }) {
  const analysis = useAnalysis(pid, row.number);
  const findings = analysis.data?.findings ?? [];
  return (
    <aside aria-label={t("queue.preview.label")} className="k-card sticky top-[calc(var(--topbar-height)+1rem)] space-y-3 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <LaneBadge lane={row.analysis_id ? row.lane : "unsorted"} maintainer={maintainer} />
        <ProvenanceBadge provenance={row.provenance} compact />
      </div>
      <h2 className="text-lg font-semibold k-anywhere">
        <span className="mr-1.5 text-muted tabular">{t("format.prNumber", { n: row.number })}</span>
        {row.title}
      </h2>
      {analysis.isLoading ? (
        <Skeleton lines={3} />
      ) : analysis.data?.summary_md ? (
        <Markdown source={analysis.data.summary_md} className="text-sm" />
      ) : row.summary ? (
        <p className="text-sm">{row.summary}</p>
      ) : null}
      {FINDING_LANES.map((lane) => {
        const items = findings.filter((f) => f.lane === lane);
        if (!items.length) return null;
        return (
          <div key={lane}>
            <p className="text-sm font-medium">{t("queue.preview.laneCount", { lane: laneLabel(lane), n: items.length })}</p>
            <ul className="mt-0.5 list-disc pl-5 text-sm text-muted">
              {items.slice(0, 5).map((f) => (
                <li key={f.id} className="k-anywhere">
                  {f.title}
                </li>
              ))}
            </ul>
          </div>
        );
      })}
      <Link to={`/pr/${row.number}`} className={buttonClass("primary")}>
        {t("queue.preview.open")}
        <ArrowRight className="size-4" aria-hidden />
      </Link>
    </aside>
  );
}

export default function QueueScreen() {
  const pid = useProjectId();
  const status = useStatus();
  const project = useProject(pid);
  const navigate = useNavigate();
  const envVar = useKeyEnvVar();
  const [params, setParams] = useSearchParams();
  const lane = params.get("lane") ?? "";
  const q = params.get("q") ?? "";
  const sort = (params.get("sort") as QueueSort | null) ?? "attention";
  const queue = useQueue(pid, sort);
  const digest = useQueueDigest(pid);
  const prefetch = usePrefetchPull(pid);
  const [selected, setSelected] = useState<number | null>(null);
  const [flash, setFlash] = useState<Set<number>>(new Set());
  const [ref, width] = useContainerWidth<HTMLDivElement>();
  const listRef = useRef<HTMLDivElement>(null);
  const wide = width >= remToPx(76);
  const maintainer = maintainerName(queue.data?.maintainer ?? project.data?.primary_maintainer, t("people.unknown"));

  const refreshGate = useGate({ live: true, maintainer: true });
  const refresh = useConfirmableAction<void>((_v, token) => startRefresh(pid!, token), () => ({ title: t("queue.refresh.confirmTitle"), description: t("queue.refresh.confirmBody", { n: queue.data?.summary.total ?? 0 }) }));
  const refreshJob = useJob(refresh.jobId);

  // Rows update as analysis.updated events arrive (a subtle flash).
  const lastSeen = useRef(0);
  useEffect(() => {
    if (!refreshJob) return;
    const fresh = refreshJob.events.slice(lastSeen.current).filter((e) => e.type === "analysis.updated");
    lastSeen.current = refreshJob.events.length;
    if (fresh.length) {
      setFlash(new Set(fresh.map((e) => num(obj(e.data).pr_number)).filter((n): n is number => n !== undefined)));
      void queue.refetch();
    }
  }, [refreshJob, queue]);

  useEffect(() => {
    writeSession(QUEUE_RETURN_KEY, params.toString());
  }, [params]);

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  const rows = useMemo(() => {
    const items = queue.data?.items ?? [];
    const needle = q.trim().toLowerCase();
    return items.filter((r) => {
      if (lane && laneKey(r.lane) !== lane) return false;
      if (!needle) return true;
      const hay = [r.title, r.author.login, r.author.display_name ?? "", ...(r.files ?? []), ...(r.areas ?? []), String(r.number)].join(" ").toLowerCase();
      return hay.includes(needle);
    });
  }, [queue.data, lane, q]);

  useEffect(() => {
    if (wide && selected === null && rows[0]) setSelected(rows[0].number);
  }, [wide, rows, selected]);

  if (!pid || queue.isLoading) return <div className="k-page" ref={ref}><QueueSkeleton /></div>;
  if (queue.error && !queue.data)
    return (
      <div className="k-page" ref={ref}>
        <h1 tabIndex={-1} data-page-title className="mb-4 text-2xl font-semibold">
          {t("queue.title")}
        </h1>
        <InlineError error={queue.error} onRetry={() => void queue.refetch()} />
      </div>
    );

  const data = queue.data!;
  const sum = data.summary;
  const anySorted = data.items.some((r) => r.analysis_id);
  const repo = project.data ? t("shell.project", { owner: project.data.owner, repo: project.data.repo }) : "";
  const estimatePerPr = status.data?.estimates?.analyze_pr;
  const refreshEstimate = estimatePerPr !== undefined ? estimatePerPr * sum.total : undefined;
  const title = sum.total === 0 ? t("queue.answer.empty", { repo }) : sum.need_count === 0 ? t("queue.answer.none", { n: sum.total }) : t("queue.answer.some", { need: sum.need_count, total: sum.total, minutes: sum.attention_minutes_total, budget: sum.budget_minutes });
  const subtitle = sum.total > 0 ? t("queue.answer.sub", { shared: sum.by_lane.shared ?? 0, unknown: sum.by_lane.unknown ?? 0 }) : undefined;
  const refreshProgress = refreshJob?.progress;
  const refreshing = refreshJob && !["completed", "failed", "cancelled"].includes(refreshJob.phase);

  const onListKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const idx = rows.findIndex((r) => r.number === selected);
    const next = rows[Math.max(0, Math.min(rows.length - 1, idx + (e.key === "ArrowDown" ? 1 : -1)))];
    if (!next) return;
    setSelected(next.number);
    listRef.current?.querySelector<HTMLElement>(`[data-row-link="${next.number}"]`)?.focus();
  };

  const groups = sort === "attention" ? QUEUE_LANES.map((l) => ({ lane: l, rows: rows.filter((r) => laneKey(r.lane) === l && r.analysis_id) })).concat([{ lane: "unsorted" as never, rows: rows.filter((r) => !r.analysis_id) }]) : [{ lane: null, rows }];
  const selectedRow = rows.find((r) => r.number === selected);

  return (
    <div ref={ref} className="k-page mx-auto w-full max-w-[110rem] space-y-5">
      <AnswerHeader
        title={title}
        subtitle={subtitle}
        eyebrow={<ProvenanceBadge provenance={data.provenance} />}
        actions={
          <Tooltip content={refreshGate}>
            <span>
              <Button
                icon={RefreshCw}
                loading={refresh.pending || Boolean(refreshing)}
                disabled={Boolean(refreshGate)}
                onClick={() => void refresh.run()}
              >
                {refreshing && refreshProgress && refreshProgress.total
                  ? t("queue.refresh.running", { done: refreshProgress.done, total: refreshProgress.total })
                  : refreshEstimate !== undefined
                    ? t("queue.refresh.withCost", { amount: formatMoney(refreshEstimate) })
                    : t("queue.refresh.label")}
              </Button>
            </span>
          </Tooltip>
        }
      />
      {refresh.keyRequired ? <KeyRequired what={t("queue.refresh.needsKey")} provider={status.data?.provider ?? ""} envVar={envVar} /> : null}
      {refresh.error ? <InlineError error={refresh.error} onRetry={() => void refresh.run()} /> : null}
      {refresh.jobId && refreshing ? <JobProgress jobId={refresh.jobId} compact /> : null}

      {!anySorted && data.items.length > 0 ? (
        <div className="rounded-md border border-border bg-surface-2 p-4 text-sm">
          <p className="font-medium">{t("lane.unsorted.meaning", { maintainer })}</p>
          <Link to="/lens" className={cx(buttonClass("secondary", "sm"), "mt-2")}>
            {t("queue.buildLens")}
          </Link>
        </div>
      ) : null}

      {sum.total > 0 ? (
        <section aria-label={t("queue.summary.label")} className="space-y-3" data-tour="lane_summary">
          <LaneFilter counts={sum.by_lane} total={sum.total} value={lane} onChange={(v) => setParam("lane", v)} />
          <BudgetBar byLane={sum.attention_by_lane} total={sum.attention_minutes_total} budget={sum.budget_minutes} overBudget={sum.over_budget} handoffSuggestion={sum.handoff_suggestion} />
        </section>
      ) : null}

      {sum.total > 0 ? (
        <div className="flex flex-wrap items-end gap-3">
          <div className="relative min-w-0 flex-[1_1_18rem]">
            <label htmlFor="queue-search" className="sr-only">
              {t("queue.search.label")}
            </label>
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
            <input
              id="queue-search"
              data-shortcut="search"
              type="search"
              value={q}
              onChange={(e) => setParam("q", e.target.value)}
              placeholder={t("queue.search.placeholder")}
              className="w-full rounded-md border border-border-strong bg-surface py-1.5 pl-8 pr-3 text-sm placeholder:text-muted"
            />
          </div>
          <SelectField
            label={t("queue.sort.label")}
            className="w-auto"
            value={sort}
            onChange={(e) => setParam("sort", e.target.value === "attention" ? "" : e.target.value)}
            options={[
              { value: "attention", label: t("queue.sort.attention") },
              { value: "updated", label: t("queue.sort.updated") },
              { value: "number", label: t("queue.sort.number") },
            ]}
          />
        </div>
      ) : null}

      {sum.total === 0 ? (
        <EmptyState
          title={t("queue.empty.title", { repo })}
          action={
            <Link to="/settings?tab=projects" className={buttonClass("primary")}>
              {t("queue.empty.import")}
            </Link>
          }
        />
      ) : rows.length === 0 ? (
        <EmptyState
          compact
          title={lane ? t("queue.empty.lane") : t("queue.empty.search")}
          action={
            <Button
              variant="primary"
              onClick={() => {
                const next = new URLSearchParams(params);
                next.delete("lane");
                next.delete("q");
                setParams(next, { replace: true });
              }}
            >
              {t("common.showAll")}
            </Button>
          }
        />
      ) : (
        <div className={cx("grid gap-5", wide && "grid-cols-[minmax(0,1fr)_minmax(22rem,34rem)]")}>
          <div className="k-card overflow-hidden" ref={listRef} onKeyDown={onListKey}>
            {groups.map((g) =>
              g.rows.length ? (
                <section key={g.lane ?? "all"} aria-label={g.lane ? laneLabel(g.lane) : t("queue.title")}>
                  {g.lane ? (
                    <h2 className="sticky top-(--topbar-height) z-[5] flex flex-wrap items-baseline gap-x-2 border-b border-border bg-surface-2 px-3 py-1.5 text-sm">
                      <span className="font-semibold">{t("queue.group", { lane: laneLabel(g.lane), n: g.rows.length })}</span>
                      <span className="text-xs text-muted">{laneMeaning(g.lane, { maintainer })}</span>
                    </h2>
                  ) : null}
                  <ul role="list">
                    {g.rows.map((r) => (
                      <QueueRow
                        key={r.number}
                        row={r}
                        href={`/pr/${r.number}`}
                        selected={wide && selected === r.number}
                        onSelect={wide ? setSelected : undefined}
                        onPrefetch={prefetch}
                        maintainer={maintainer}
                        flash={flash.has(r.number)}
                        onHandoff={(row) => navigate(`/pr/${row.number}#handoff`)}
                      />
                    ))}
                  </ul>
                </section>
              ) : null,
            )}
          </div>
          {wide && selectedRow && pid ? <PreviewPane pid={pid} row={selectedRow} maintainer={maintainer} /> : null}
        </div>
      )}

      {digest.data?.markdown ? (
        <section className="k-card p-4">
          <Disclosure summary={<span className="text-base font-semibold">{t("queue.digest.title")}</span>}>
            <Markdown source={digest.data.markdown} className="text-sm" />
            <Button className="mt-3" size="sm" icon={MessageSquare} onClick={() => ask.open({ screen: "queue" })}>
              {t("queue.digest.ask")}
            </Button>
          </Disclosure>
        </section>
      ) : null}
    </div>
  );
}
