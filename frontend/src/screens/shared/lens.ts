import { useSearchParams } from "react-router";
import { useLens, useLenses } from "@/api/hooks/lens";
import { useProject } from "@/api/hooks/system";
import { useViewer } from "@/state/role";
import type { LensSummary } from "@/api/types";

/**
 * Which lens to show: ?person= first, then the viewer's own lens, then the project's primary maintainer,
 * then any maintainer, then the first lens.
 */
export function pickLens(items: LensSummary[], personParam: string | null, viewerId: string | null, maintainerId: string | undefined): LensSummary | undefined {
  return (
    items.find((l) => l.person.id === personParam) ??
    items.find((l) => l.person.id === viewerId) ??
    items.find((l) => l.person.id === maintainerId) ??
    items.find((l) => (l.person.role ?? "").includes("maintainer")) ??
    items[0]
  );
}

export function useActiveLens(pid: string | undefined) {
  const [params] = useSearchParams();
  const lenses = useLenses(pid);
  const project = useProject(pid);
  const viewer = useViewer();
  const summary = pickLens(lenses.data?.items ?? [], params.get("person"), viewer.personId, project.data?.primary_maintainer?.id);
  const overview = useLens(summary?.id);
  return { summary, overview, lenses, project };
}

/** The primary maintainer's display name, used in copy ("{name}'s lens"). */
export function maintainerName(p: { display_name?: string | null; login: string } | null | undefined, fallback: string): string {
  return p?.display_name || p?.login || fallback;
}
