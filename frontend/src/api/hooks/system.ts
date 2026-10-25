import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router";
import { api, call } from "../client";
import { keys } from "../keys";
import { setAuthMode } from "../headers";
import { setDemoNow } from "@/lib/format";
import type { Status } from "../types";

/** /status is polled every 60 s (docs/05-api/04 §3); it drives the badge, banners and disabled states. */
const STATUS_POLL_MS = 60_000;

export function useStatus() {
  return useQuery({
    queryKey: keys.status(),
    queryFn: async () => {
      const s = await call(api.GET("/api/v1/status"));
      setAuthMode(s.auth_mode);
      setDemoNow(s.mode === "demo" ? s.demo_now : null);
      return s;
    },
    refetchInterval: (q) => (q.state.data?.data.loading ? 3_000 : STATUS_POLL_MS),
    staleTime: 10_000,
    retry: 1,
  });
}

/** True when results come from Keeper's offline simulator rather than a model run. */
export function isSimulated(status: Status | undefined): boolean {
  return Boolean(status?.simulated || status?.data.snapshot_simulated);
}

export function useProjectId(): string | undefined {
  const [params] = useSearchParams();
  const status = useStatus();
  return params.get("project") ?? status.data?.default_project_id ?? undefined;
}

export function useSession(enabled: boolean) {
  return useQuery({
    queryKey: keys.session(),
    queryFn: () => call(api.GET("/api/v1/auth/session")),
    enabled,
    staleTime: 60_000,
  });
}

export function useTourSteps(enabled = true) {
  return useQuery({
    queryKey: keys.tour(),
    queryFn: () => call(api.GET("/api/v1/tour")),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useGlossary() {
  return useQuery({
    queryKey: keys.glossary(),
    queryFn: () => call(api.GET("/api/v1/glossary")),
    staleTime: Infinity,
  });
}

export function useProjects() {
  return useQuery({ queryKey: keys.projects(), queryFn: () => call(api.GET("/api/v1/projects")) });
}

export function useProject(pid: string | undefined) {
  return useQuery({
    queryKey: keys.project(pid ?? ""),
    queryFn: () => call(api.GET("/api/v1/projects/{pid}", { params: { path: { pid: pid! } } })),
    enabled: Boolean(pid),
    staleTime: 5 * 60_000,
  });
}

export function usePeople(pid: string | undefined) {
  return useQuery({
    queryKey: keys.people(pid ?? ""),
    queryFn: () => call(api.GET("/api/v1/projects/{pid}/people", { params: { path: { pid: pid! } } })),
    enabled: Boolean(pid),
    staleTime: 5 * 60_000,
  });
}

export function useJobs(running: boolean) {
  return useQuery({
    queryKey: keys.jobs(),
    queryFn: () => call(api.GET("/api/v1/jobs", { params: { query: { limit: 12 } } })),
    refetchInterval: running ? 4_000 : 30_000,
    staleTime: 2_000,
  });
}
