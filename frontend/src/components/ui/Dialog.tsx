import * as RD from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { cx } from "@/lib/cx";
import { t } from "@/copy/t";

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  role?: "dialog" | "alertdialog";
}

/** Width min(36rem, 100vw − 2·gutter); a bottom sheet on phones. Focus is trapped and restored. */
export function Dialog({ open, onOpenChange, title, description, children, footer, role = "dialog" }: DialogProps) {
  return (
    <RD.Root open={open} onOpenChange={onOpenChange}>
      <RD.Portal>
        <RD.Overlay className="fixed inset-0 z-50 bg-overlay data-[state=open]:animate-[k-fade-in_var(--dur)]" />
        <RD.Content
          role={role}
          className={cx(
            "fixed z-50 bg-surface text-text shadow-dialog border border-border flex flex-col",
            "inset-x-0 bottom-0 max-h-[90dvh] rounded-t-lg sm:rounded-lg",
            "sm:inset-auto sm:left-1/2 sm:top-1/2 sm:-translate-x-1/2 sm:-translate-y-1/2 sm:w-(--dialog-width) sm:max-h-[85dvh]",
            "data-[state=open]:animate-[k-fade-in_var(--dur)]",
          )}
        >
          <div className="flex items-start gap-3 p-5 pb-3">
            <div className="flex-1 min-w-0">
              <RD.Title className="text-lg font-semibold">{title}</RD.Title>
              {description ? <RD.Description className="mt-1 text-sm text-muted">{description}</RD.Description> : <RD.Description className="sr-only">{title}</RD.Description>}
            </div>
            <RD.Close className="rounded-md p-1 text-muted hover:text-text hover:bg-surface-2" aria-label={t("common.close")}>
              <X className="size-5" aria-hidden />
            </RD.Close>
          </div>
          <div className="px-5 pb-4 overflow-y-auto">{children}</div>
          {footer ? <div className="flex flex-wrap justify-end gap-2 border-t border-border px-5 py-3">{footer}</div> : null}
        </RD.Content>
      </RD.Portal>
    </RD.Root>
  );
}

interface SheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  side?: "right" | "left" | "bottom";
  width?: "drawer" | "wide" | "nav";
  children: ReactNode;
  headerExtra?: ReactNode;
  modal?: boolean;
  hideTitle?: boolean;
}

/** A Radix dialog as a side or bottom sheet. */
export function Sheet({ open, onOpenChange, title, side = "right", width = "drawer", children, headerExtra, modal = true, hideTitle }: SheetProps) {
  const widthClass = width === "drawer" ? "lg:w-(--drawer-width)" : width === "nav" ? "w-[min(18rem,85vw)]" : "lg:w-[min(48rem,60vw)]";
  return (
    <RD.Root open={open} onOpenChange={onOpenChange} modal={modal}>
      <RD.Portal>
        {modal ? <RD.Overlay className="fixed inset-0 z-40 bg-overlay data-[state=open]:animate-[k-fade-in_var(--dur)]" /> : null}
        <RD.Content
          onInteractOutside={modal ? undefined : (e) => e.preventDefault()}
          className={cx(
            "fixed z-40 bg-surface text-text shadow-dialog border-border flex flex-col",
            side === "right" && cx("inset-y-0 right-0 w-full border-l data-[state=open]:animate-[k-slide-in_var(--dur)]", widthClass),
            side === "left" && cx("inset-y-0 left-0 border-r", widthClass),
            side === "bottom" && "inset-x-0 bottom-0 max-h-[85dvh] rounded-t-lg border-t data-[state=open]:animate-[k-slide-up_var(--dur)]",
          )}
        >
          <div className="flex items-center gap-2 border-b border-border px-4 py-2.5">
            <RD.Title className={cx("flex-1 min-w-0 truncate font-semibold", hideTitle && "sr-only")}>{title}</RD.Title>
            {hideTitle ? <div className="flex-1" /> : null}
            {headerExtra}
            <RD.Description className="sr-only">{title}</RD.Description>
            <RD.Close className="rounded-md p-1.5 text-muted hover:text-text hover:bg-surface-2" aria-label={t("common.close")}>
              <X className="size-5" aria-hidden />
            </RD.Close>
          </div>
          <div className="flex-1 min-h-0 overflow-y-auto">{children}</div>
        </RD.Content>
      </RD.Portal>
    </RD.Root>
  );
}
