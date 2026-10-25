import { Link } from "react-router";
import { Activity } from "lucide-react";
import { badgeClass, type Tone } from "@/components/ui/Badge";
import { Tooltip } from "@/components/ui/Tooltip";
import { tDynamic } from "@/copy/t";

const TONES: Record<string, Tone> = {
  healthy: "success",
  absorbed: "warning",
  self_caricature: "warning",
  deskilling: "danger",
  replaced: "info",
  insufficient_data: "neutral",
};

export function healthLabel(state: string | null | undefined): string {
  return tDynamic(`health.${state ?? "insufficient_data"}.label`, undefined, "health.insufficient_data.label");
}

/** The health state with its plain sentence in a tooltip; links to Growth. */
export function HealthBadge({ state, href }: { state: string | null | undefined; href?: string }) {
  const key = state ?? "insufficient_data";
  const sentence = tDynamic(`health.${key}.sentence`);
  const cls = badgeClass(TONES[key] ?? "neutral", "md");
  const body = (
    <>
      <Activity className="size-[1em]" aria-hidden strokeWidth={1.75} />
      {healthLabel(key)}
    </>
  );
  return (
    <Tooltip content={sentence}>
      {href ? (
        <Link to={href} className={cls}>
          {body}
        </Link>
      ) : (
        <span tabIndex={0} className={cls}>
          {body}
        </span>
      )}
    </Tooltip>
  );
}
