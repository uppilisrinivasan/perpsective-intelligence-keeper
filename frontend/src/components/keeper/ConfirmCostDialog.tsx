import { useState } from "react";
import { Dialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { Checkbox } from "@/components/ui/Field";
import { t } from "@/copy/t";
import { formatMoney } from "@/lib/format";

export interface ConfirmRequest {
  title: string;
  description?: string;
  estimateUsd?: number;
  duration?: string;
  remainingUsd?: number;
  /** The upper bound for "Don't ask again below $x" (editable setting max). */
  autoApproveMax?: number;
}

/** What will happen, the estimate, the remaining budget, and "Don't ask again below $x". */
export function ConfirmCostDialog({ request, onResolve }: { request: ConfirmRequest | null; onResolve: (ok: boolean, dontAskBelow?: number) => void }) {
  const [dontAsk, setDontAsk] = useState(false);
  const est = request?.estimateUsd;
  const canRemember = est !== undefined && request?.autoApproveMax !== undefined && est <= request.autoApproveMax;
  return (
    <Dialog
      open={request !== null}
      onOpenChange={(o) => {
        if (!o) onResolve(false);
      }}
      title={request?.title ?? ""}
      description={request?.description}
      footer={
        <>
          <Button onClick={() => onResolve(false)}>{t("common.cancel")}</Button>
          <Button variant="primary" onClick={() => onResolve(true, dontAsk && est !== undefined ? est : undefined)} autoFocus>
            {est !== undefined ? t("confirm.runFor", { amount: formatMoney(est) }) : t("confirm.run")}
          </Button>
        </>
      }
    >
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
        {est !== undefined ? (
          <>
            <dt className="text-muted">{t("confirm.estimate")}</dt>
            <dd className="tabular font-medium">{t("confirm.about", { amount: formatMoney(est) })}</dd>
          </>
        ) : null}
        {request?.duration ? (
          <>
            <dt className="text-muted">{t("confirm.duration")}</dt>
            <dd>{request.duration}</dd>
          </>
        ) : null}
        {request?.remainingUsd !== undefined ? (
          <>
            <dt className="text-muted">{t("confirm.remaining")}</dt>
            <dd className="tabular">{formatMoney(request.remainingUsd)}</dd>
          </>
        ) : null}
      </dl>
      {canRemember && est !== undefined ? (
        <div className="mt-4">
          <Checkbox checked={dontAsk} onCheckedChange={setDontAsk} label={t("confirm.dontAsk", { amount: formatMoney(est) })} />
        </div>
      ) : null}
    </Dialog>
  );
}
