import { useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useVirtualizer } from "@tanstack/react-virtual";
import { AlertTriangle, CheckCircle2, MessageSquare, Play, Search } from "lucide-react";
import { api, call } from "@/api/client";
import { useConfirmableAction } from "@/api/hooks/confirm";
import { useFidelityCase, useFidelityCases, useFidelityRun, useFidelityRuns } from "@/api/hooks/proof";
import { useProjectId, useStatus } from "@/api/hooks/system";
import type { CaseRow, FidelityRun, Metric, SystemMetrics } from "@/api/types";
import { AnswerHeader } from "@/components/keeper/AnswerHeader";
import { CompareView } from "@/components/keeper/CompareView";
import { JobProgress } from "@/components/keeper/JobProgress";
import { CompareBars, CriteriaList, FalsifierList, MetricBar } from "@/components/keeper/Metrics";
import { ProvenanceBadge } from "@/components/keeper/Provenance";
import { EmptyState, InlineError, KeyRequired, PageError } from "@/components/keeper/States";
import { Button, buttonClass } from "@/components/ui/Button";
import { Checkbox, SelectField } from "@/components/ui/Field";
import { Disclosure } from "@/components/ui/Disclosure";
import { Segmented } from "@/components/ui/Segmented";
import { Delayed, Skeleton } from "@/components/ui/Skeleton";
import { SplitPane } from "@/components/ui/SplitPane";
import { Term } from "@/components/ui/Term";
import { t } from "@/copy/t";
import { cx } from "@/lib/cx";
import { formatDate, formatMoney, formatPercent, humanise, personName } from "@/lib/format";
import { MQ, useMediaQuery } from "@/lib/useMedia";
import { num, obj } from "@/lib/unknown";
import { ask } from "@/state/ask";
import { useGate } from "@/screens/shared/permissions";
import { useKeyEnvVar } from "@/shell/AppShell";

/** Looks up a system's metrics; the run's `metrics` is keyed by system name. */
export function systemMetrics(run: FidelityRun, system: "keeper" | "lens" | "baseline"): SystemMetrics | undefined {
  const alias: Record<string, string[]> = { keeper: ["keeper", "combined", "routed"], lens: ["lens", "lens_only"], baseline: ["baseline", "generic", "c"] };
  for (const k of alias[system]!) if (run.metrics[k]) return run.metrics[k];
  return undefined;
}

function Dots({ matched, total, label }: { matched: number; total: number; label: string }) {
  const n = Math.min(total, 6);
  const filled = Math.round(Math.min(matched, total) * (n / Math.max(total, 1)));
  return (
    <span className="inline-flex items-center gap-0.5" role="img" aria-label={t("proof.cases.dotsAria", { label, matched: Math.round(matched * 10) / 10, total })}>
      {Array.from({ length: n }, (_, i) => (
        <span key={i} className={cx("size-2 rounded-full border", i < filled ? "border-text bg-text" : "border-border-strong")} aria-hidden />
      ))}
    </span>
  );
}

function CaseList({ fid, selected, onSelect, maintainer }: { fid: string; selected?: number; onSelect: (n: number) => void; maintainer: string }) {
  const [q, setQ] = useState("");
  const [outcome, setOutcome] = useState("");
  const cases = useFidelityCases(fid, q, outcome);
  const items = cases.data?.items ?? [];
  const parentRef = useRef<HTMLDivElement>(null);
  const v = useVirtualizer({ count: items.length, getScrollElement: () => parentRef.current, estimateSize: () => 64, overscan: 8 });
  const row = (c: CaseRow) => (
    <button
      type="button"
      onClick={() => onSelect(c.pr_number)}
      aria-current={selected === c.pr_number || undefined}
      className={cx("w-full border-b border-border px-3 py-2 text-left text-sm hover:bg-surface-2", selected === c.pr_number && "bg-surface-2")}
    >
      <p className="font-medium k-anywhere">
        <span className="mr-1.5 text-muted tabular">{t("format.prNumber", { n: c.pr_number })}</span>
        {c.title}
      </p>
      <p className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-muted">
        <span>{t("proof.cases.raised", { name: maintainer, n: c.maintainer_findings })}</span>
        <span className="inline-flex items-center gap-1">
          {t("proof.sys.keeperShort")} <Dots matched={c.keeper_matched} total={c.maintainer_findings} label={t("proof.sys.keeperShort")} />
        </span>
        <span className="inline-flex items-center gap-1">
          {t("proof.sys.baselineShort")} <Dots matched={c.baseline_matched} total={c.maintainer_findings} label={t("proof.sys.baselineShort")} />
        </span>
        {c.lens_extra ? <span>{t("proof.cases.extra", { n: c.lens_extra })}</span> : null}
      </p>
    </button>
  );
  return (
    <section aria-labelledby="cases-h" className="flex h-full min-h-0 flex-col gap-2">
      <h2 id="cases-h" className="text-lg font-semibold">
        {t("proof.cases.title", { n: items.length })}
      </h2>
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-0 flex-[1_1_12rem]">
          <label htmlFor="case-search" className="sr-only">
            {t("proof.cases.search")}
          </label>
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
          <input id="case-search" data-shortcut="search" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("proof.cases.search")} className="w-full rounded-md border border-border-strong bg-surface py-1.5 pl-8 pr-3 text-sm placeholder:text-muted" />
        </div>
        <Segmented
          size="sm"
          label={t("proof.cases.filter")}
          value={outcome || "all"}
          onChange={(x) => setOutcome(x === "all" ? "" : x)}
          options={[
            { value: "all", label: t("common.showAll") },
            { value: "caught", label: t("proof.cases.caught") },
            { value: "missed", label: t("proof.cases.missed") },
            { value: "extra", label: t("proof.cases.extraFilter") },
          ]}
        />
      </div>
      {cases.isLoading ? <Skeleton lines={6} /> : null}
      {cases.error ? <InlineError error={cases.error} onRetry={() => void cases.refetch()} /> : null}
      {cases.data && items.length === 0 ? <p className="text-sm text-muted">{t("proof.cases.none")}</p> : null}
      <div ref={parentRef} className="min-h-[16rem] flex-1 overflow-y-auto rounded-md border border-border">
        <ul style={{ height: `${v.getTotalSize()}px`, position: "relative" }}>
          {v.getVirtualItems().map((it) => (
            <li key={items[it.index]!.pr_number} data-index={it.index} ref={v.measureElement} className="absolute left-0 w-full" style={{ transform: `translateY(${it.start}px)` }}>
              {row(items[it.index]!)}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function CaseDetailPane({ fid, n, maintainer }: { fid: string; n: number; maintainer: string }) {
  const c = useFidelityCase(fid, n);
  if (c.isLoading) return <Skeleton lines={8} />;
  if (c.error) return <InlineError error={c.error} onRetry={() => void c.refetch()} />;
  const d = c.data!;
  return (
    <section aria-labelledby="case-h" className="space-y-3">
      <h2 id="case-h" className="text-lg font-semibold k-anywhere">
        <Link to={`/pr/${d.pr_number}?view=compare`} className="hover:underline">
          <span className="mr-1.5 text-muted tabular">{t("format.prNumber", { n: d.pr_number })}</span>
          {d.title}
        </Link>
      </h2>
      <CompareView baseline={d.baseline} lens={d.lens} pairs={d.lens_baseline_pairs ?? []} human={d.human} humanPairs={d.matches} maintainer={maintainer} />
    </section>
  );
}

function HowThisWorks({ maintainer }: { maintainer: string }) {
  const steps = [t("proof.how.1"), t("proof.how.2"), t("proof.how.3", { name: maintainer }), t("proof.how.4")];
  return (
    <Disclosure summary={<span className="text-base font-semibold">{t("common.learnMore")}</span>} className="k-card p-4">
      <ol className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(min(100%,12rem),1fr))]">
        {steps.map((s, i) => (
          <li key={i} className="relative rounded-md bg-surface-2 p-3 text-sm">
            <span className="mb-1 flex size-6 items-center justify-center rounded-full bg-primary text-xs font-semibold text-on-primary">{i + 1}</span>
            {s}
          </li>
        ))}
      </ol>
      <Button className="mt-3" size="sm" icon={MessageSquare} onClick={() => ask.open({ screen: "proof" }, t("proof.how.askPrompt"))}>
        {t("proof.how.ask")}
      </Button>
    </Disclosure>
  );
}

function sensitivityRows(s: Record<string, unknown>): Array<[string, string]> {
  return Object.entries(s).map(([k, v]) => {
    const m = obj(v);
    const val = num(m.value) ?? num(v);
    return [humanise(k), val !== undefined ? formatPercent(val) : typeof v === "string" ? v : JSON.stringify(v)];
  });
}

export default function ProofScreen() {
  const pid = useProjectId();
  const status = useStatus();
  const envVar = useKeyEnvVar();
  const isLg = useMediaQuery(MQ.lg);
  const [params, setParams] = useSearchParams();
  const runs = useFidelityRuns(pid);
  const runList = useMemo(() => [...(runs.data?.items ?? [])].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)), [runs.data]);
  const fid = params.get("run") ?? runList[0]?.id;
  const run = useFidelityRun(fid);
  const caseN = params.get("case") ? Number(params.get("case")) : undefined;
  const [useBatch, setUseBatch] = useState(false);
  const gate = useGate({ live: true });
  const again = useConfirmableAction<void>(
    (_v, token) => call(api.POST("/api/v1/projects/{pid}/fidelity-runs", { params: { path: { pid: pid! } }, body: { use_batch: useBatch, lens_version: run.data?.lens_version ?? null, confirm_token: token ?? null } })),
    () => ({ title: t("proof.run.confirmTitle"), description: t("proof.run.confirmBody"), duration: useBatch ? t("proof.run.batchDuration") : t("proof.run.duration") }),
  );

  const set = (k: string, v: string | null) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v);
    else next.delete(k);
    setParams(next, { replace: true });
  };

  if (!pid || runs.isLoading || (fid && run.isLoading))
    return (
      <div className="k-page">
        <Delayed>
          <Skeleton shape="block" className="mb-4 h-24" />
          <Skeleton lines={8} />
        </Delayed>
      </div>
    );
  if (runs.error) return <PageError error={runs.error} onRetry={() => void runs.refetch()} />;

  const live = status.data?.live ?? false;
  const runButton = (
    <div className="flex flex-wrap items-center gap-3">
      {status.data?.batch_enabled ? <Checkbox checked={useBatch} onCheckedChange={setUseBatch} label={t("proof.run.batch")} /> : null}
      <Button icon={Play} disabled={Boolean(gate)} title={gate} loading={again.pending} onClick={() => void again.run()}>
        {runList.length ? t("proof.run.again") : t("proof.run.first")}
      </Button>
    </div>
  );
  const jobLine = again.jobId ? <JobProgress jobId={again.jobId} /> : null;
  const keyLine = again.keyRequired ? <KeyRequired what={t("proof.run.needsKey")} provider={status.data?.provider ?? ""} envVar={envVar} /> : again.error ? <InlineError error={again.error} /> : null;

  if (!fid)
    return (
      <div className="k-page space-y-4">
        <AnswerHeader title={t("proof.none.title")} />
        {live ? <EmptyState title={t("proof.none.body")} action={runButton} /> : <EmptyState title={t("proof.none.saved")} />}
        {jobLine}
        {keyLine}
      </div>
    );
  if (run.error) return <PageError error={run.error} onRetry={() => void run.refetch()} />;
  const r = run.data!;
  const name = personName(r.person);
  const keeper = systemMetrics(r, "keeper");
  const lens = systemMetrics(r, "lens");
  const baseline = systemMetrics(r, "baseline");
  const holdout = obj(r.holdout);
  const prs = num(holdout.prs) ?? r.cases_count;
  const failed = r.criteria.filter((c) => c.passed === false);
  const pass = r.pass_overall;
  const pct = (m: Metric | null | undefined) => formatPercent(m?.value);

  return (
    <div className="k-page mx-auto w-full max-w-[130rem] space-y-6">
      <AnswerHeader
        tour="proof_verdict"
        title={
          <span className="inline-flex items-start gap-2">
            {pass ? <CheckCircle2 className="mt-1 size-7 shrink-0 text-success" aria-hidden /> : <AlertTriangle className="mt-1 size-7 shrink-0 text-warning" aria-hidden />}
            <span>{pass ? t("proof.verdict.pass", { name, n: prs }) : t("proof.verdict.fail")}</span>
          </span>
        }
        subtitle={
          <span className="space-y-1">
            <span className="block">{t("proof.verdict.line1", { name, k: pct(keeper?.substantive_recall), b: pct(baseline?.substantive_recall) })}</span>
            {lens?.residual_recall ? <span className="block">{t("proof.verdict.line2", { name, r: pct(lens.residual_recall) })}</span> : null}
            {!pass && failed.length ? (
              <span className="block text-warning-fg">
                {t("proof.verdict.failed", { list: failed.map((c) => c.label).join(", ") })}{" "}
                <Link to="/lens?tab=items&status=low_confidence" className="underline">
                  {t("proof.verdict.lowPrecision")}
                </Link>
              </span>
            ) : null}
          </span>
        }
        eyebrow={
          <>
            <span>{t("proof.eyebrow", { v: r.lens_version, date: formatDate(r.created_at, true) })}</span>
            <ProvenanceBadge provenance={r.provenance} />
          </>
        }
        actions={
          <>
            <SelectField
              label={t("proof.runPicker")}
              hideLabel
              value={fid}
              onChange={(e) => set("run", e.target.value)}
              options={runList.map((x) => ({
                value: x.id,
                label: t("proof.runOption", {
                  v: x.lens_version,
                  date: formatDate(x.created_at),
                  origin: x.simulated ? t("provenance.savedSimulated") : x.origin === "snapshot" ? t("common.saved_run") : t("common.live"),
                  pass: x.pass_overall ? t("proof.pass") : t("proof.fail"),
                }),
              }))}
            />
            {runButton}
          </>
        }
      />
      {jobLine}
      {keyLine}

      <section className="k-card @container space-y-4 p-4">
        <CompareBars
          title={t("proof.bars.title", { name })}
          tooltip={t("proof.bars.tip", { name })}
          rows={[
            { key: "keeper", label: t("proof.sys.keeper"), metric: keeper?.substantive_recall, tone: "primary" },
            { key: "lens", label: t("proof.sys.lens"), metric: lens?.substantive_recall, tone: "edge" },
            { key: "baseline", label: t("proof.sys.baseline"), metric: baseline?.substantive_recall, tone: "baseline" },
          ]}
          difference={r.paired_difference}
        />
        <div className="space-y-2 border-t border-border pt-3">
          <h3 className="text-base font-semibold">
            <Term term="residual">{t("proof.residual.title", { name })}</Term>
          </h3>
          <MetricBar label={t("proof.sys.lens")} metric={lens?.residual_recall} tone="edge" />
          <MetricBar label={t("proof.sys.keeper")} metric={keeper?.residual_recall} tone="primary" />
          <p className="text-xs text-muted">{t("proof.residual.zero")}</p>
        </div>
      </section>

      <section aria-labelledby="crit-h" className="space-y-2">
        <h2 id="crit-h" className="text-lg font-semibold">
          {t("proof.criteria.title")}
        </h2>
        <CriteriaList items={r.criteria} />
      </section>

      <section aria-labelledby="fals-h" className="space-y-2">
        <h2 id="fals-h" className="text-lg font-semibold">
          {t("proof.falsifiers.title")}
        </h2>
        <FalsifierList items={r.falsifiers} />
      </section>

      {Object.keys(r.sensitivity ?? {}).length ? (
        <Disclosure summary={<span className="text-base font-semibold">{t("proof.sensitivity.title")}</span>} className="k-card p-4">
          <p className="mb-2 text-sm text-muted">{t("proof.sensitivity.body")}</p>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            {sensitivityRows(r.sensitivity ?? {}).map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted">{k}</dt>
                <dd className="tabular">{v}</dd>
              </div>
            ))}
          </dl>
        </Disclosure>
      ) : null}

      <HowThisWorks maintainer={name} />
      <p className="text-xs text-muted">{t("proof.cost", { amount: formatMoney(r.cost_usd), n: r.cases_count })}</p>

      <div className={cx(isLg ? "h-[min(80dvh,60rem)]" : "space-y-6")}>
        {isLg ? (
          <SplitPane
            id="proof"
            className="h-full"
            panes={[
              { id: "cases", defaultSize: 38, minSize: 25, content: <div className="h-full pr-3"><CaseList fid={fid} selected={caseN} onSelect={(n) => set("case", String(n))} maintainer={name} /></div> },
              { id: "detail", defaultSize: 62, minSize: 35, content: <div className="h-full overflow-y-auto pl-3">{caseN !== undefined ? <CaseDetailPane fid={fid} n={caseN} maintainer={name} /> : <EmptyState compact title={t("proof.cases.pick")} />}</div> },
            ]}
          />
        ) : (
          <>
            <div className="h-[60dvh]">
              <CaseList fid={fid} selected={caseN} onSelect={(n) => set("case", String(n))} maintainer={name} />
            </div>
            {caseN !== undefined ? <CaseDetailPane fid={fid} n={caseN} maintainer={name} /> : null}
          </>
        )}
      </div>
      <Link to="/practice" className={cx(buttonClass("ghost"), "sr-only focus:not-sr-only")}>
        {t("proof.toPractice")}
      </Link>
    </div>
  );
}
