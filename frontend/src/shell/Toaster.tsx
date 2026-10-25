import { useEffect } from "react";
import { Link } from "react-router";
import { AlertTriangle, CheckCircle2, CircleX, Info, X } from "lucide-react";
import { dismissToast, useToasts, type Toast } from "@/state/toasts";
import { t } from "@/copy/t";
import { cx } from "@/lib/cx";

const LIFETIME_MS = 7000;

function ToastItem({ toast }: { toast: Toast }) {
  useEffect(() => {
    const id = setTimeout(() => dismissToast(toast.id), LIFETIME_MS);
    return () => clearTimeout(id);
  }, [toast.id]);
  const Icon = toast.tone === "success" ? CheckCircle2 : toast.tone === "danger" ? CircleX : toast.tone === "warning" ? AlertTriangle : Info;
  return (
    <li className="pointer-events-auto flex w-[min(24rem,calc(100vw-2rem))] items-start gap-2.5 rounded-lg border border-border bg-surface p-3 shadow-pop">
      <Icon className={cx("mt-0.5 size-4 shrink-0", toast.tone === "success" ? "text-success" : toast.tone === "danger" ? "text-danger" : toast.tone === "warning" ? "text-warning" : "text-info")} aria-hidden />
      <div className="min-w-0 flex-1 text-sm">
        <p className="font-medium">{toast.title}</p>
        {toast.body ? <p className="text-muted">{toast.body}</p> : null}
        {toast.href ? (
          <Link to={toast.href} onClick={() => dismissToast(toast.id)} className="mt-1 inline-block font-medium text-primary hover:underline">
            {toast.actionLabel ?? t("common.open")}
          </Link>
        ) : toast.onAction ? (
          <button type="button" onClick={toast.onAction} className="mt-1 font-medium text-primary hover:underline">
            {toast.actionLabel ?? t("common.retry")}
          </button>
        ) : null}
      </div>
      <button type="button" onClick={() => dismissToast(toast.id)} className="rounded-sm p-0.5 text-muted hover:text-text" aria-label={t("common.dismiss")}>
        <X className="size-4" aria-hidden />
      </button>
    </li>
  );
}

/** Bottom-right (bottom-centre on phones); polite, errors assertive. */
export function Toaster() {
  const toasts = useToasts();
  const polite = toasts.filter((x) => x.tone !== "danger");
  const urgent = toasts.filter((x) => x.tone === "danger");
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-16 z-[65] flex flex-col items-center gap-2 px-4 sm:bottom-4 sm:items-end">
      <ul aria-live="polite" className="flex flex-col gap-2">
        {polite.map((x) => (
          <ToastItem key={x.id} toast={x} />
        ))}
      </ul>
      <ul aria-live="assertive" className="flex flex-col gap-2">
        {urgent.map((x) => (
          <ToastItem key={x.id} toast={x} />
        ))}
      </ul>
    </div>
  );
}
