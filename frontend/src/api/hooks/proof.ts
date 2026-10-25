import { useQuery } from "@tanstack/react-query";
import { api, call } from "../client";
import { keys } from "../keys";

export function useFidelityRuns(pid: string | undefined) {
  return useQuery({
    queryKey: keys.fidelityRuns(pid ?? ""),
    queryFn: () => call(api.GET("/api/v1/projects/{pid}/fidelity-runs", { params: { path: { pid: pid! } } })),
    enabled: Boolean(pid),
  });
}

export function useFidelityRun(fid: string | undefined) {
  return useQuery({
    queryKey: keys.fidelityRun(fid ?? ""),
    queryFn: () => call(api.GET("/api/v1/fidelity-runs/{fid}", { params: { path: { fid: fid! } } })),
    enabled: Boolean(fid),
  });
}

export function useFidelityCases(fid: string | undefined, q: string, outcome: string) {
  return useQuery({
    queryKey: keys.fidelityCases(fid ?? "", q, outcome),
    queryFn: () =>
      call(api.GET("/api/v1/fidelity-runs/{fid}/cases", { params: { path: { fid: fid! }, query: { q: q || null, outcome: outcome || null } } })),
    enabled: Boolean(fid),
    placeholderData: (prev) => prev,
  });
}

export function useFidelityCase(fid: string | undefined, n: number | undefined) {
  return useQuery({
    queryKey: keys.fidelityCase(fid ?? "", n ?? 0),
    queryFn: () => call(api.GET("/api/v1/fidelity-runs/{fid}/cases/{n}", { params: { path: { fid: fid!, n: n! } } })),
    enabled: Boolean(fid) && n !== undefined,
  });
}
