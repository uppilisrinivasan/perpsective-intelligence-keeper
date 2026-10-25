import { AlertTriangle, CheckCircle2, Eye, KeyRound, ScanSearch, UserRoundSearch, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { ApiError } from "@/api/errors";
import { Button, buttonClass } from "@/components/ui/Button";
import { Disclosure } from "@/components/ui/Disclosure";
import { Popover } from "@/components/ui/Popover";
import { t } from "@/copy/t";
import { cx } from "@/lib/cx";
import { errorMessage } from "@/lib/errors";

/** The empty-state glyph: the lane icons in a circle. */
function Glyph({ icon: Icon }: { icon?: LucideIcon }) {
  if (Icon)
    return (
      <span className="flex size-14 items-center justify-center rounded-full bg-surface-2 text-muted" aria-hidden>
        <Icon className="size-7" strokeWidth={1.5} />
      </span>
    );
  return (
    <span className="relative grid size-16 grid-cols-2 place-items-center rounded-full bg-surface-2 p-2.5" aria-hidden>
      <Eye className="size-5 text-edge-fg" strokeWidth={1.5} />
      <ScanSearch className="size-5 text-blind-fg" strokeWidth={1.5} />
      <UserRoundSearch className="size-5 text-unknown-fg" strokeWidth={1.5} />
      <CheckCircle2 className="size-5 text-shared-fg" strokeWidth={1.5} />
    </span>
  );
}

/** Icon composition, one sentence why, one primary next step. */
export function EmptyState({ title, body, action, icon, compact }: { title: ReactNode; body?: ReactNode; action?: ReactNode; icon?: LucideIcon; compact?: boolean }) {
  return (
    <div className={cx("flex flex-col items-center text-center gap-3", compact ? "py-6" : "py-12")}>
      <Glyph icon={icon} />
      <p className="text-base font-medium">{title}</p>
      {body ? <p className="k-measure text-sm text-muted">{body}</p> : null}
      {action ? <div className="mt-1 flex flex-wrap justify-center gap-2">{action}</div> : null}
    </div>
  );
}

function ErrorDetails({ error }: { error: unknown }) {
  if (!(error instanceof ApiError)) return null;
  return (
    <Disclosure summary={t("common.details")} className="mt-2 text-xs text-muted" headerClassName="text-xs text-muted">
      <dl className="grid gap-0.5 font-mono text-xs">
        <dd>{t("common.errorCode", { code: error.code })}</dd>
        {error.requestId ? <dd>{t("common.requestId", { id: error.requestId })}</dd> : null}
        {error.message ? <dd className="k-anywhere">{error.message}</dd> : null}
      </dl>
    </Disclosure>
  );
}

/** What happened in plain words, Try again, a Details disclosure with the code and request ID. */
export function InlineError({ error, onRetry, message, className }: { error: unknown; onRetry?: () => void; message?: string; className?: string }) {
  return (
    <div role="alert" className={cx("rounded-md border border-danger/40 bg-danger-bg p-3 text-danger-fg", className)}>
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium">{message ?? errorMessage(error)}</p>
          <ErrorDetails error={error} />
        </div>
        {onRetry ? (
          <Button size="sm" variant="secondary" onClick={onRetry}>
            {t("common.retry")}
          </Button>
        ) : null}
      </div>
    </div>
  );
}

export function PageError({ error, onRetry, title }: { error: unknown; onRetry?: () => void; title?: string }) {
  return (
    <div className="k-page flex flex-col items-center py-16 text-center" role="alert">
      <Glyph icon={AlertTriangle} />
      <h1 className="mt-4 text-xl font-semibold" tabIndex={-1}>
        {title ?? errorMessage(error)}
      </h1>
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        {onRetry ? (
          <Button variant="primary" onClick={onRetry}>
            {t("common.retry")}
          </Button>
        ) : null}
        <Link to="/queue" className={buttonClass("secondary")}>
          {t("states.goToQueue")}
        </Link>
      </div>
      <div className="mt-2 text-left">
        <ErrorDetails error={error} />
      </div>
    </div>
  );
}

/** How to add a key: three steps, never asking for the key in the UI. */
export function KeyHowTo({ provider, envVar }: { provider: string; envVar?: string }) {
  return (
    <ol className="list-decimal space-y-1 pl-5 text-sm">
      <li>{t("key.how.step1", { provider })}</li>
      <li>{envVar ? t("key.how.step2", { env: envVar }) : t("key.how.step2generic")}</li>
      <li>{t("key.how.step3")}</li>
    </ol>
  );
}

export function KeyHowButton({ provider, envVar }: { provider: string; envVar?: string }) {
  return (
    <Popover
      trigger={
        <button type="button" className={buttonClass("secondary", "sm")}>
          {t("key.how")}
        </button>
      }
    >
      <p className="mb-2 text-sm font-medium">{t("key.how.title", { provider })}</p>
      <KeyHowTo provider={provider} envVar={envVar} />
    </Popover>
  );
}

/** What it would do, what you can see instead. */
export function KeyRequired({ what, instead, provider, envVar }: { what: string; instead?: ReactNode; provider: string; envVar?: string }) {
  return (
    <div className="rounded-md border border-border bg-surface-2 p-4">
      <div className="flex items-start gap-3">
        <KeyRound className="mt-0.5 size-5 shrink-0 text-muted" aria-hidden />
        <div className="flex-1 space-y-2">
          <p className="text-sm font-medium">{what}</p>
          {instead ? <div className="text-sm text-muted">{instead}</div> : null}
          <KeyHowButton provider={provider} envVar={envVar} />
        </div>
      </div>
    </div>
  );
}
