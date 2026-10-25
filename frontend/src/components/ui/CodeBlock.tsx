import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { t } from "@/copy/t";
import { copyText } from "@/lib/clipboard";

/** A code block with copy. Syntax highlighting (shiki) is not loaded in this build; the text is plain mono. */
export function CodeBlock({ code, lang, copy = true }: { code: string; lang?: string; copy?: boolean }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="group relative my-2 rounded-md border border-border bg-surface-2">
      {copy ? (
        <button
          type="button"
          onClick={async () => {
            if (await copyText(code)) {
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            }
          }}
          className="absolute right-1.5 top-1.5 rounded-sm p-1 text-muted opacity-70 hover:opacity-100 hover:bg-surface focus-visible:opacity-100"
          aria-label={copied ? t("common.copied") : t("common.copy")}
        >
          {copied ? <Check className="size-4" aria-hidden /> : <Copy className="size-4" aria-hidden />}
        </button>
      ) : null}
      <pre className="overflow-x-auto p-3 pr-9 text-code font-mono leading-relaxed" data-lang={lang}>
        <code>{code}</code>
      </pre>
    </div>
  );
}
