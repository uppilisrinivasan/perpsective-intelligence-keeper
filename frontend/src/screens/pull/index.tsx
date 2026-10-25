import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, CircleX, Copy, ExternalLink, Hand, MessageSquare, MoreHorizontal, RefreshCw, WrapText, Columns2, Wrench } from "lucide-react";
import { api, call } from "@/api/client";
import { isNotFound } from "@/api/errors";
import { useConfirmableAction } from "@/api/hooks/confirm";
import { useJob } from "@/api/hooks/jobs";
import { startAnalysis, startFix, startHandoff, useAnalysis, useCompare, useDiff, useFindingFeedback, useFixes, useHandoff, useHumanReview, usePull, useReviewDraft } from "@/api/hooks/pull";
import { useSettings } from "@/api/hooks/settings";
import { useProject, useProjectId, useStatus } from "@/api/hooks/system";
import { keys } from "@/api/keys";
import type { DiffFile, RoutedFinding } from "@/api/types";
import { AnswerHeader } from "@/components/keeper/AnswerHeader";
import { CompareView } from "@/components/keeper/CompareView";
import { DiffView, fileAnchorId, lineAnchorId } from "@/components/keeper/DiffView";
import { FindingCard } from "@/components/keeper/FindingCard";
import { HandoffCard } from "@/components/keeper/HandoffCard";
import { JobProgress } from "@/components/keeper/JobProgress";
import { LaneBadge } from "@/components/keeper/Lane";
import { ProvenanceBadge } from "@/components/keeper/Provenance";
import { SignalChips } from "@/components/keeper/ReasonLine";
import { ReviewDraftPanel } from "@/components/keeper/ReviewDraftPanel";
import { EmptyState, InlineError, KeyRequired, PageError } from "@/components/keeper/States";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { IconButton } from "@/components/ui/IconButton";
import { Markdown } from "@/components/ui/Markdown";
import { Menu } from "@/components/ui/Menu";
import { Segmented } from "@/components/ui/Segmented";
import { SelectField } from "@/components/ui/Field";
import { SplitPane } from "@/components/ui/SplitPane";
import { Delayed, Skeleton } from "@/components/ui/Skeleton";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { Tooltip } from "@/components/ui/Tooltip";
import { t } from "@/copy/t";
import { cx } from "@/lib/cx";
import { copyText } from "@/lib/clipboard";
import { errorMessage } from "@/lib/errors";
import { formatRelative, personName } from "@/lib/format";
import { isTypingTarget } from "@/lib/shortcuts";
import { readSession } from "@/lib/storage";
import { MQ, useMediaQuery } from "@/lib/useMedia";
import { ask } from "@/state/ask";
import { setPref, usePrefs } from "@/state/prefs";
import { toast } from "@/state/toasts";
import { useGate } from "@/screens/shared/permissions";
import { maintainerName } from "@/screens/shared/lens";
import { useKeyEnvVar } from "@/shell/AppShell";
import { QUEUE_RETURN_KEY } from "@/screens/queue";
import { AnalysisStages, FindingsPane } from "./FindingsPane";
import { FixPanel } from "./FixPanel";

type View = "diff" | "compare";

function ChecksLine({ checks }: { checks: Array<{ name: string; conclusion?: string | null }> }) {
  if (!checks.length) return null;
  const failed = checks.filter((c) => c.conclusion && !["success", "neutral", "skipped"].includes(c.conclusion));
  const ok = failed.length === 0;
  return (
    <Tooltip content={checks.map((c) => `${c.name}: ${c.conclusion ?? t("pr.ci.pending")}`).join("\n")}>
      <span tabIndex={0} className={cx("inline-flex items-center gap-1", ok ? "text-success-fg" : "text-danger-fg")}>
        {ok ? <CheckCircle2 className="size-3.5" aria-hidden /> : <CircleX className="size-3.5" aria-hidden />}
        {ok ? t("pr.ci.ok") : t("pr.ci.failed", { n: failed.length })}
      </span>
    </Tooltip>
  );
}

export default function PullScreen() {
  const { number: numParam, fixId } = useParams();
  const n = Number(numParam);
  const pid = useProjectId();
  const status = useStatus();
  const project = useProject(pid);
  const settings = useSettings();
  const prefs = usePrefs();
  const navigate = useNavigate();
  const location = useLocation();
  const qc = useQueryClient();
  const envVar = useKeyEnvVar();
  const [params, setParams] = useSearchParams();
  const view: View = params.get("view") === "compare" ? "compare" : "diff";
  const focusFinding = params.get("finding");
  const isLg = useMediaQuery(MQ.lg);
  const isXl = useMediaQuery(MQ.xl);
  const isXxl = useMediaQuery(MQ.xxl);
  const [tab, setTab] = useState("findings");
  const [flash, setFlash] = useState<{ path: string; line: number | null } | null>(null);
  const [extraFiles, setExtraFiles] = useState<Record<string, DiffFile>>({});
  const [fileFilter, setFileFilter] = useState("");

  const pull = usePull(pid, n);
  const analysis = useAnalysis(pid, n);
  const diff = useDiff(pid, n);
  const compare = useCompare(pid, n, view === "compare" && !analysis.error);
  const human = useHumanReview(pid, n, view === "compare" && Boolean(pull.data?.has_human_review) && !compare.data?.human);
  const draft = useReviewDraft(pid, n);
  const lane = analysis.data?.lane;
  const handoff = useHandoff(pid, n, lane === "unknown");
  const feedback = useFindingFeedback(pid, n);
  const fixRuns = useFixes(pid, n);
  const editable = (key: string) => settings.data?.editable.find((e) => e.key === key)?.value;
  const wrap = prefs.diffWrap ?? Boolean(editable("diff_wrap"));
  const split = isXl && (prefs.diffSplit ?? editable("diff_view") === "split");
  const showBaselineOnly = Boolean(editable("show_baseline_only"));

  const maintainer = maintainerName(compare.data?.maintainer ?? project.data?.primary_maintainer, t("people.unknown"));
  const feedbackGate = useGate({ maintainer: true });
  const actionGate = useGate({ live: true, maintainer: true });

  const analyse = useConfirmableAction<void>((_v, token) => startAnalysis(pid!, n, token), { title: t("pr.analyse.confirmTitle", { n }), description: t("pr.analyse.confirmBody") });
  const analyseJob = useJob(analyse.jobId);
  useEffect(() => {
    if (analyseJob?.phase === "completed") void analysis.refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analyseJob?.phase]);

  const fix = useConfirmableAction<RoutedFinding>((f, token) => startFix(pid!, n, [f.id], undefined, token), (f) => ({ title: t("fix.confirmTitle"), description: f.title, duration: t("pr.fix.duration") }), {
    onJob: (jobId) => navigate(`/pr/${n}/fix/${jobId}`),
  });
  const suggestHandoff = useConfirmableAction<void>((_v, token) => startHandoff(pid!, n, token), { title: t("handoff.suggest") });
  const handoffJob = useJob(suggestHandoff.jobId);
  useEffect(() => {
    if (handoffJob?.phase === "completed") void handoff.refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handoffJob?.phase]);

  const files: DiffFile[] = useMemo(() => (diff.data?.files ?? []).map((f) => extraFiles[f.filename] ?? f), [diff.data, extraFiles]);
  const shownFiles = fileFilter ? files.filter((f) => f.filename === fileFilter) : files;
  const findings = useMemo(() => analysis.data?.findings ?? [], [analysis.data]);
  const inlineFindings = useMemo(() => findings.filter((f) => f.anchor.scope !== "pr" && (f.lane !== "baseline_only" || showBaselineOnly)), [findings, showBaselineOnly]);

  const loadLarge = useCallback(
    async (filename: string) => {
      if (!pid) return;
      try {
        const res = await call(api.GET("/api/v1/projects/{pid}/pulls/{n}/diff", { params: { path: { pid, n }, query: { file: filename } } }));
        const f = res.files.find((x) => x.filename === filename);
        if (f) setExtraFiles((m) => ({ ...m, [filename]: { ...f, too_large: false } }));
      } catch (e) {
        toast({ tone: "danger", title: errorMessage(e) });
      }
    },
    [pid, n],
  );

  const setView = (v: string) => {
    const next = new URLSearchParams(params);
    if (v === "diff") next.delete("view");
    else next.set("view", v);
    setParams(next, { replace: true });
    if (!isLg) setTab("diff");
  };

  const locate = useCallback(
    (path: string, line: number | null) => {
      if (view !== "diff") setView("diff");
      if (!isLg) setTab("diff");
      setFlash({ path, line });
      requestAnimationFrame(() =>
        setTimeout(() => {
          const el = document.getElementById(line ? lineAnchorId(path, line) : fileAnchorId(path)) ?? document.getElementById(fileAnchorId(path));
          el?.scrollIntoView({ block: "center", behavior: "smooth" });
        }, 50),
      );
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [view, isLg, params],
  );

  // Deep link ?finding= scrolls to the finding.
  useEffect(() => {
    if (!focusFinding || !analysis.data) return;
    const f = analysis.data.findings.find((x) => x.id === focusFinding || x.finding_id === focusFinding);
    if (f?.anchor.path) locate(f.anchor.path, f.anchor.end_line ?? f.anchor.start_line ?? null);
    else document.getElementById(`finding-${focusFinding}`)?.scrollIntoView({ block: "center" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusFinding, analysis.data]);

  useEffect(() => {
    if (location.hash === "#handoff") setTimeout(() => document.getElementById("handoff")?.scrollIntoView({ block: "start" }), 200);
  }, [location.hash, handoff.data]);

  // j/k next/previous finding, n/p next/previous file, w wrap.
  useEffect(() => {
    const ordered = inlineFindings.filter((f) => f.anchor.path);
    let fi = -1;
    let fl = -1;
    const onKey = (e: KeyboardEvent) => {
      if (isTypingTarget(e.target) || e.metaKey || e.ctrlKey || e.altKey || !prefs.shortcuts) return;
      if (e.key === "j" || e.key === "k") {
        if (!ordered.length) return;
        fi = (fi + (e.key === "j" ? 1 : -1) + ordered.length) % ordered.length;
        const f = ordered[fi]!;
        locate(f.anchor.path!, f.anchor.end_line ?? f.anchor.start_line ?? null);
      } else if (e.key === "n" || e.key === "p") {
        if (!files.length) return;
        fl = (fl + (e.key === "n" ? 1 : -1) + files.length) % files.length;
        document.getElementById(fileAnchorId(files[fl]!.filename))?.scrollIntoView({ block: "start", behavior: "smooth" });
      } else if (e.key === "w") {
        setPref("diffWrap", !wrap);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [inlineFindings, files, locate, wrap, prefs.shortcuts]);

  if (!pid || pull.isLoading)
    return (
      <div className="k-page">
        <Delayed>
          <Skeleton shape="block" className="mb-4 h-20" />
          <Skeleton lines={8} />
        </Delayed>
      </div>
    );
  if (pull.error) return <PageError error={pull.error} onRetry={() => void pull.refetch()} />;
  const pr = pull.data!;
  const a = analysis.data;
  const noAnalysis = analysis.error && isNotFound(analysis.error);
  const live = status.data?.live ?? false;
  const backTo = `/queue${readSession<string>(QUEUE_RETURN_KEY, "") ? `?${readSession<string>(QUEUE_RETURN_KEY, "")}` : ""}`;
  const fixable = findings.filter((f) => f.fixable && (f.lane === "edge" || f.lane === "blind_spot") && f.user_state !== "dismissed");

  const onFeedback = (f: RoutedFinding, p: { state: string; text?: string; severity?: string; reason?: string }) =>
    feedback.mutate(
      { id: f.id, body: { state: p.state as "accepted", text: p.text ?? null, severity: p.severity ?? null, reason: p.reason ?? null } },
      { onError: (e) => toast({ tone: "danger", title: errorMessage(e) }) },
    );
  const onAsk = (f: RoutedFinding) => ask.open({ screen: "pr", number: n, finding_id: f.id, finding_title: f.title });
  const copyDraft = async () => {
    const body = draft.data?.body_md ?? "";
    if (body && (await copyText(body))) toast({ tone: "success", title: t("draft.copiedToast") });
  };

  // Primary action depends on the lane (screens/02).
  const primary = (() => {
    if (!a) return null;
    if (a.lane === "unknown")
      return handoff.data ? (
        <Button variant="primary" icon={Hand} onClick={() => document.getElementById("handoff")?.scrollIntoView({ block: "start", behavior: "smooth" })}>
          {t("pr.primary.handTo", { name: personName(handoff.data.target) })}
        </Button>
      ) : null;
    if (a.lane === "shared")
      return (
        <Button variant="primary" icon={Copy} onClick={() => void copyDraft()}>
          {t("pr.primary.approve")}
        </Button>
      );
    const savedFix = [...(fixRuns.data?.items ?? [])].sort((x, y) => Date.parse(y.created_at) - Date.parse(x.created_at))[0];
    if (fixable[0] && !live && savedFix && !fixId)
      return (
        <Button variant="primary" icon={Wrench} onClick={() => navigate(`/pr/${n}/fix/${savedFix.id}`)}>
          {t("pr.primary.savedFix")}
        </Button>
      );
    if (fixable[0])
      return (
        <Tooltip content={actionGate}>
          <span>
            <Button variant="primary" icon={Wrench} loading={fix.pending} disabled={Boolean(actionGate)} onClick={() => void fix.run(fixable[0]!)}>
              {t("finding.action.fix")}
            </Button>
          </span>
        </Tooltip>
      );
    return (
      <Button variant="primary" icon={Copy} onClick={() => void copyDraft()}>
        {t("draft.copy")}
      </Button>
    );
  })();

  const header = (
    <div className="space-y-3 border-b border-border pb-4">
      <Link to={backTo} className="inline-flex items-center gap-1 text-sm text-muted hover:text-text">
        <ArrowLeft className="size-4" aria-hidden />
        {t("pr.back")}
      </Link>
      <AnswerHeader
        title={
          <>
            <span className="mr-2 text-muted tabular">{t("format.prNumber", { n: pr.number })}</span>
            {pr.title}
          </>
        }
        eyebrow={
          a ? (
            <>
              <LaneBadge lane={a.lane} size="md" maintainer={maintainer} />
              <span className="tabular">{t("format.approxMinutes", { m: a.attention_minutes })}</span>
            </>
          ) : null
        }
        actions={
          <>
            {primary}
            <Button icon={MessageSquare} onClick={() => ask.open({ screen: "pr", number: n })}>
              {t("common.askAboutThis")}
            </Button>
            <Menu
              label={t("common.more")}
              trigger={<IconButton icon={MoreHorizontal} label={t("common.more")} />}
              items={[
                { key: "analyse", label: t("pr.analyse.again"), icon: RefreshCw, onSelect: () => void analyse.run(), disabled: Boolean(actionGate), disabledReason: actionGate },
                ...(pr.html_url && project.data && !project.data.fictional ? [{ key: "gh", label: t("pr.viewOnGithub"), icon: ExternalLink, onSelect: () => window.open(pr.html_url!, "_blank", "noopener") }] : []),
              ]}
            />
          </>
        }
      />
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
        <span>{t("pr.meta.wants", { author: personName(pr.author), commits: pr.commits, base: pr.base })}</span>
        {pr.author.first_time ? <Badge tone="outline">{t("queue.row.firstTime")}</Badge> : null}
        {pr.author.association ? <span>{pr.author.association.toLowerCase()}</span> : null}
        <span aria-hidden>·</span>
        <span className="tabular">{t("format.plusMinus", { add: pr.additions, del: pr.deletions })}</span>
        <span aria-hidden>·</span>
        <span>{t("pr.meta.files", { n: pr.files.length })}</span>
        <ChecksLine checks={pr.checks} />
      </p>
      {a?.summary_md ? (
        <div className="rounded-md border-l-4 border-l-primary bg-surface-2 p-3">
          <p className="mb-1 flex items-center gap-2 text-xs font-medium text-muted">
            {t("pr.summary")} <Badge tone="outline">{t("common.drafted")}</Badge>
          </p>
          <Markdown source={a.summary_md} className="text-sm" />
        </div>
      ) : null}
      {a?.signals.length ? <SignalChips signals={a.signals} /> : null}
      {a ? (
        <p className="flex flex-wrap items-center gap-2 text-xs text-muted">
          <span>{t("pr.provenance", { when: formatRelative(a.provenance.computed_at), v: a.lens_version ?? a.provenance.lens_version ?? "" })}</span>
          <ProvenanceBadge provenance={a.provenance} />
        </p>
      ) : null}
      {analyse.keyRequired ? <KeyRequired what={t("pr.analyse.needsKey")} provider={status.data?.provider ?? ""} envVar={envVar} /> : null}
      {analyse.error ? <InlineError error={analyse.error} onRetry={() => void analyse.run()} /> : null}
      {fix.keyRequired ? <KeyRequired what={t("fix.needsKey")} provider={status.data?.provider ?? ""} envVar={envVar} /> : null}
      {fix.error ? <InlineError error={fix.error} /> : null}
    </div>
  );

  const handoffSlot =
    a?.lane === "unknown" ? (
      handoff.data ? (
        <HandoffCard handoff={handoff.data} />
      ) : handoff.isLoading ? (
        <Skeleton lines={4} />
      ) : (
        <div className="space-y-2 rounded-md border border-unknown-border bg-unknown-bg/40 p-4">
          <p className="text-sm">{t("handoff.none")}</p>
          {suggestHandoff.jobId ? <JobProgress jobId={suggestHandoff.jobId} compact /> : null}
          <Button variant="primary" icon={Hand} disabled={Boolean(actionGate)} title={actionGate} loading={suggestHandoff.pending} onClick={() => void suggestHandoff.run()}>
            {t("handoff.suggest")}
          </Button>
          {suggestHandoff.error ? <InlineError error={suggestHandoff.error} /> : null}
        </div>
      )
    ) : null;

  const findingsPane = fixId ? (
    <FixPanel pid={pid} number={n} fixParam={fixId} findings={findings} draft={draft.data} onBack={() => navigate(`/pr/${n}${location.search}`)} />
  ) : analysis.isLoading ? (
    <Skeleton lines={6} />
  ) : noAnalysis ? (
    <div className="space-y-3">
      {analyseJob && analyseJob.phase !== "completed" ? (
        <>
          <JobProgress jobId={analyse.jobId!} compact />
          <AnalysisStages job={analyseJob} />
        </>
      ) : live ? (
        <EmptyState
          compact
          title={t("pr.noAnalysis")}
          action={
            <Button variant="primary" disabled={Boolean(actionGate)} title={actionGate} loading={analyse.pending} onClick={() => void analyse.run()}>
              {t("pr.analyse.label")}
            </Button>
          }
        />
      ) : (
        <EmptyState compact title={t("pr.notInSaved")} body={t("pr.notInSavedBody")} />
      )}
    </div>
  ) : analysis.error ? (
    <InlineError error={analysis.error} onRetry={() => void analysis.refetch()} message={analysis.error && errorMessage(analysis.error)} />
  ) : a ? (
    <>
      {analyseJob && !["completed", "failed", "cancelled"].includes(analyseJob.phase) ? (
        <div className="mb-4 space-y-2">
          <JobProgress jobId={analyse.jobId!} compact />
          <AnalysisStages job={analyseJob} />
        </div>
      ) : null}
      <FindingsPane
        pid={pid}
        n={n}
        analysis={a}
        handoff={handoff.data}
        handoffSlot={handoffSlot}
        files={files}
        maintainer={maintainer}
        showBaselineOnly={showBaselineOnly}
        onFeedback={onFeedback}
        onFix={(f) => void fix.run(f)}
        onAsk={onAsk}
        onLocate={locate}
        feedbackGate={feedbackGate}
        fixGate={actionGate}
        highlighted={focusFinding}
        fixPrimaryId={undefined}
      />
    </>
  ) : null;

  const compareHuman = compare.data?.human ?? human.data?.findings ?? (pull.data?.has_human_review ? null : undefined);
  const diffToolbar = (
    <div className="mb-3 flex flex-wrap items-center gap-2">
      <Segmented
        label={t("pr.view.label")}
        value={view}
        onChange={setView}
        options={[
          { value: "diff", label: t("pr.view.diff") },
          { value: "compare", label: t("pr.view.compare") },
        ]}
      />
      {view === "diff" && files.length > 1 ? (
        <SelectField
          label={t("pr.files.label")}
          hideLabel
          className="min-w-0 flex-[0_1_20rem]"
          value={fileFilter}
          onChange={(e) => setFileFilter(e.target.value)}
          options={[{ value: "", label: t("pr.files.all", { n: files.length }) }, ...files.map((f) => ({ value: f.filename, label: f.filename }))]}
        />
      ) : null}
      {view === "diff" ? (
        <div className="ml-auto flex items-center gap-1">
          <IconButton icon={WrapText} label={wrap ? t("pr.wrapOff") : t("pr.wrapOn")} aria-pressed={wrap} onClick={() => setPref("diffWrap", !wrap)} />
          {isXl ? <IconButton icon={Columns2} label={split ? t("pr.unified") : t("pr.split")} aria-pressed={split} onClick={() => setPref("diffSplit", !split)} /> : null}
        </div>
      ) : null}
    </div>
  );

  const diffPane = (
    <div>
      {diffToolbar}
      {view === "compare" ? (
        compare.isLoading ? (
          <Skeleton lines={6} />
        ) : compare.error ? (
          isNotFound(compare.error) ? (
            <EmptyState compact title={t("pr.compare.none")} />
          ) : (
            <InlineError error={compare.error} onRetry={() => void compare.refetch()} />
          )
        ) : compare.data ? (
          <CompareView
            baseline={compare.data.baseline}
            lens={compare.data.lens}
            pairs={compare.data.pairs}
            residual={compare.data.residual}
            human={compareHuman}
            humanPairs={compare.data.human_pairs}
            maintainer={maintainer}
            onOpenFinding={(id) => {
              const f = findings.find((x) => x.finding_id === id || x.id === id || x.evidence.baseline_pair?.finding_id === id);
              if (f?.anchor.path) locate(f.anchor.path, f.anchor.end_line ?? f.anchor.start_line ?? null);
              else setView("diff");
            }}
          />
        ) : null
      ) : diff.isLoading ? (
        <Skeleton lines={10} />
      ) : diff.error ? (
        <InlineError error={diff.error} onRetry={() => void diff.refetch()} />
      ) : (
        <DiffView
          files={shownFiles}
          findings={inlineFindings}
          wrap={wrap}
          split={split}
          flash={flash}
          onLoadLarge={loadLarge}
          renderFinding={(f) => (
            <FindingCard
              finding={f}
              variant="inline"
              maintainer={maintainer}
              onFeedback={(p) => onFeedback(f, p)}
              onFix={() => void fix.run(f)}
              onAsk={() => onAsk(f)}
              canFix
              disabledReason={feedbackGate}
              fixDisabledReason={actionGate}
            />
          )}
        />
      )}
    </div>
  );

  const draftPane = draft.isLoading ? (
    <Skeleton lines={5} />
  ) : draft.data ? (
    <ReviewDraftPanel
      draft={draft.data}
      readOnlyReason={feedbackGate}
      onLocate={(path, line) => locate(path, line)}
      onSave={async (body_md) => {
        const saved = await call(api.PUT("/api/v1/projects/{pid}/pulls/{n}/review-draft", { params: { path: { pid, n } }, body: { body_md, comments: draft.data?.comments ?? [] } }));
        qc.setQueryData(keys.pullPart(pid, n, "draft"), saved);
      }}
      onExport={(format) => call(api.GET("/api/v1/projects/{pid}/pulls/{n}/review-draft/export", { params: { path: { pid, n }, query: { format } } }))}
    />
  ) : (
    <p className="text-sm text-muted">{t("draft.none")}</p>
  );

  if (!isLg) {
    return (
      <div className="k-page space-y-4">
        {header}
        <Tabs
          value={tab}
          onValueChange={setTab}
          label={t("pr.tabs.label")}
          tabs={[
            { value: "findings", label: fixId ? t("fix.title") : t("pr.tabs.findings") },
            { value: "diff", label: view === "compare" ? t("pr.view.compare") : t("pr.view.diff") },
            { value: "draft", label: t("pr.tabs.draft") },
          ]}
        >
          <TabPanel value="findings" className="pt-4">
            {findingsPane}
          </TabPanel>
          <TabPanel value="diff" className="pt-4">
            {diffPane}
          </TabPanel>
          <TabPanel value="draft" className="pt-4">
            {draftPane}
          </TabPanel>
        </Tabs>
      </div>
    );
  }

  return (
    <div className="mx-auto flex h-[calc(100dvh-var(--topbar-height))] w-full max-w-[140rem] flex-col">
      <div className="max-h-[45dvh] shrink-0 overflow-y-auto px-(--gutter) pt-4">{header}</div>
      <div className="min-h-0 flex-1 px-(--gutter) pb-2">
        <SplitPane
          id={isXxl ? "pr3" : "pr"}
          className="h-full"
          panes={[
            { id: "findings", defaultSize: isXxl ? 30 : 38, minSize: 22, content: <div className="h-full overflow-y-auto py-4 pr-3" aria-label={t("pr.tabs.findings")} role="region">{findingsPane}</div> },
            { id: "diff", defaultSize: isXxl ? 45 : 62, minSize: 35, content: <div className="h-full overflow-y-auto py-4 pl-3 pr-1" role="region" aria-label={t("pr.view.diff")}>{diffPane}</div> },
            ...(isXxl ? [{ id: "draft", defaultSize: 25, minSize: 18, content: <div className="h-full overflow-y-auto py-4 pl-3" role="region" aria-label={t("pr.tabs.draft")}>{draftPane}</div> }] : []),
          ]}
        />
      </div>
      {!isXxl ? (
        <div className="max-h-[40dvh] shrink-0 overflow-y-auto border-t border-border px-(--gutter) py-2">
          <details className="group">
            <summary className="cursor-pointer list-none py-1 text-sm font-semibold">
              <span className="inline-flex items-center gap-2">
                {t("pr.tabs.draft")} <Badge tone="outline">{t("common.drafted")}</Badge>
              </span>
            </summary>
            <div className="pt-2">{draftPane}</div>
          </details>
        </div>
      ) : null}
    </div>
  );
}
