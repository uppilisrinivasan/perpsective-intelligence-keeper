import * as RSwitch from "@radix-ui/react-switch";
import * as RCheckbox from "@radix-ui/react-checkbox";
import { Check } from "lucide-react";
import { useId, type InputHTMLAttributes, type ReactNode, type Ref, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";
import { cx } from "@/lib/cx";

export const inputClass =
  "w-full rounded-md border border-border-strong bg-surface px-3 py-1.5 text-sm text-text placeholder:text-muted disabled:opacity-60 aria-[invalid=true]:border-danger";

interface FieldShell {
  label: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  className?: string;
  hideLabel?: boolean;
}

function Shell({ id, label, hint, error, className, hideLabel, children }: FieldShell & { id: string; children: ReactNode }) {
  return (
    <div className={cx("flex flex-col gap-1", className)}>
      <label htmlFor={id} className={cx("text-sm font-medium", hideLabel && "sr-only")}>
        {label}
      </label>
      {children}
      {hint ? (
        <p id={`${id}-hint`} className="text-xs text-muted">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={`${id}-error`} className="text-xs text-danger-fg" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function describedBy(id: string, hint: unknown, error: unknown): string | undefined {
  return [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(" ") || undefined;
}

export function TextField({ label, hint, error, className, hideLabel, ref, ...rest }: FieldShell & InputHTMLAttributes<HTMLInputElement> & { ref?: Ref<HTMLInputElement> }) {
  const auto = useId();
  const id = rest.id ?? auto;
  return (
    <Shell id={id} label={label} hint={hint} error={error} className={className} hideLabel={hideLabel}>
      <input ref={ref} id={id} className={inputClass} aria-invalid={error ? true : undefined} aria-describedby={describedBy(id, hint, error)} {...rest} />
    </Shell>
  );
}

export function TextArea({ label, hint, error, className, hideLabel, ref, ...rest }: FieldShell & TextareaHTMLAttributes<HTMLTextAreaElement> & { ref?: Ref<HTMLTextAreaElement> }) {
  const auto = useId();
  const id = rest.id ?? auto;
  return (
    <Shell id={id} label={label} hint={hint} error={error} className={className} hideLabel={hideLabel}>
      <textarea ref={ref} id={id} className={cx(inputClass, "min-h-20 resize-y")} aria-invalid={error ? true : undefined} aria-describedby={describedBy(id, hint, error)} {...rest} />
    </Shell>
  );
}

export interface SelectOption {
  value: string;
  label: string;
}

/** A native select (best keyboard and screen-reader support). */
export function SelectField({ label, hint, error, className, hideLabel, options, ...rest }: FieldShell & SelectHTMLAttributes<HTMLSelectElement> & { options: SelectOption[] }) {
  const auto = useId();
  const id = rest.id ?? auto;
  return (
    <Shell id={id} label={label} hint={hint} error={error} className={className} hideLabel={hideLabel}>
      <select id={id} className={cx(inputClass, "pr-8")} aria-describedby={describedBy(id, hint, error)} {...rest}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </Shell>
  );
}

export function Switch({ checked, onCheckedChange, label, disabled, hint }: { checked: boolean; onCheckedChange: (v: boolean) => void; label: ReactNode; disabled?: boolean; hint?: ReactNode }) {
  const id = useId();
  return (
    <div className="flex items-start gap-3">
      <RSwitch.Root
        id={id}
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        aria-describedby={hint ? `${id}-hint` : undefined}
        className="relative mt-0.5 h-5 w-9 shrink-0 rounded-full border border-border-strong bg-surface-2 data-[state=checked]:bg-primary data-[state=checked]:border-primary disabled:opacity-50"
      >
        <RSwitch.Thumb className="block size-4 translate-x-0.5 rounded-full bg-surface shadow-card transition-transform duration-(--dur-fast) data-[state=checked]:translate-x-4" />
      </RSwitch.Root>
      <div>
        <label htmlFor={id} className="text-sm font-medium">
          {label}
        </label>
        {hint ? (
          <p id={`${id}-hint`} className="text-xs text-muted">
            {hint}
          </p>
        ) : null}
      </div>
    </div>
  );
}

export function Checkbox({ checked, onCheckedChange, label, disabled }: { checked: boolean; onCheckedChange: (v: boolean) => void; label: ReactNode; disabled?: boolean }) {
  const id = useId();
  return (
    <div className="flex items-start gap-2">
      <RCheckbox.Root
        id={id}
        checked={checked}
        onCheckedChange={(v) => onCheckedChange(v === true)}
        disabled={disabled}
        className="mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-sm border border-border-strong bg-surface data-[state=checked]:bg-primary data-[state=checked]:border-primary"
      >
        <RCheckbox.Indicator>
          <Check className="size-3 text-on-primary" aria-hidden />
        </RCheckbox.Indicator>
      </RCheckbox.Root>
      <label htmlFor={id} className="text-sm">
        {label}
      </label>
    </div>
  );
}
