import { FlaskConical } from "lucide-react";
import type { Status } from "@/api/types";
import { isSimulated } from "@/api/hooks/system";
import { Popover } from "@/components/ui/Popover";
import { KeyHowTo } from "@/components/keeper/States";
import { t } from "@/copy/t";
import { cx } from "@/lib/cx";
import { formatDate } from "@/lib/format";

/** "Live" (green dot) when the key is configured and the probe is OK; "Saved results" otherwise, with a popover. */
export function ModeBadge({ status, envVar }: { status: Status; envVar?: string }) {
  const simulated = isSimulated(status);
  const probeOk = status.models.every((m) => (m.probe.exists ?? "ok") !== "fail");
  const live = status.live && probeOk;
  const label = live ? t("mode.live") : simulated ? t("mode.savedSimulated") : t("mode.saved");
  return (
    <Popover
      align="end"
      trigger={
        <button
          type="button"
          className={cx(
            "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap",
            live ? "border-success/50 bg-success-bg text-success-fg" : simulated ? "border-warning/50 bg-warning-bg text-warning-fg" : "border-border bg-surface-2 text-muted",
          )}
          aria-label={t("mode.aria", { label })}
        >
          {simulated && !live ? <FlaskConical className="size-3" aria-hidden /> : <span className={cx("size-2 rounded-full", live ? "bg-success" : "bg-baseline-solid")} aria-hidden />}
          <span className="max-sm:sr-only">{label}</span>
        </button>
      }
    >
      {live ? (
        <div className="space-y-2 text-sm">
          <p className="font-medium">{t("mode.livePop.title")}</p>
          <ul className="space-y-0.5 text-muted">
            {status.models.map((m) => (
              <li key={m.role}>{t("mode.livePop.model", { role: m.purpose || m.role, model: m.display })}</li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="space-y-2 text-sm">
          <p className="font-medium">{simulated ? t("mode.savedPop.titleSimulated") : t("mode.savedPop.title")}</p>
          <p className="text-muted">
            {simulated
              ? t("mode.savedPop.simulated", { date: formatDate(status.data.snapshot_created_at) })
              : t("mode.savedPop.body", { date: formatDate(status.data.snapshot_created_at) })}
          </p>
          <p className="text-muted">{t("mode.savedPop.works")}</p>
          {status.reason_if_not_live ? <p className="text-xs text-muted">{status.reason_if_not_live}</p> : null}
          <p className="pt-1 font-medium">{t("key.how.title", { provider: status.provider })}</p>
          <KeyHowTo provider={status.provider} envVar={envVar} />
        </div>
      )}
    </Popover>
  );
}
