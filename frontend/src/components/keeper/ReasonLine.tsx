import type { Reason, SignalRef } from "@/api/types";
import { Popover } from "@/components/ui/Popover";
import { Tooltip } from "@/components/ui/Tooltip";
import { Pill } from "@/components/ui/Badge";
import { t } from "@/copy/t";
import { AlertTriangle } from "lucide-react";

/** The top reason in plain words, with a quote from the evidence when there is one; "+2 more" popover. */
export function ReasonLine({ reasons }: { reasons: Reason[] }) {
  const [first, ...rest] = reasons;
  if (!first) return null;
  return (
    <span className="inline-flex min-w-0 flex-wrap items-baseline gap-x-1.5">
      <span className="min-w-0 k-anywhere">
        {first.label}
        {first.detail ? <q className="ml-1 text-muted">{first.detail}</q> : null}
      </span>
      {rest.length > 0 ? (
        <Popover
          trigger={
            <button type="button" className="text-xs font-medium text-primary underline-offset-2 hover:underline">
              {t("common.moreCount", { n: rest.length })}
            </button>
          }
        >
          <ul className="space-y-2 text-sm">
            {reasons.map((r, i) => (
              <li key={i}>
                <p className="font-medium">{r.label}</p>
                {r.detail ? <p className="text-muted">{r.detail}</p> : null}
              </li>
            ))}
          </ul>
        </Popover>
      ) : null}
    </span>
  );
}

/** Risk signals ("New dependency"), with tooltips explaining why each raises attention. */
export function SignalChips({ signals, limit }: { signals: SignalRef[]; limit?: number }) {
  if (!signals.length) return null;
  const shown = limit ? signals.slice(0, limit) : signals;
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label={t("pr.signals.label")}>
      {shown.map((s) => {
        const tip = [s.evidence?.join(" · "), s.paths?.length ? t("pr.signals.paths", { paths: s.paths.slice(0, 4).join(", ") }) : null, s.covered ? t("pr.signals.covered") : null]
          .filter(Boolean)
          .join(" — ");
        return (
          <li key={s.key}>
            <Tooltip content={tip || t("pr.signals.why")}>
              <span tabIndex={0}>
                <Pill tone={s.covered ? "neutral" : "unknown"} icon={s.covered ? undefined : AlertTriangle}>
                  {s.label}
                </Pill>
              </span>
            </Tooltip>
          </li>
        );
      })}
      {limit && signals.length > limit ? <li className="text-xs text-muted">{t("common.moreCount", { n: signals.length - limit })}</li> : null}
    </ul>
  );
}
