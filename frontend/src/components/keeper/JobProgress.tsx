import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, CircleX, WifiOff } from "lucide-react";
import { useJob } from "@/api/hooks/jobs";
import { cancelJob, type JobState } from "@/api/jobs";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { t, tDynamic } from "@/copy/t";
import { cx } from "@/lib/cx";
import { formatDurationMs, formatMoney } from "@/lib/format";

export function jobTitle(kind: string | undefined): string {
  return tDynamic(`job.kind.${kind ?? ""}`, undefined, "job.kind.generic");
}

export function ProgressBar({ value, label, tone = "primary" }: { value: number; label: string; tone?: "primary" | "warning" | "danger" | "success" }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  const color = tone === "primary" ? "bg-primary" : tone === "warning" ? "bg-warning" : tone === "danger" ? "bg-danger" : "bg-success";
  return (
    <div role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)} className="h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
      <div className={cx("h-full rounded-full transition-[width] duration-(--dur)", color)} style={{ width: `${pct}%` }} />
    </div>
  );
}

function stepLine(s: JobState): string {
  if (s.step && s.step.total > 0) return t("job.stepOf", { index: s.step.index + 1, total: s.step.total, label: s.step.label });
  if (s.step) return s.step.label;
  if (s.phase === "queued" || s.phase === "connecting") return t("job.waiting");
  return t("job.working");
}

function fraction(s: JobState): number {
  if (s.phase === "completed") return 1;
  if (s.progress && s.progress.total > 0) return s.progress.done / s.progress.total;
  if (s.progress) return s.progress.progress > 1 ? s.progress.progress / 100 : s.progress.progress;
  if (s.step && s.step.total > 0) return s.step.index / s.step.total;
  return 0;
}

/** The current step label, progress, elapsed time, cost so far, Cancel. Announces step changes politely. */
export function JobProgress({ jobId, compact, title, onDone, hideWhenDone }: { jobId: string; compact?: boolean; title?: string; onDone?: (s: JobState) => void; hideWhenDone?: boolean }) {
  const s = useJob(jobId);
  const [elapsed, setElapsed] = useState(0);
  const [cancelling, setCancelling] = useState(false);
  const terminal = s ? ["completed", "failed", "cancelled"].includes(s.phase) : false;

  useEffect(() => {
    if (!s || terminal) return;
    const id = setInterval(() => setElapsed(Date.now() - s.startedAt), 1000);
    return () => clearInterval(id);
  }, [s, terminal]);

  useEffect(() => {
    if (s && terminal) onDone?.(s);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [terminal]);

  if (!s) return null;
  if (terminal && hideWhenDone && s.phase === "completed") return null;
  const heading = title ?? jobTitle(s.kind);
  const line = stepLine(s);

  return (
    <div className={cx("rounded-md border border-border bg-surface", compact ? "p-2.5" : "p-4")} data-job={jobId}>
      <div className="flex items-start gap-2">
        <span className="mt-0.5">
          {s.phase === "completed" ? (
            <CheckCircle2 className="size-4 text-success" aria-hidden />
          ) : s.phase === "failed" ? (
            <CircleX className="size-4 text-danger" aria-hidden />
          ) : s.phase === "cancelled" ? (
            <AlertTriangle className="size-4 text-warning" aria-hidden />
          ) : (
            <Spinner />
          )}
        </span>
        <div className="min-w-0 flex-1">
          <p className={cx("font-medium", compact ? "text-sm" : "text-base")}>{heading}</p>
          <p className="text-sm text-muted" aria-live="polite">
            {s.phase === "completed"
              ? t("job.done")
              : s.phase === "failed"
                ? s.error?.message || t("job.failed")
                : s.phase === "cancelled"
                  ? t("job.cancelled")
                  : line}
          </p>
        </div>
        {!terminal ? (
          <Button
            size="sm"
            variant="ghost"
            loading={cancelling}
            onClick={async () => {
              setCancelling(true);
              try {
                await cancelJob(jobId);
              } finally {
                setCancelling(false);
              }
            }}
          >
            {t("common.cancel")}
          </Button>
        ) : null}
      </div>
      {!terminal ? (
        <div className="mt-2.5 space-y-1.5">
          <ProgressBar value={fraction(s)} label={line} />
          <p className="flex flex-wrap gap-x-3 text-xs text-muted tabular">
            <span>{t("job.elapsed", { time: formatDurationMs(elapsed) })}</span>
            {s.cost ? <span>{t("job.costSoFar", { amount: formatMoney(s.cost.cost_usd) })}</span> : null}
            {s.connectionLost ? (
              <span className="inline-flex items-center gap-1 text-warning-fg">
                <WifiOff className="size-3" aria-hidden />
                {t("job.reconnecting")}
              </span>
            ) : null}
          </p>
          {s.warnings.map((w, i) => (
            <p key={i} className="flex items-center gap-1 text-xs text-warning-fg">
              <AlertTriangle className="size-3" aria-hidden />
              {w.message || tDynamic(`job.warning.${w.code}`)}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}
