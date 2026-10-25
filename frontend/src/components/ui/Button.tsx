import type { ButtonHTMLAttributes, ReactNode, Ref } from "react";
import { LoaderCircle, type LucideIcon } from "lucide-react";
import { cx } from "@/lib/cx";
import { Kbd } from "./Kbd";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: "sm" | "md";
  loading?: boolean;
  icon?: LucideIcon;
  iconEnd?: LucideIcon;
  kbd?: string;
  ref?: Ref<HTMLButtonElement>;
  children?: ReactNode;
}

const variants: Record<ButtonVariant, string> = {
  primary: "bg-primary text-on-primary hover:bg-primary-hover border border-transparent",
  secondary: "bg-surface text-text border border-border-strong hover:bg-surface-2",
  ghost: "bg-transparent text-text border border-transparent hover:bg-surface-2",
  danger: "bg-danger-bg text-danger-fg border border-danger hover:brightness-95",
};

export function buttonClass(variant: ButtonVariant = "secondary", size: "sm" | "md" = "md", extra?: string): string {
  return cx(
    "inline-flex items-center justify-center gap-2 rounded-md font-medium whitespace-nowrap",
    "transition-colors duration-(--dur-fast) disabled:opacity-55 disabled:cursor-not-allowed",
    size === "sm" ? "text-sm px-2.5 py-1 min-h-7" : "text-sm px-3.5 py-2 min-h-9",
    variants[variant],
    extra,
  );
}

export function Button({ variant = "secondary", size = "md", loading, icon: Icon, iconEnd: IconEnd, kbd, className, children, disabled, ref, type, ...rest }: ButtonProps) {
  return (
    <button ref={ref} type={type ?? "button"} className={buttonClass(variant, size, className)} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading ? <LoaderCircle className="size-[1em] animate-spin motion-reduce:animate-none" aria-hidden /> : Icon ? <Icon className="size-[1em] shrink-0" aria-hidden strokeWidth={1.75} /> : null}
      {children}
      {IconEnd ? <IconEnd className="size-[1em] shrink-0" aria-hidden strokeWidth={1.75} /> : null}
      {kbd ? <Kbd keys={kbd} subtle /> : null}
    </button>
  );
}
