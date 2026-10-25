import { useEffect, useState } from "react";
import { Check, MessageSquare, Pencil, Star, ThumbsUp, Undo2, Wrench, X } from "lucide-react";
import type { RoutedFinding } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Menu } from "@/components/ui/Menu";
import { SelectField, TextArea } from "@/components/ui/Field";
import { Badge } from "@/components/ui/Badge";
import { Tooltip } from "@/components/ui/Tooltip";
import { t, tDynamic } from "@/copy/t";

export type FeedbackState = "accepted" | "edited" | "dismissed" | "good_catch" | "open";

export interface FeedbackPayload {
  state: FeedbackState;
  text?: string;
  severity?: string;
  reason?: string;
}

const UNDO_MS = 10_000;
const DISMISS_REASONS = ["not_relevant", "wrong", "already_handled"] as const;
const SEVERITIES = ["low", "medium", "high"] as const;

/** Accept, Edit, Dismiss (with reason), Good catch, Fix and test, Ask; Undo for 10 s, then an Undo link. */
export function FeedbackActions({ finding, canFix, onFeedback, onFix, onAsk, disabledReason, fixDisabledReason, fixPrimary }: {
  finding: RoutedFinding;
  canFix: boolean;
  onFeedback: (p: FeedbackPayload) => void;
  onFix?: () => void;
  onAsk?: () => void;
  disabledReason?: string;
  fixDisabledReason?: string;
  fixPrimary?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(finding.user_text ?? finding.statement_md);
  const [severity, setSeverity] = useState(finding.user_severity ?? finding.severity);
  const [recent, setRecent] = useState(false);
  const state = finding.user_state as FeedbackState;
  const decided = state && state !== "open";

  useEffect(() => {
    if (!recent) return;
    const id = setTimeout(() => setRecent(false), UNDO_MS);
    return () => clearTimeout(id);
  }, [recent]);

  const give = (p: FeedbackPayload) => {
    onFeedback(p);
    setRecent(p.state !== "open");
  };
  const disabled = Boolean(disabledReason);

  if (editing) {
    return (
      <form
        className="space-y-2"
        onSubmit={(e) => {
          e.preventDefault();
          give({ state: "edited", text, severity });
          setEditing(false);
        }}
      >
        <TextArea label={t("finding.edit.text")} value={text} onChange={(e) => setText(e.target.value)} rows={4} />
        <SelectField
          label={t("finding.edit.severity")}
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
          options={SEVERITIES.map((s) => ({ value: s, label: tDynamic(`severity.${s}`) }))}
        />
        <div className="flex gap-2">
          <Button type="submit" size="sm" variant="primary">
            {t("common.save")}
          </Button>
          <Button size="sm" onClick={() => setEditing(false)}>
            {t("common.cancel")}
          </Button>
        </div>
      </form>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {decided ? (
        <>
          <Badge tone={state === "dismissed" ? "neutral" : "success"} icon={state === "dismissed" ? X : Check}>
            {tDynamic(`finding.state.${state}`)}
          </Badge>
          {recent ? (
            <Button size="sm" variant="secondary" icon={Undo2} onClick={() => give({ state: "open" })}>
              {t("common.undo")}
            </Button>
          ) : (
            <button type="button" className="text-xs text-primary hover:underline" onClick={() => give({ state: "open" })}>
              {t("common.undo")}
            </button>
          )}
        </>
      ) : (
        <>
          <Tooltip content={disabledReason}>
            <span>
              <Button size="sm" icon={Check} disabled={disabled} onClick={() => give({ state: "accepted" })}>
                {t("finding.action.accept")}
              </Button>
            </span>
          </Tooltip>
          <Tooltip content={disabledReason}>
            <span>
              <Button size="sm" variant="ghost" icon={Pencil} disabled={disabled} onClick={() => setEditing(true)}>
                {t("common.edit")}
              </Button>
            </span>
          </Tooltip>
          <Menu
            label={t("finding.dismiss.label")}
            align="start"
            trigger={
              <Button size="sm" variant="ghost" icon={X} disabled={disabled} title={disabledReason}>
                {t("common.dismiss")}
              </Button>
            }
            items={[
              ...DISMISS_REASONS.map((r) => ({ key: r, label: tDynamic(`finding.dismiss.${r}`), onSelect: () => give({ state: "dismissed", reason: r }) })),
              "separator" as const,
              { key: "none", label: t("finding.dismiss.noReason"), onSelect: () => give({ state: "dismissed" }) },
            ]}
          />
          {finding.lane === "blind_spot" ? (
            <Button size="sm" variant="ghost" icon={Star} disabled={disabled} onClick={() => give({ state: "good_catch" })}>
              {t("finding.action.goodCatch")}
            </Button>
          ) : null}
        </>
      )}
      {finding.fixable && canFix && onFix ? (
        <Tooltip content={fixDisabledReason}>
          <span>
            <Button size="sm" variant={fixPrimary ? "primary" : "secondary"} icon={Wrench} disabled={Boolean(fixDisabledReason)} onClick={onFix}>
              {t("finding.action.fix")}
            </Button>
          </span>
        </Tooltip>
      ) : null}
      {onAsk ? (
        <Button size="sm" variant="ghost" icon={MessageSquare} onClick={onAsk}>
          {t("common.askAboutThis")}
        </Button>
      ) : null}
      {state === "good_catch" ? <ThumbsUp className="sr-only" aria-hidden /> : null}
    </div>
  );
}
