import { useQuery } from "@tanstack/react-query";
import { api, call } from "../client";
import { keys } from "../keys";

export function useLenses(pid: string | undefined) {
  return useQuery({
    queryKey: keys.lenses(pid ?? ""),
    queryFn: () => call(api.GET("/api/v1/projects/{pid}/lenses", { params: { path: { pid: pid! } } })),
    enabled: Boolean(pid),
  });
}

export function useLens(lid: string | undefined) {
  return useQuery({
    queryKey: keys.lens(lid ?? ""),
    queryFn: () => call(api.GET("/api/v1/lenses/{lid}", { params: { path: { lid: lid! } } })),
    enabled: Boolean(lid),
  });
}

export function useLensVersion(lid: string | undefined, v: number | undefined) {
  return useQuery({
    queryKey: keys.lensPart(lid ?? "", "version", v),
    queryFn: () => call(api.GET("/api/v1/lenses/{lid}/versions/{v}", { params: { path: { lid: lid!, v: v! } } })),
    enabled: Boolean(lid) && v !== undefined,
  });
}

export interface ItemFilters {
  type?: string;
  category?: string;
  status?: string;
  q?: string;
}

export function useLensItems(lid: string | undefined, v: number | undefined, f: ItemFilters = {}) {
  return useQuery({
    queryKey: keys.lensPart(lid ?? "", "items", { v, ...f }),
    queryFn: () =>
      call(
        api.GET("/api/v1/lenses/{lid}/versions/{v}/items", {
          params: {
            path: { lid: lid!, v: v! },
            query: { type: f.type || null, category: f.category || null, status: f.status || null, q: f.q || null },
          },
        }),
      ),
    enabled: Boolean(lid) && v !== undefined,
    placeholderData: (prev) => prev,
  });
}

export function useLensItem(id: string | undefined) {
  return useQuery({
    queryKey: keys.lensItem(id ?? ""),
    queryFn: () => call(api.GET("/api/v1/lens-items/{item_id}", { params: { path: { item_id: id! } } })),
    enabled: Boolean(id),
  });
}

export function useLensDiff(lid: string | undefined, from: number | undefined, to: number | undefined) {
  return useQuery({
    queryKey: keys.lensPart(lid ?? "", "diff", { from, to }),
    queryFn: () => call(api.GET("/api/v1/lenses/{lid}/diff", { params: { path: { lid: lid! }, query: { from: from!, to: to! } } })),
    enabled: Boolean(lid) && from !== undefined && to !== undefined && from !== to,
  });
}

export function useEdgeMap(lid: string | undefined, version: number | undefined) {
  return useQuery({
    queryKey: keys.lensPart(lid ?? "", "edge-map", version),
    queryFn: () =>
      call(api.GET("/api/v1/lenses/{lid}/edge-map", { params: { path: { lid: lid! }, query: version !== undefined ? { version } : {} } })),
    enabled: Boolean(lid),
  });
}

export function useGrowth(lid: string | undefined) {
  return useQuery({
    queryKey: keys.lensPart(lid ?? "", "growth"),
    queryFn: () => call(api.GET("/api/v1/lenses/{lid}/growth", { params: { path: { lid: lid! } } })),
    enabled: Boolean(lid),
  });
}

export function useLensAudit(lid: string | undefined) {
  return useQuery({
    queryKey: keys.lensPart(lid ?? "", "audit"),
    queryFn: () => call(api.GET("/api/v1/lenses/{lid}/audit", { params: { path: { lid: lid! } } })),
    enabled: Boolean(lid),
  });
}

export function useLensBias(lid: string | undefined) {
  return useQuery({
    queryKey: keys.lensPart(lid ?? "", "bias"),
    queryFn: () => call(api.GET("/api/v1/lenses/{lid}/bias", { params: { path: { lid: lid! } } })),
    enabled: Boolean(lid),
  });
}
