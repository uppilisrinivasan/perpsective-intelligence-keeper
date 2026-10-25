import type { ReactNode } from "react";
import { useGlossary } from "@/api/hooks/system";
import { Tooltip } from "./Tooltip";

/** A glossary term: dotted underline + tooltip from GET /glossary. Renders plain text if the term is unknown. */
export function Term({ term, children }: { term: string; children?: ReactNode }) {
  const g = useGlossary();
  const entry = g.data?.terms.find((x) => x.key === term);
  const label = children ?? entry?.label ?? null;
  if (!entry) return <>{label}</>;
  return (
    <Tooltip
      content={
        <span className="block">
          <span className="block font-semibold">{entry.label}</span>
          <span className="block">{entry.short}</span>
        </span>
      }
    >
      <span tabIndex={0} className="k-term">
        {label}
      </span>
    </Tooltip>
  );
}
