import { LoaderCircle } from "lucide-react";
import { cx } from "@/lib/cx";

export function Spinner({ className, label }: { className?: string; label?: string }) {
  return (
    <span role={label ? "status" : undefined} className="inline-flex items-center">
      <LoaderCircle className={cx("size-[1em] animate-spin motion-reduce:animate-none text-muted", className)} aria-hidden strokeWidth={1.75} />
      {label ? <span className="sr-only">{label}</span> : null}
    </span>
  );
}
