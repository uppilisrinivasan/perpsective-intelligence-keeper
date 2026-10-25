import { useEffect, useState, type ReactNode } from "react";
import { cx } from "@/lib/cx";
import { t } from "@/copy/t";

/** Skeleton blocks; respects reduced motion (the shimmer is disabled in CSS). */
export function Skeleton({ shape = "line", lines = 1, className }: { shape?: "line" | "block" | "circle" | "row"; lines?: number; className?: string }) {
  if (shape === "circle") return <div className={cx("k-skeleton rounded-full size-8", className)} aria-hidden />;
  if (shape === "block") return <div className={cx("k-skeleton h-24 w-full", className)} aria-hidden />;
  if (shape === "row")
    return (
      <div className={cx("flex flex-col gap-2 py-3", className)} aria-hidden>
        <div className="k-skeleton h-4 w-3/5" />
        <div className="k-skeleton h-3 w-2/5" />
      </div>
    );
  return (
    <div className={cx("flex flex-col gap-2", className)} aria-hidden>
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className={cx("k-skeleton h-3.5", i === lines - 1 && lines > 1 ? "w-2/3" : "w-full")} />
      ))}
    </div>
  );
}

/** Shows its children only after 150 ms, to avoid skeleton flashes (screens/08 §2). */
export function Delayed({ children, ms = 150 }: { children: ReactNode; ms?: number }) {
  const [show, setShow] = useState(false);
  useEffect(() => {
    const id = setTimeout(() => setShow(true), ms);
    return () => clearTimeout(id);
  }, [ms]);
  return show ? (
    <div role="status" aria-live="polite">
      <span className="sr-only">{t("common.loading")}</span>
      {children}
    </div>
  ) : null;
}
