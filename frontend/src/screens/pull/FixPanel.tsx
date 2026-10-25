import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ClipboardCopy, Download, FilePlus2, RotateCcw, ShieldCheck } from "lucide-react";
import { api, call, downloadWithHeaders, urls } from "@/api/client";
import { useJob } from "@/api/hooks/jobs";
import { startFix, useFix, useFixes } from "@/api/hooks/pull";
import { useConfirmableAction } from "@/api/hooks/confirm";
import { useStatus } from "@/api/hooks/system";
import { keys } from "@/api/keys";
import { cancelJob } from "@/api/jobs";
import type { DiffFile, ReviewDraft, RoutedFinding } from "@/api/types";
import { DiffView } from "@/components/keeper/DiffView";
import { FixTimeline } from "@/components/keeper/FixTimeline";
import { ProvenanceBadge } from "@/components/keeper/Provenance";
import { InlineError, KeyRequired } from "@/components/keeper/States";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { TextArea } from "@/components/ui/Field";
import { Skeleton } from "@/components/ui/Skeleton";
import { t } from "@/copy/t";
import { copyText } from "@/lib/clipboard";
import { splitMultiFileDiff, toSuggestion } from "@/lib/diff";
import { fixFromEvents, fixFromRun, isFixSuccess } from "@/lib/fix";
import { formatMoney } from "@/lib/format";
import { errorMessage } from "@/lib/errors";
import { str } from "@/lib/unknown";
import { toast } from "@/state/toasts";
import { useGate } from "@/screens/shared/permissions";
import { useKeyEnvVar } from "@/shell/AppShell";

export interface FixPanelProps {
  pid: string;
  number: number;
  /** A fix id (fix_…) or, while it starts, the job id (job_…). */
  fixParam: string;
  findings: RoutedFinding[];
  draft?: ReviewDraft;
  onBack: () => void;
}

function useDraftAppend(pid: string, n: number) {
  const qc = useQueryClient();
  return async (draft: ReviewDraft | undefined, text: string) => {
    const body = [draft?.body_md ?? "", text].filter(Boolean).join("\n\n");
    const saved = await call(api.PUT("/api/v1/projects/{pid}/pulls/{n}/review-draft", { params: { path: { pid, n } }, body: { body_md: body, comments: draft?.comments ?? [] } }));
    qc.setQueryData(keys.pullPart(pid, n, "draft"), saved);
  };
}

/** Fix and test: the live timeline (job events) or a saved fix run, the winning diff, and what to do with it. */
export function FixPanel({ pid, number, fixParam, findings, draft, onBack }: FixPanelProps) {
  const navigate = useNavigate();
  const status = useStatus();
  const envVar = useKeyEnvVar();
  const isJob = fixParam.startsWith("job_");
  const fix = useFix(isJob ? undefined : fixParam);
  const liveJobId = isJob ? fixParam : fix.data && ["running", "queued"].includes(fix.data.status) ? fix.data.job_id : null;
  const job = useJob(liveJobId);
  const [hint, setHint] = useState("");
  const appendDraft = useDraftAppend(pid, number);
  const gate = useGate({ live: true, maintainer: true });

  // When the job finishes, move to the fix run's own URL (from the job result, or the PR's fix list).
  const fixes = useFixes(isJob && job?.phase === "completed" ? pid : undefined, number);
  useEffect(() => {
    if (!isJob || job?.phase !== "completed") return;
    const fixId = str(job.result?.fix_id) ?? str(job.result?.id) ?? fixes.data?.items.find((f) => f.job_id === fixParam)?.id;
    if (fixId) navigate(`/pr/${number}/fix/${fixId}`, { replace: true });
  }, [isJob, job?.phase, job?.result, fixes.data, fixParam, navigate, number]);

  useEffect(() => {
    if (!isJob && job?.phase === "completed") void fix.refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.phase]);

  const vm = useMemo(() => {
    if (job && (isJob || (fix.data && ["running", "queued"].includes(fix.data.status)))) return fixFromEvents(job.events, job.phase);
    return fix.data ? fixFromRun(fix.data) : null;
  }, [job, fix.data, isJob]);

  const findingIds = fix.data?.finding_ids ?? [];
  const target = findings.filter((f) => findingIds.includes(f.id));
  const title = (fix.data?.findings?.[0] ?? target[0])?.title;

  const retry = useConfirmableAction<string>(
    (userHint, token) => startFix(pid, number, findingIds, userHint, token),
    { title: t("fix.confirmTitle"), description: title },
    { onJob: (jobId) => navigate(`/pr/${number}/fix/${jobId}`) },
  );

  const files: DiffFile[] = useMemo(() => {
    const winning = fix.data?.branches.find((b) => b.name === fix.data?.winning_branch);
    const diff = fix.data?.diff ?? winning?.diff;
    return splitMultiFileDiff(diff).map((f) => ({ filename: f.filename, patch: f.patch, status: "modified", binary: false, too_large: false }));
  }, [fix.data]);

  if (!isJob && fix.isLoading) return <Skeleton lines={6} />;
  if (!isJob && fix.error) return <InlineError error={fix.error} onRetry={() => void fix.refetch()} />;
  if (!vm) return <Skeleton lines={6} />;

  const done = !vm.running;
  const success = done && isFixSuccess(vm.status) && Boolean(vm.winning);
  const failed = done && !success && vm.status !== "cancelled";
  const saved = fix.data?.provenance.origin === "snapshot";
  const cost = job?.cost?.cost_usd ?? fix.data?.cost_usd;
  const suggestion = fix.data?.suggestion_md ?? (files.length === 1 ? toSuggestion(files[0]?.patch) : null);
  const attempts = fix.data?.iterations ?? vm.branches.reduce((n, b) => n + b.steps.filter((s) => s.kind === "plan" || s.kind === "repair").length, 0);

  return (
    <section className="space-y-4" aria-labelledby="fix-title">
      <div className="flex flex-wrap items-start gap-2">
        <Button size="sm" variant="ghost" icon={ArrowLeft} onClick={onBack}>
          {t("fix.back")}
        </Button>
        <div className="min-w-0 flex-[1_1_16rem]">
          <h2 id="fix-title" className="text-lg font-semibold k-anywhere">
            {title ? t("fix.titleWith", { title }) : t("fix.title")}
          </h2>
          <p className="flex flex-wrap items-center gap-x-2 text-sm text-muted">
            {vm.provider ? <span>{t("fix.sandbox", { provider: vm.provider })}</span> : null}
            {cost !== undefined ? <span className="tabular">{done ? t("fix.cost", { amount: formatMoney(cost) }) : t("job.costSoFar", { amount: formatMoney(cost) })}</span> : null}
            {fix.data ? <ProvenanceBadge provenance={fix.data.provenance} compact /> : null}
            {saved ? <Badge tone="neutral">{t("common.saved_run")}</Badge> : null}
          </p>
        </div>
        {!done && liveJobId ? (
          <Button size="sm" onClick={() => void cancelJob(liveJobId)}>
            {t("common.cancel")}
          </Button>
        ) : null}
      </div>

      {fix.data?.isolation || fix.data?.provider_reason ? (
        <p className="flex items-start gap-2 rounded-md bg-surface-2 p-2.5 text-sm text-muted">
          <ShieldCheck className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            {fix.data?.isolation ? t("fix.isolation", { isolation: fix.data.isolation }) : null} {fix.data?.provider_reason ?? ""}
          </span>
        </p>
      ) : null}

      <div aria-live="polite">
        <FixTimeline vm={vm} />
      </div>

      {failed ? (
        <div className="space-y-2 rounded-md border border-danger/40 bg-danger-bg p-3">
          <p className="text-sm font-medium text-danger-fg">{t("fix.failed", { n: attempts })}</p>
          {vm.error ? <p className="text-sm text-danger-fg">{vm.error}</p> : null}
          <TextArea label={t("fix.hint")} hint={t("fix.hintHelp")} value={hint} onChange={(e) => setHint(e.target.value)} rows={2} />
          <Button icon={RotateCcw} disabled={Boolean(gate) || findingIds.length === 0} title={gate} loading={retry.pending} onClick={() => void retry.run(hint)}>
            {t("fix.tryAgain")}
          </Button>
          {retry.keyRequired ? <KeyRequired what={t("fix.needsKey")} provider={status.data?.provider ?? ""} envVar={envVar} /> : null}
          {retry.error ? <InlineError error={retry.error} /> : null}
        </div>
      ) : null}

      {success && fix.data ? (
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Button
              variant="primary"
              icon={Download}
              onClick={() => downloadWithHeaders(urls.fixPatch(fix.data!.id), `fix-${number}.patch`).catch((e) => toast({ tone: "danger", title: errorMessage(e) }))}
            >
              {t("fix.download")}
            </Button>
            {suggestion ? (
              <Button
                icon={ClipboardCopy}
                onClick={async () => {
                  if (await copyText(suggestion)) toast({ tone: "success", title: t("fix.suggestionCopied") });
                }}
              >
                {t("fix.copySuggestion")}
              </Button>
            ) : null}
            <Button
              icon={FilePlus2}
              disabled={Boolean(draftGate(gate))}
              onClick={async () => {
                try {
                  await appendDraft(draft, suggestion ?? t("fix.draftNote", { branch: fix.data?.winning_branch ?? "" }));
                  toast({ tone: "success", title: t("fix.addedToDraft") });
                } catch {
                  toast({ tone: "danger", title: t("errors.unknown") });
                }
              }}
            >
              {t("draft.addFix")}
            </Button>
          </div>
          <h3 className="text-base font-semibold">{t("fix.winningDiff", { branch: fix.data.winning_branch ?? "" })}</h3>
          <DiffView files={files} />
        </div>
      ) : null}
    </section>
  );
}

/** Adding to the draft needs the maintainer role but not a key. */
function draftGate(gate: string | undefined): string | undefined {
  return gate === t("common.needsKey") ? undefined : gate;
}
