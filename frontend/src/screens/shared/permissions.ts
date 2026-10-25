import { useStatus } from "@/api/hooks/system";
import { useViewer } from "@/state/role";
import { t } from "@/copy/t";

/** The reason an action is disabled because the spending cap is reached (all reading still works). */
export function useCapReason(): string | undefined {
  const status = useStatus();
  return status.data?.spend.reached ? t("common.capReached") : undefined;
}

export interface Gate {
  /** Needs a live model (an API key). */
  live?: boolean;
  /** Needs X-Keeper-Role maintainer. */
  maintainer?: boolean;
  /** Needs the viewer to be this person (lens owner). */
  ownerId?: string | null;
}

/** Returns the tooltip text explaining why an action is disabled, or undefined when it is allowed. */
export function useGate(gate: Gate): string | undefined {
  const status = useStatus();
  const viewer = useViewer();
  if (status.data?.spend.reached && gate.live) return t("common.capReached");
  if (gate.live && status.data && !status.data.live) return t("common.needsKey");
  if (gate.ownerId !== undefined && gate.ownerId !== null && viewer.personId !== gate.ownerId) return t("common.onlyOwner");
  if (gate.maintainer && viewer.role !== "maintainer") return t("common.onlyMaintainer");
  return undefined;
}
