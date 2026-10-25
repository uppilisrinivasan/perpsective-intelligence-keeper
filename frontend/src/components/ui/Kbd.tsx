import { cx } from "@/lib/cx";

export function Kbd({ keys, subtle }: { keys: string; subtle?: boolean }) {
  return (
    <span className="inline-flex items-center gap-0.5" aria-hidden={subtle || undefined}>
      {keys.split(" ").map((k, i) => (
        <kbd
          key={i}
          className={cx(
            "font-mono text-xs rounded-sm border border-border px-1 leading-normal",
            subtle ? "opacity-70" : "bg-surface-2",
          )}
        >
          {k}
        </kbd>
      ))}
    </span>
  );
}
