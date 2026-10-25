import { useQuery } from "@tanstack/react-query";
import { api, call } from "../client";
import { keys } from "../keys";

export function usePracticeOverview(pid: string | undefined, learner: string) {
  return useQuery({
    queryKey: keys.practiceOverview(pid ?? "", learner),
    queryFn: () => call(api.GET("/api/v1/projects/{pid}/practice/overview", { params: { path: { pid: pid! }, query: { learner } } })),
    enabled: Boolean(pid),
  });
}

export function usePracticeSession(sid: string | undefined) {
  return useQuery({
    queryKey: keys.practiceSession(sid ?? ""),
    queryFn: () => call(api.GET("/api/v1/practice/sessions/{sid}", { params: { path: { sid: sid! } } })),
    enabled: Boolean(sid),
  });
}

export function usePracticeItem(sid: string | undefined, n: number) {
  return useQuery({
    queryKey: keys.practiceItem(sid ?? "", n),
    queryFn: () => call(api.GET("/api/v1/practice/sessions/{sid}/items/{n}", { params: { path: { sid: sid!, n } } })),
    enabled: Boolean(sid) && n >= 0,
  });
}

const PENDING = new Set(["pending", "scoring", "queued", "running"]);

export function usePracticeFeedback(sid: string | undefined, n: number, enabled: boolean) {
  return useQuery({
    queryKey: keys.practiceFeedback(sid ?? "", n),
    queryFn: () => call(api.GET("/api/v1/practice/sessions/{sid}/items/{n}/feedback", { params: { path: { sid: sid!, n } } })),
    enabled: Boolean(sid) && enabled,
    retry: false,
    refetchInterval: (q) => (q.state.data && PENDING.has(q.state.data.status) ? 2_000 : false),
  });
}

export function isFeedbackPending(status: string | undefined): boolean {
  return status !== undefined && PENDING.has(status);
}
