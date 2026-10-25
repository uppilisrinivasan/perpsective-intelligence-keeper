import { queryClient } from "./queryClient";

/** Cache invalidation when a job completes (docs/05-api/04-frontend-integration.md §4). */
const FAMILIES: Record<string, string[]> = {
  triage: ["queue", "pull"],
  analyze: ["queue", "pull"],
  fix: ["pull", "fix", "queue"],
  handoff: ["pull", "queue"],
  learn: ["lens", "queue", "tour"],
  lens_update: ["lens", "queue", "tour"],
  recalibrate: ["lens", "queue", "tour"],
  fidelity: ["fidelity", "tour"],
  practice_score: ["practice"],
  import: ["projects", "status", "people"],
  probe: ["status", "settings"],
  sandbox_check: ["status", "settings"],
  reset_saved: ["status", "queue", "pull", "lens", "fidelity", "practice", "chat", "tour", "usage"],
  load_demo: ["status", "projects", "people", "queue", "pull", "lens", "fidelity", "practice", "chat", "tour"],
};

export function invalidateForJob(kind: string | undefined): void {
  const families = (kind && FAMILIES[kind]) || ["queue", "status"];
  for (const f of new Set([...families, "jobs", "usage"])) {
    void queryClient.invalidateQueries({ queryKey: [f] });
  }
}
