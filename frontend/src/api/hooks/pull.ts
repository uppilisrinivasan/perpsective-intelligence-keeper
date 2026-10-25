import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, call } from "../client";
import { keys } from "../keys";
import type { AnalysisResponse, FeedbackRequest, RoutedFinding } from "../types";

export function pullQueries(pid: string, n: number) {
  const path = { pid, n };
  return {
    detail: {
      queryKey: keys.pullPart(pid, n, "detail"),
      queryFn: () => call(api.GET("/api/v1/projects/{pid}/pulls/{n}", { params: { path } })),
      staleTime: 60_000,
    },
    analysis: {
      queryKey: keys.pullPart(pid, n, "analysis"),
      queryFn: () => call(api.GET("/api/v1/projects/{pid}/pulls/{n}/analysis", { params: { path } })),
      staleTime: 30_000,
    },
  };
}

export function usePull(pid: string | undefined, n: number) {
  return useQuery({ ...pullQueries(pid ?? "", n).detail, enabled: Boolean(pid) && n > 0 });
}

export function useAnalysis(pid: string | undefined, n: number) {
  return useQuery({ ...pullQueries(pid ?? "", n).analysis, enabled: Boolean(pid) && n > 0 });
}

export function useDiff(pid: string | undefined, n: number, file?: string) {
  return useQuery({
    queryKey: keys.pullPart(pid ?? "", n, "diff", file ?? null),
    queryFn: () =>
      call(api.GET("/api/v1/projects/{pid}/pulls/{n}/diff", { params: { path: { pid: pid!, n }, query: file ? { file } : {} } })),
    enabled: Boolean(pid) && n > 0,
    staleTime: 5 * 60_000,
  });
}

export function useCompare(pid: string | undefined, n: number, enabled = true) {
  return useQuery({
    queryKey: keys.pullPart(pid ?? "", n, "compare"),
    queryFn: () => call(api.GET("/api/v1/projects/{pid}/pulls/{n}/compare", { params: { path: { pid: pid!, n } } })),
    enabled: Boolean(pid) && n > 0 && enabled,
  });
}

export function useHumanReview(pid: string | undefined, n: number, enabled: boolean) {
  return useQuery({
    queryKey: keys.pullPart(pid ?? "", n, "human"),
    queryFn: () => call(api.GET("/api/v1/projects/{pid}/pulls/{n}/human-review", { params: { path: { pid: pid!, n } } })),
    enabled: Boolean(pid) && n > 0 && enabled,
    retry: false,
  });
}

export function useReviewDraft(pid: string | undefined, n: number) {
  return useQuery({
    queryKey: keys.pullPart(pid ?? "", n, "draft"),
    queryFn: () => call(api.GET("/api/v1/projects/{pid}/pulls/{n}/review-draft", { params: { path: { pid: pid!, n } } })),
    enabled: Boolean(pid) && n > 0,
    retry: false,
  });
}

export function useHandoff(pid: string | undefined, n: number, enabled: boolean) {
  return useQuery({
    queryKey: keys.pullPart(pid ?? "", n, "handoff"),
    queryFn: () => call(api.GET("/api/v1/projects/{pid}/pulls/{n}/handoff", { params: { path: { pid: pid!, n } } })),
    enabled: Boolean(pid) && n > 0 && enabled,
    retry: false,
  });
}

export function useFixes(pid: string | undefined, n: number) {
  return useQuery({
    queryKey: keys.pullPart(pid ?? "", n, "fixes"),
    queryFn: () => call(api.GET("/api/v1/projects/{pid}/pulls/{n}/fixes", { params: { path: { pid: pid!, n } } })),
    enabled: Boolean(pid) && n > 0,
  });
}

export function useFix(fixId: string | undefined) {
  return useQuery({
    queryKey: keys.fix(fixId ?? ""),
    queryFn: () => call(api.GET("/api/v1/fixes/{fix_id}", { params: { path: { fix_id: fixId! } } })),
    enabled: Boolean(fixId),
  });
}

/** Feedback on a finding with an optimistic update and rollback (05-api/04 §4). */
export function useFindingFeedback(pid: string | undefined, n: number) {
  const qc = useQueryClient();
  const key = keys.pullPart(pid ?? "", n, "analysis");
  return useMutation({
    mutationFn: (v: { id: string; body: FeedbackRequest }) =>
      call(api.PATCH("/api/v1/projects/{pid}/findings/{rf_id}", { params: { path: { pid: pid!, rf_id: v.id } }, body: v.body })),
    onMutate: async (v) => {
      await qc.cancelQueries({ queryKey: key });
      const prev = qc.getQueryData<AnalysisResponse>(key);
      if (prev) {
        qc.setQueryData<AnalysisResponse>(key, {
          ...prev,
          findings: prev.findings.map((f) =>
            f.id === v.id
              ? { ...f, user_state: v.body.state, user_text: v.body.text ?? f.user_text, user_severity: v.body.severity ?? f.user_severity }
              : f,
          ),
        });
      }
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(key, ctx.prev);
    },
    onSuccess: (finding: RoutedFinding) => {
      const prev = qc.getQueryData<AnalysisResponse>(key);
      if (prev) qc.setQueryData<AnalysisResponse>(key, { ...prev, findings: prev.findings.map((f) => (f.id === finding.id ? finding : f)) });
      void qc.invalidateQueries({ queryKey: keys.pullPart(pid ?? "", n, "draft") });
    },
  });
}

export function startAnalysis(pid: string, n: number, confirm_token?: string) {
  return call(api.POST("/api/v1/projects/{pid}/pulls/{n}/analysis", { params: { path: { pid, n } }, body: { confirm_token: confirm_token ?? null } }));
}

export function startFix(pid: string, n: number, finding_ids: string[], user_hint?: string, confirm_token?: string) {
  return call(
    api.POST("/api/v1/projects/{pid}/pulls/{n}/fixes", {
      params: { path: { pid, n } },
      body: { finding_ids, both_ways: false, user_hint: user_hint || null, confirm_token: confirm_token ?? null },
    }),
  );
}

export function startHandoff(pid: string, n: number, confirm_token?: string) {
  return call(api.POST("/api/v1/projects/{pid}/pulls/{n}/handoff", { params: { path: { pid, n } }, body: { confirm_token: confirm_token ?? null } }));
}
