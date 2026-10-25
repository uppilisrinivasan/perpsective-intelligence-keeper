import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, call } from "../client";
import { keys } from "../keys";
import { pullQueries } from "./pull";

export type QueueSort = "attention" | "updated" | "number";

export function useQueue(pid: string | undefined, sort: QueueSort) {
  return useQuery({
    queryKey: keys.queue(pid ?? "", sort),
    queryFn: () => call(api.GET("/api/v1/projects/{pid}/queue", { params: { path: { pid: pid! }, query: { sort } } })),
    enabled: Boolean(pid),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });
}

export function useQueueDigest(pid: string | undefined) {
  return useQuery({
    queryKey: keys.digest(pid ?? ""),
    queryFn: () => call(api.GET("/api/v1/projects/{pid}/queue/digest", { params: { path: { pid: pid! } } })),
    enabled: Boolean(pid),
  });
}

/** Prefetch on queue-row hover and focus. */
export function usePrefetchPull(pid: string | undefined) {
  const qc = useQueryClient();
  return (n: number) => {
    if (!pid) return;
    const q = pullQueries(pid, n);
    void qc.prefetchQuery(q.detail);
    void qc.prefetchQuery(q.analysis);
  };
}

export function startRefresh(pid: string, confirm_token?: string, numbers?: number[]) {
  return call(
    api.POST("/api/v1/projects/{pid}/queue/refresh", {
      params: { path: { pid } },
      body: { confirm_token: confirm_token ?? null, numbers: numbers ?? null },
    }),
  );
}
