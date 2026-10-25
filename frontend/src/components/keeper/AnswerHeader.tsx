import type { ReactNode } from "react";
import { cx } from "@/lib/cx";

/** The page h1 and the answer sentence. Focus moves here on route change (tabIndex −1). */
export function AnswerHeader({ title, subtitle, actions, eyebrow, className, tour }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode; className?: string; tour?: string }) {
  return (
    <header className={cx("flex flex-wrap items-start gap-x-6 gap-y-3", className)} data-tour={tour}>
      <div className="min-w-0 flex-[1_1_28rem]">
        {eyebrow ? <div className="mb-1 flex flex-wrap items-center gap-2 text-sm text-muted">{eyebrow}</div> : null}
        <h1 tabIndex={-1} className="text-2xl font-semibold outline-none k-anywhere" data-page-title>
          {title}
        </h1>
        {subtitle ? <div className="mt-1.5 text-base text-muted k-measure">{subtitle}</div> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}
