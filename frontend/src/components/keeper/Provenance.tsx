import { Clock, FlaskConical, Radio } from "lucide-react";
import type { Provenance } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Tooltip } from "@/components/ui/Tooltip";
import { t } from "@/copy/t";
import { formatDate, formatDateTime, formatRelative } from "@/lib/format";

/**
 * "Live" or "Saved run · {date}". When provenance.simulated is true the result came from Keeper's offline
 * simulator, so the badge says so and never names a model run.
 */
export function ProvenanceBadge({ provenance, compact }: { provenance: Provenance | null | undefined; compact?: boolean }) {
  if (!provenance) return null;
  const simulated = Boolean(provenance.simulated);
  const at = provenance.computed_at;
  const models = (provenance.model_displays ?? []).filter(Boolean);
  if (provenance.origin === "snapshot" || simulated) {
    const label = simulated
      ? at
        ? t("provenance.savedSimulatedOn", { date: formatDate(at) })
        : t("provenance.savedSimulated")
      : at
        ? t("provenance.savedOn", { date: formatDate(at) })
        : t("common.saved_run");
    const tip = simulated ? t("provenance.simulatedTip") : models.length ? t("provenance.savedTip", { models: models.join(", "), date: formatDateTime(at) }) : t("provenance.savedTipNoModels", { date: formatDateTime(at) });
    return (
      <Tooltip content={tip}>
        <span tabIndex={0} className="inline-flex">
          <Badge tone={simulated ? "warning" : "neutral"} icon={simulated ? FlaskConical : Clock}>
            {compact && !simulated ? t("common.saved_run") : label}
          </Badge>
        </span>
      </Tooltip>
    );
  }
  return (
    <Tooltip content={models.length ? t("provenance.liveTip", { models: models.join(", ") }) : undefined}>
      <span tabIndex={0} className="inline-flex">
        <Badge tone="success" icon={Radio}>
          {at && !compact ? t("provenance.liveAt", { when: formatRelative(at) }) : t("common.live")}
        </Badge>
      </span>
    </Tooltip>
  );
}
