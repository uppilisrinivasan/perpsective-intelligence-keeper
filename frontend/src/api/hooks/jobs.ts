import { useCallback, useSyncExternalStore } from "react";
import { getJobState, subscribeJob, type JobState } from "../jobs";

const noop = () => () => undefined;
const none = () => null;

/** Live state of one job: steps, progress, cost, result or error. Shares one EventSource per job. */
export function useJob(id: string | null | undefined): JobState | null {
  const subscribe = useCallback((l: () => void) => (id ? subscribeJob(id, l) : noop()), [id]);
  const get = useCallback(() => (id ? getJobState(id) : null), [id]);
  return useSyncExternalStore(id ? subscribe : noop, id ? get : none, id ? get : none);
}
