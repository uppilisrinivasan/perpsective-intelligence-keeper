import { useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { ArrowUp, Square, X } from "lucide-react";
import { t } from "@/copy/t";
import { cx } from "@/lib/cx";

export interface MentionOption {
  key: string;
  label: string;
  hint?: string;
}

const MAX_ROWS = 8;

/** Auto-growing textarea (1–8 lines); Enter sends, Shift+Enter adds a newline; "@" attaches context. */
export function ChatInput({ onSend, onStop, streaming, disabled, disabledReason, contextLabel, onRemoveContext, mentions, onMention, autoFocus, prefill }: {
  onSend: (text: string) => void;
  onStop?: () => void;
  streaming: boolean;
  disabled?: boolean;
  disabledReason?: string;
  contextLabel?: string;
  onRemoveContext?: () => void;
  mentions?: MentionOption[];
  onMention?: (key: string) => void;
  autoFocus?: boolean;
  prefill?: string;
}) {
  const [text, setText] = useState(prefill ?? "");
  const [active, setActive] = useState(0);
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (prefill) setText(prefill);
  }, [prefill]);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    const line = parseFloat(getComputedStyle(el).lineHeight) || 24;
    el.style.height = `${Math.min(el.scrollHeight, line * MAX_ROWS + 16)}px`;
  }, [text]);

  const mentionQuery = /(?:^|\s)@([^\s@]*)$/.exec(text)?.[1];
  const options = useMemo(() => {
    if (mentionQuery === undefined || !mentions) return [];
    const q = mentionQuery.toLowerCase();
    return mentions.filter((m) => m.label.toLowerCase().includes(q)).slice(0, 8);
  }, [mentionQuery, mentions]);

  const pick = (key: string) => {
    onMention?.(key);
    setText((s) => s.replace(/@([^\s@]*)$/, ""));
    setActive(0);
    ref.current?.focus();
  };

  const submit = () => {
    const v = text.trim();
    if (!v || disabled || streaming) return;
    onSend(v);
    setText("");
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (options.length) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActive((a) => (a + 1) % options.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActive((a) => (a - 1 + options.length) % options.length);
        return;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        const o = options[active];
        if (o) pick(o.key);
        return;
      }
    }
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="relative">
      {options.length ? (
        <ul role="listbox" aria-label={t("chat.mention.label")} className="absolute bottom-full z-10 mb-2 max-h-64 w-full overflow-y-auto rounded-md border border-border bg-surface p-1 shadow-pop">
          {options.map((o, i) => (
            <li key={o.key} role="option" aria-selected={i === active}>
              <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => pick(o.key)} className={cx("flex w-full items-baseline gap-2 rounded-sm px-2 py-1 text-left text-sm", i === active && "bg-surface-2")}>
                <span className="truncate">{o.label}</span>
                {o.hint ? <span className="text-xs text-muted">{o.hint}</span> : null}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <div className={cx("rounded-lg border border-border-strong bg-surface p-2 shadow-card focus-within:border-focus", disabled && "opacity-70")}>
        {contextLabel ? (
          <span className="mb-1.5 inline-flex items-center gap-1 rounded-full bg-surface-2 py-0.5 pl-2.5 pr-1 text-xs">
            {contextLabel}
            {onRemoveContext ? (
              <button type="button" onClick={onRemoveContext} className="rounded-full p-0.5 hover:bg-border" aria-label={t("chat.removeContext", { label: contextLabel })}>
                <X className="size-3" aria-hidden />
              </button>
            ) : null}
          </span>
        ) : null}
        <div className="flex items-end gap-2">
          <label htmlFor="ask-input" className="sr-only">
            {t("chat.input.label")}
          </label>
          <textarea
            id="ask-input"
            ref={ref}
            data-shortcut="ask-input"
            rows={1}
            value={text}
            disabled={disabled}
            autoFocus={autoFocus}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKey}
            placeholder={disabled ? (disabledReason ?? "") : t("chat.input.placeholder")}
            aria-describedby={disabled && disabledReason ? "ask-input-disabled" : undefined}
            className="max-h-[50dvh] min-h-9 flex-1 resize-none bg-transparent px-1.5 py-1.5 text-base outline-none placeholder:text-muted"
          />
          {streaming ? (
            <button type="button" onClick={onStop} className="inline-flex size-9 items-center justify-center rounded-md bg-text text-bg" aria-label={t("chat.stop")}>
              <Square className="size-4" aria-hidden />
            </button>
          ) : (
            <button type="button" onClick={submit} disabled={disabled || !text.trim()} className="inline-flex size-9 items-center justify-center rounded-md bg-primary text-on-primary disabled:opacity-40" aria-label={t("chat.send")}>
              <ArrowUp className="size-4" aria-hidden />
            </button>
          )}
        </div>
      </div>
      {disabled && disabledReason ? (
        <p id="ask-input-disabled" className="mt-1 text-xs text-muted">
          {disabledReason}
        </p>
      ) : null}
    </div>
  );
}
