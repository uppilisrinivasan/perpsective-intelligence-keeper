import { FileCode } from "lucide-react";
import type { RoutedFinding } from "@/api/types";
import { Pill } from "@/components/ui/Badge";
import { Markdown } from "@/components/ui/Markdown";
import { Tooltip } from "@/components/ui/Tooltip";
import { t, tDynamic } from "@/copy/t";
import { cx } from "@/lib/cx";
import { laneDef } from "@/lib/lanes";
import { EvidenceList } from "./EvidenceList";
import { FeedbackActions, type FeedbackPayload } from "./FeedbackActions";
import { LaneBadge } from "./Lane";

export type FindingVariant = "pane" | "inline" | "compare" | "practice-reveal";

export interface FindingCardProps {
  finding: RoutedFinding;
  variant?: FindingVariant;
  maintainer: string;
  onFeedback?: (p: FeedbackPayload) => void;
  onFix?: () => void;
  onAsk?: () => void;
  onLocate?: (path: string, line: number | null) => void;
  canFix?: boolean;
  disabledReason?: string;
  fixDisabledReason?: string;
  fixPrimary?: boolean;
  highlighted?: boolean;
}

function looksLikeCode(md: string): boolean {
  return md.includes("```") || /^\s{4}\S/m.test(md);
}

export function anchorLabel(a: RoutedFinding["anchor"]): string | null {
  if (!a.path) return null;
  if (a.start_line) return t("format.pathLine", { path: a.path, line: a.end_line && a.end_line !== a.start_line ? `${a.start_line}–${a.end_line}` : a.start_line });
  return a.path;
}

/** One routed finding: title, meta, statement, why (evidence), suggestion and feedback actions. */
export function FindingCard({ finding: f, variant = "pane", maintainer, onFeedback, onFix, onAsk, onLocate, canFix = false, disabledReason, fixDisabledReason, fixPrimary, highlighted }: FindingCardProps) {
  const def = laneDef(f.lane);
  const where = anchorLabel(f.anchor);
  const severity = f.user_severity ?? f.severity;
  const statement = f.user_state === "edited" && f.user_text ? f.user_text : f.statement_md;
  const Heading = variant === "inline" ? "p" : "h3";
  return (
    <article
      id={`finding-${f.id}`}
      className={cx(
        "rounded-md border bg-surface text-left",
        variant === "inline" ? cx("border-l-4 p-3", def.border) : "border-border p-3.5",
        variant !== "inline" && cx("border-l-4", def.border),
        f.user_state === "dismissed" && "opacity-70",
        highlighted && "ring-2 ring-focus",
      )}
      aria-label={variant === "inline" ? t("finding.inlineAria", { title: f.title }) : undefined}
      data-finding={f.id}
    >
      <div className="flex flex-wrap items-start gap-2">
        <Heading className={cx("min-w-0 flex-1 font-semibold leading-snug k-anywhere", variant === "inline" ? "text-sm" : "text-base")}>{f.title}</Heading>
        {variant !== "pane" ? <LaneBadge lane={f.lane} maintainer={maintainer} /> : null}
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs text-muted">
        <Pill tone={severity === "high" || severity === "critical" ? "danger" : "neutral"}>{tDynamic(`severity.${severity}`) || severity}</Pill>
        <span>{f.category_label || f.category}</span>
        {where ? (
          onLocate && f.anchor.path ? (
            <button type="button" className="inline-flex items-center gap-1 font-mono text-primary hover:underline k-anywhere" onClick={() => onLocate(f.anchor.path!, f.anchor.end_line ?? f.anchor.start_line ?? null)}>
              <FileCode className="size-3" aria-hidden />
              {where}
            </button>
          ) : (
            <span className="font-mono k-anywhere">{where}</span>
          )
        ) : null}
        {f.confidence ? (
          <Tooltip content={t("confidence.tooltip")}>
            <span tabIndex={0} className="k-term">
              {tDynamic(`confidence.${f.confidence}`)}
            </span>
          </Tooltip>
        ) : null}
        {f.model?.display ? <span>{t("finding.by", { model: f.model.display })}</span> : null}
      </div>
      <Markdown source={statement} className="mt-2 text-sm" />
      {variant !== "inline" ? (
        <div className="mt-2">
          <EvidenceList evidence={f.evidence} maintainer={maintainer} lane={f.lane} />
        </div>
      ) : null}
      {f.suggestion_md ? (
        <div className="mt-2">
          <p className="text-xs font-medium text-muted">{t("finding.suggested")}</p>
          {looksLikeCode(f.suggestion_md) ? <Markdown source={f.suggestion_md} className="text-sm" /> : <Markdown source={f.suggestion_md} className="text-sm italic" />}
        </div>
      ) : null}
      {onFeedback && variant !== "practice-reveal" ? (
        <div className="mt-3">
          <FeedbackActions
            finding={f}
            canFix={canFix}
            onFeedback={onFeedback}
            onFix={onFix}
            onAsk={onAsk}
            disabledReason={disabledReason}
            fixDisabledReason={fixDisabledReason}
            fixPrimary={fixPrimary}
          />
        </div>
      ) : null}
    </article>
  );
}
