import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ConfirmCostDialog, type ConfirmRequest } from "@/components/keeper/ConfirmCostDialog";
import { ApiError } from "../errors";
import { keys } from "../keys";
import { patchSettings, useSettings } from "./settings";
import { useStatus } from "./system";
import { num, obj, str } from "@/lib/unknown";
import { toast } from "@/state/toasts";
import { t } from "@/copy/t";

type ConfirmFn = (req: ConfirmRequest) => Promise<boolean>;
const ConfirmContext = createContext<ConfirmFn | null>(null);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [request, setRequest] = useState<ConfirmRequest | null>(null);
  const resolver = useRef<((ok: boolean) => void) | null>(null);
  const qc = useQueryClient();
  const confirm = useCallback<ConfirmFn>((req) => {
    setRequest(req);
    return new Promise<boolean>((resolve) => {
      resolver.current = resolve;
    });
  }, []);
  const onResolve = (ok: boolean, dontAskBelow?: number) => {
    resolver.current?.(ok);
    resolver.current = null;
    setRequest(null);
    if (ok && dontAskBelow !== undefined) {
      patchSettings({ auto_approve_usd: dontAskBelow })
        .then(() => {
          void qc.invalidateQueries({ queryKey: keys.settings() });
          void qc.invalidateQueries({ queryKey: keys.status() });
        })
        .catch(() => undefined);
    }
  };
  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <ConfirmCostDialog request={request} onResolve={onResolve} />
    </ConfirmContext.Provider>
  );
}

export interface ConfirmMeta {
  title: string;
  description?: string;
  duration?: string;
}

export interface ConfirmableState {
  jobId: string | null;
  pending: boolean;
  error: unknown;
  keyRequired: boolean;
}

/**
 * Runs an action; on 402 confirmation_required opens ConfirmCostDialog with the estimate and resends the same
 * body with confirm_token. Returns the job id from 202 {job}. 402 spend_cap_reached refreshes /status (the
 * banner blocks), 503 no_api_key sets keyRequired, 409 job_in_progress attaches to the existing job.
 */
export function useConfirmableAction<V = void, R = unknown>(
  fn: (vars: V, confirmToken?: string) => Promise<R>,
  meta: ConfirmMeta | ((vars: V) => ConfirmMeta),
  opts: { onSuccess?: (result: R, vars: V) => void; onJob?: (jobId: string, vars: V) => void } = {},
) {
  const confirm = useContext(ConfirmContext);
  const qc = useQueryClient();
  const status = useStatus();
  const settings = useSettings();
  const [state, setState] = useState<ConfirmableState>({ jobId: null, pending: false, error: null, keyRequired: false });

  const handleResult = (result: R, vars: V) => {
    const job = obj(obj(result).job);
    const jobId = str(job.id) ?? null;
    setState({ jobId, pending: false, error: null, keyRequired: false });
    if (jobId) opts.onJob?.(jobId, vars);
    opts.onSuccess?.(result, vars);
    return result;
  };

  const run = async (vars: V): Promise<R | undefined> => {
    setState((s) => ({ ...s, pending: true, error: null, keyRequired: false }));
    try {
      return handleResult(await fn(vars), vars);
    } catch (e) {
      if (e instanceof ApiError && e.code === "confirmation_required" && confirm) {
        const m = typeof meta === "function" ? meta(vars) : meta;
        const spend = status.data?.spend;
        const setting = settings.data?.editable.find((x) => x.key === "auto_approve_usd");
        const ok = await confirm({
          title: m.title,
          description: m.description,
          duration: m.duration,
          estimateUsd: num(e.details.estimate_usd),
          remainingUsd: spend ? Math.max(0, spend.cap_usd - spend.used_usd) : undefined,
          autoApproveMax: setting?.max ?? undefined,
        });
        if (!ok) {
          setState((s) => ({ ...s, pending: false }));
          return undefined;
        }
        try {
          return handleResult(await fn(vars, str(e.details.confirm_token)), vars);
        } catch (e2) {
          return fail(e2);
        }
      }
      return fail(e);
    }
  };

  const fail = (e: unknown): undefined => {
    if (e instanceof ApiError) {
      if (e.code === "spend_cap_reached") void qc.invalidateQueries({ queryKey: keys.status() });
      if (e.code === "job_in_progress") {
        const existing = str(e.details.job_id);
        if (existing) {
          setState({ jobId: existing, pending: false, error: null, keyRequired: false });
          toast({ tone: "info", title: t("errors.job_in_progress") });
          return undefined;
        }
      }
      if (e.code === "no_api_key") {
        setState({ jobId: null, pending: false, error: e, keyRequired: true });
        return undefined;
      }
    }
    setState({ jobId: null, pending: false, error: e, keyRequired: false });
    return undefined;
  };

  const reset = () => setState({ jobId: null, pending: false, error: null, keyRequired: false });
  return { ...state, run, reset };
}
