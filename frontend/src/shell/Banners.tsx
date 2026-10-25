import { useState } from "react";
import { AlertTriangle, Ban, FlaskConical, Info, X } from "lucide-react";
import type { Status } from "@/api/types";
import { isSimulated } from "@/api/hooks/system";
import { KeyHowButton } from "@/components/keeper/States";
import { t } from "@/copy/t";
import { cx } from "@/lib/cx";
import { formatDate, formatMoney } from "@/lib/format";
import { readSession, writeSession } from "@/lib/storage";

type BannerKind = "cap" | "nokey" | "fallback" | "sandbox";
const KEY = "keeper.banners.dismissed";

/** At most one banner, by priority: spend cap > no key > model fallback > sandbox fallback. */
export function pickBanner(status: Status, dismissed: string[]): BannerKind | null {
  if (status.spend.reached) return "cap";
  if (!status.live && !dismissed.includes("nokey")) return "nokey";
  if (status.models.some((m) => m.fallback_active) && !dismissed.includes("fallback")) return "fallback";
  if (status.sandbox.requested && status.sandbox.provider !== status.sandbox.requested && !dismissed.includes("sandbox")) return "sandbox";
  return null;
}

export function BannerArea({ status, envVar }: { status: Status; envVar?: string }) {
  const [dismissed, setDismissed] = useState<string[]>(() => readSession<string[]>(KEY, []));
  const kind = pickBanner(status, dismissed);
  if (!kind) return null;
  const dismiss = () => {
    const next = [...dismissed, kind];
    setDismissed(next);
    writeSession(KEY, next);
  };
  const simulated = isSimulated(status);
  const date = formatDate(status.data.snapshot_created_at ?? status.data.loaded_at);
  let tone: string;
  let Icon: typeof Info;
  let text: string;
  let extra = null as React.ReactNode;
  if (kind === "cap") {
    tone = "danger";
    Icon = Ban;
    text = t("banner.cap", { cap: formatMoney(status.spend.cap_usd), period: status.spend.period });
  } else if (kind === "nokey") {
    tone = simulated ? "warning" : "info";
    Icon = simulated ? FlaskConical : Info;
    text = simulated ? t("banner.noKeySimulated", { date, provider: status.provider }) : t("banner.noKey", { date, provider: status.provider });
    extra = <KeyHowButton provider={status.provider} envVar={envVar} />;
  } else if (kind === "fallback") {
    tone = "warning";
    Icon = AlertTriangle;
    const m = status.models.find((x) => x.fallback_active);
    text = t("banner.fallback", { model: m?.display ?? "", fallback: m?.fallback_model ?? "" });
  } else {
    tone = "warning";
    Icon = AlertTriangle;
    text = t("banner.sandbox", { provider: status.sandbox.provider, requested: status.sandbox.requested, reason: status.sandbox.reason ?? "" });
  }
  return (
    <div
      role={kind === "cap" ? "alert" : "status"}
      className={cx(
        "flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b px-(--gutter) py-2 text-sm",
        tone === "danger" ? "border-danger/40 bg-danger-bg text-danger-fg" : tone === "warning" ? "border-warning/40 bg-warning-bg text-warning-fg" : "border-info/30 bg-info-bg text-info-fg",
      )}
    >
      <Icon className="size-4 shrink-0" aria-hidden />
      <p className="min-w-0 flex-[1_1_20rem]">{text}</p>
      {extra}
      {kind !== "cap" ? (
        <button type="button" onClick={dismiss} className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium hover:bg-surface/50">
          <X className="size-3.5" aria-hidden />
          {t("common.dismiss")}
        </button>
      ) : null}
    </div>
  );
}
