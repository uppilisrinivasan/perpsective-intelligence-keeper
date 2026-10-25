import { Link } from "react-router";
import { Activity as ActivityIcon, CheckCircle2, CircleX } from "lucide-react";
import { useJobs } from "@/api/hooks/system";
import { JobProgress, jobTitle } from "@/components/keeper/JobProgress";
import { IconButton } from "@/components/ui/IconButton";
import { Popover } from "@/components/ui/Popover";
import { RelativeTime } from "@/components/ui/Formatted";
import { t } from "@/copy/t";
import { formatMoney } from "@/lib/format";
import { jobHref } from "@/lib/jobLinks";
import { useState } from "react";

const RUNNING = new Set(["queued", "running"]);

/** The count of running jobs; a popover with recent jobs, progress, cost and links. */
export function ActivityButton() {
  const [open, setOpen] = useState(false);
  const jobs = useJobs(true);
  const items = jobs.data?.items ?? [];
  const running = items.filter((j) => RUNNING.has(j.status));
  return (
    <Popover
      open={open}
      onOpenChange={setOpen}
      align="end"
      trigger={<IconButton icon={ActivityIcon} label={running.length ? t("activity.labelRunning", { n: running.length }) : t("activity.label")} badge={running.length || undefined} />}
    >
      <h2 className="mb-2 text-sm font-semibold">{t("activity.title")}</h2>
      {items.length === 0 ? (
        <p className="text-sm text-muted">{t("activity.empty")}</p>
      ) : (
        <ul className="space-y-2">
          {items.map((j) =>
            RUNNING.has(j.status) ? (
              <li key={j.id}>
                <JobProgress jobId={j.id} compact />
              </li>
            ) : (
              <li key={j.id} className="flex items-start gap-2 text-sm">
                {j.status === "failed" ? <CircleX className="mt-0.5 size-4 text-danger" aria-hidden /> : <CheckCircle2 className="mt-0.5 size-4 text-success" aria-hidden />}
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{jobTitle(j.kind)}</p>
                  <p className="text-xs text-muted">
                    <RelativeTime at={j.finished_at ?? j.created_at} /> · {formatMoney(j.cost_usd)}
                  </p>
                </div>
                {jobHref(j.kind, j.params, j.result) ? (
                  <Link to={jobHref(j.kind, j.params, j.result)!} onClick={() => setOpen(false)} className="text-xs font-medium text-primary hover:underline">
                    {t("common.open")}
                  </Link>
                ) : null}
              </li>
            ),
          )}
        </ul>
      )}
    </Popover>
  );
}
