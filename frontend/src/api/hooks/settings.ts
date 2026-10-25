import { useQuery } from "@tanstack/react-query";
import { api, call } from "../client";
import { keys } from "../keys";

export function useSettings() {
  return useQuery({ queryKey: keys.settings(), queryFn: () => call(api.GET("/api/v1/settings")), staleTime: 60_000 });
}

export type UsagePeriod = "day" | "month" | "total";
export type UsageGroup = "model" | "feature" | "day";

export function useUsage(period: UsagePeriod, group_by: UsageGroup) {
  return useQuery({
    queryKey: keys.usage(period, group_by),
    queryFn: () => call(api.GET("/api/v1/usage", { params: { query: { period, group_by } } })),
  });
}

/** PATCH /settings takes {key: value}; the generated body type is an empty record, so it is widened here. */
export function patchSettings(values: Record<string, unknown>) {
  return call(api.PATCH("/api/v1/settings", { body: values as Record<string, never> }));
}

export function resetSettings(keysToReset: string[]) {
  return call(api.POST("/api/v1/settings/reset", { body: { keys: keysToReset } as unknown as Record<string, never> }));
}
