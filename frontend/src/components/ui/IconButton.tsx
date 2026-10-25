import type { ButtonHTMLAttributes, Ref } from "react";
import type { LucideIcon } from "lucide-react";
import { cx } from "@/lib/cx";
import { Tooltip } from "./Tooltip";

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  /** Required: becomes aria-label and the tooltip. */
  label: string;
  icon: LucideIcon;
  size?: "sm" | "md";
  badge?: number | string;
  tooltip?: boolean;
  ref?: Ref<HTMLButtonElement>;
}

export function IconButton({ label, icon: Icon, size = "md", badge, tooltip = true, className, ref, type, ...rest }: IconButtonProps) {
  const btn = (
    <button
      ref={ref}
      type={type ?? "button"}
      aria-label={label}
      className={cx(
        "relative inline-flex items-center justify-center rounded-md text-muted hover:text-text hover:bg-surface-2",
        "disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-(--dur-fast)",
        size === "sm" ? "size-7 text-sm" : "size-9 text-base",
        className,
      )}
      {...rest}
    >
      <Icon className="size-[1.15em]" aria-hidden strokeWidth={1.75} />
      {badge !== undefined && badge !== 0 ? (
        <span className="absolute -top-0.5 -right-0.5 min-w-4 rounded-full bg-primary px-1 text-[0.65rem] leading-4 text-on-primary tabular">{badge}</span>
      ) : null}
    </button>
  );
  return tooltip ? <Tooltip content={label}>{btn}</Tooltip> : btn;
}
