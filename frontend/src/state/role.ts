import { createStore, useStore } from "@/lib/store";
import { readLocal, writeLocal } from "@/lib/storage";
import { setViewer, type ViewerRole } from "@/api/headers";
import { queryClient } from "@/api/queryClient";

/**
 * The role picker ("Viewing as"). `personId` null means "Me (judge)": X-Keeper-Role judge and no
 * X-Keeper-Person header. `chosen` is false until the user picks someone, so the first load can default
 * to the project's primary maintainer.
 */
export interface Viewer {
  personId: string | null;
  role: ViewerRole;
  chosen: boolean;
}

const KEY = "keeper.viewer.v1";
const initial = readLocal<Viewer>(KEY, { personId: null, role: "judge", chosen: false });
setViewer(initial.role, initial.personId);

export const viewerStore = createStore<Viewer>(initial, (v) => {
  setViewer(v.role, v.personId);
  writeLocal(KEY, v);
  // Responses can depend on the viewer (second-person lens card, permissions), so refetch what is on screen.
  void queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "status" });
});

export function useViewer(): Viewer {
  return useStore(viewerStore);
}

/** Maps a person's project role to the X-Keeper-Role vocabulary. */
export function toViewerRole(role: string | null | undefined): ViewerRole {
  const r = (role ?? "").toLowerCase();
  if (r.includes("maintainer") || r === "owner") return "maintainer";
  if (r.includes("contributor") || r.includes("learner")) return "contributor";
  if (r === "judge") return "judge";
  return "reviewer";
}

export function chooseViewer(personId: string | null, role: string | null | undefined): void {
  viewerStore.set({ personId, role: personId ? toViewerRole(role) : "judge", chosen: true });
}
