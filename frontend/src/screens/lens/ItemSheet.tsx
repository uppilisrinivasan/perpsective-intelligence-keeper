import { useState } from "react";
import { Link } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Ban, Pencil, VolumeX, Volume2 } from "lucide-react";
import { api, call } from "@/api/client";
import { useLensItem } from "@/api/hooks/lens";
import { InlineError } from "@/components/keeper/States";
import { SupportMeter, itemLane, itemStatusLabel, itemTypeLabel } from "@/components/keeper/LensItem";
import { Pill } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { Sheet } from "@/components/ui/Dialog";
import { TextArea, TextField } from "@/components/ui/Field";
import { Markdown } from "@/components/ui/Markdown";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tooltip } from "@/components/ui/Tooltip";
import { t } from "@/copy/t";
import { formatDate, humanise } from "@/lib/format";
import { laneDef } from "@/lib/lanes";
import { MQ, useMediaQuery } from "@/lib/useMedia";
import { num, obj, str } from "@/lib/unknown";
import { toast } from "@/state/toasts";

function BiasLine({ bias }: { bias: Record<string, unknown> | null | undefined }) {
  if (!bias) return <p className="text-sm text-muted">{t("lens.item.biasNone")}</p>;
  const b = obj(bias);
  const verdict = str(b.verdict);
  const odds = num(b.odds_ratio);
  const explanation = str(b.explanation_md) ?? str(b.explanation);
  const warn = verdict === "bias_suspected" || verdict === "warning";
  return (
    <div className={warn ? "rounded-md bg-warning-bg p-2.5 text-warning-fg" : ""}>
      <p className="flex items-center gap-1.5 text-sm">
        {warn ? <AlertTriangle className="size-4" aria-hidden /> : null}
        {warn ? t("lens.item.biasWarn", { odds: odds !== undefined ? odds.toFixed(2) : "" }) : t("lens.item.biasOk")}
      </p>
      {explanation ? <Markdown source={explanation} className="mt-1 text-sm" /> : null}
    </div>
  );
}

/** Item detail: statement and rationale, exemplars, counter-examples, stats, bias check, triggers, history; owner controls. */
export function ItemSheet({ itemId, onClose, ownerGate, maintainer }: { itemId: string | null; onClose: () => void; ownerGate?: string; maintainer: string }) {
  const item = useLensItem(itemId ?? undefined);
  const qc = useQueryClient();
  const isLg = useMediaQuery(MQ.lg);
  const [editing, setEditing] = useState(false);
  const [wrongOpen, setWrongOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [statement, setStatement] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const d = item.data;

  const patch = async (body: { status?: "active" | "muted"; edits?: Record<string, string>; not_me?: boolean; reason?: string }) => {
    if (!itemId) return;
    setBusy(true);
    setError(null);
    try {
      await call(api.PATCH("/api/v1/lens-items/{item_id}", { params: { path: { item_id: itemId } }, body: { not_me: false, ...body } }));
      void qc.invalidateQueries({ queryKey: ["lens"] });
      toast({ tone: "success", title: t("lens.item.nextAnalysis") });
      setEditing(false);
      setWrongOpen(false);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const muted = d?.status === "muted" || d?.status === "disabled_by_owner";
  return (
    <Sheet open={itemId !== null} onOpenChange={(o) => !o && onClose()} title={d?.title ?? t("lens.item.title")} width="wide" side={isLg ? "right" : "bottom"}>
      <div className="space-y-5 p-4">
        {item.isLoading ? <Skeleton lines={8} /> : null}
        {item.error ? <InlineError error={item.error} onRetry={() => void item.refetch()} /> : null}
        {d ? (
          <>
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              <Pill tone={laneDef(itemLane(d.type)).tone}>{itemTypeLabel(d.type)}</Pill>
              <span className="text-muted">{d.category_label || d.category}</span>
              <Pill tone="outline">{itemStatusLabel(d.status)}</Pill>
              {d.owner_override ? <Pill tone="info">{t("lens.item.override")}</Pill> : null}
            </div>
            <Markdown source={d.statement_md} className="text-base" />
            {d.rationale_md ? (
              <section>
                <h3 className="text-sm font-semibold">{t("lens.item.rationale")}</h3>
                <Markdown source={d.rationale_md} className="text-sm" />
              </section>
            ) : null}
            <SupportMeter support={d.stats.support} precision={d.stats.posterior_mean} ci={d.stats.ci90} />

            <div className="flex flex-wrap gap-2">
              <Tooltip content={ownerGate}>
                <span>
                  <Button size="sm" icon={muted ? Volume2 : VolumeX} disabled={Boolean(ownerGate) || busy} onClick={() => void patch({ status: muted ? "active" : "muted" })}>
                    {muted ? t("lens.item.unmute") : t("lens.item.mute")}
                  </Button>
                </span>
              </Tooltip>
              <Tooltip content={ownerGate}>
                <span>
                  <Button
                    size="sm"
                    icon={Pencil}
                    disabled={Boolean(ownerGate)}
                    onClick={() => {
                      setTitle(d.title);
                      setStatement(d.statement_md);
                      setEditing(true);
                    }}
                  >
                    {t("lens.item.editWording")}
                  </Button>
                </span>
              </Tooltip>
              <Tooltip content={ownerGate}>
                <span>
                  <Button size="sm" variant="danger" icon={Ban} disabled={Boolean(ownerGate)} onClick={() => setWrongOpen(true)}>
                    {t("lens.item.wrong")}
                  </Button>
                </span>
              </Tooltip>
            </div>
            {editing ? (
              <form
                className="k-card space-y-2 p-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  void patch({ edits: { title, statement } });
                }}
              >
                <TextField label={t("lens.item.editTitle")} value={title} onChange={(e) => setTitle(e.target.value)} />
                <TextArea label={t("lens.item.editStatement")} value={statement} onChange={(e) => setStatement(e.target.value)} rows={4} />
                <p className="text-xs text-muted">{t("lens.item.nextAnalysis")}</p>
                <div className="flex gap-2">
                  <Button type="submit" size="sm" variant="primary" loading={busy}>
                    {t("common.save")}
                  </Button>
                  <Button size="sm" onClick={() => setEditing(false)}>
                    {t("common.cancel")}
                  </Button>
                </div>
              </form>
            ) : null}
            {wrongOpen ? (
              <form
                className="k-card space-y-2 p-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  void patch({ not_me: true, status: "muted", reason });
                }}
              >
                <TextArea label={t("lens.item.wrongReason")} value={reason} onChange={(e) => setReason(e.target.value)} rows={2} />
                <p className="text-xs text-muted">{t("lens.item.wrongHelp")}</p>
                <div className="flex gap-2">
                  <Button type="submit" size="sm" variant="danger" loading={busy}>
                    {t("lens.item.wrongConfirm")}
                  </Button>
                  <Button size="sm" onClick={() => setWrongOpen(false)}>
                    {t("common.cancel")}
                  </Button>
                </div>
              </form>
            ) : null}
            {error ? <InlineError error={error} /> : null}

            <section>
              <h3 className="mb-1.5 text-sm font-semibold">{t("lens.item.exemplars", { n: d.exemplars?.length ?? 0, name: maintainer })}</h3>
              {d.exemplars?.length ? (
                <ul className="space-y-3">
                  {d.exemplars.map((ex) => (
                    <li key={ex.finding_id} className="border-l-2 border-edge-border pl-3">
                      <blockquote className="text-sm k-anywhere">{ex.comment_excerpt ?? ex.statement}</blockquote>
                      <p className="mt-0.5 text-xs text-muted">
                        {ex.author ? `${ex.author} · ` : ""}
                        <Link to={`/pr/${ex.pr_number}`} className="text-primary hover:underline">
                          {t("format.prNumber", { n: ex.pr_number })}
                        </Link>
                        {ex.path ? ` · ${ex.path}${ex.line ? `:${ex.line}` : ""}` : ""}
                        {ex.at ? ` · ${formatDate(ex.at)}` : ""}
                      </p>
                      {ex.hunk ? <CodeBlock code={ex.hunk} lang="diff" copy={false} /> : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted">{t("common.none")}</p>
              )}
            </section>

            {d.counter_examples?.length ? (
              <section>
                <h3 className="mb-1 text-sm font-semibold">{t("lens.item.counter")}</h3>
                <p className="flex flex-wrap gap-2 text-sm">
                  {d.counter_examples.map((n) => (
                    <Link key={n} to={`/pr/${n}`} className="text-primary hover:underline">
                      {t("format.prNumber", { n })}
                    </Link>
                  ))}
                </p>
              </section>
            ) : null}

            <section>
              <h3 className="mb-1 text-sm font-semibold">{t("lens.item.stats")}</h3>
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5 text-sm">
                {Object.entries(d.stats)
                  .filter(([, v]) => v !== null && v !== undefined && typeof v !== "object")
                  .map(([k, v]) => (
                    <div key={k} className="contents">
                      <dt className="text-muted">{humanise(k)}</dt>
                      <dd className="tabular">{typeof v === "number" ? (Number.isInteger(v) ? v : v.toFixed(2)) : String(v)}</dd>
                    </div>
                  ))}
              </dl>
            </section>

            <section>
              <h3 className="mb-1 text-sm font-semibold">{t("lens.item.bias")}</h3>
              <BiasLine bias={d.bias as Record<string, unknown> | null | undefined} />
            </section>

            {d.triggers.paths?.length || d.triggers.code_patterns?.length ? (
              <section>
                <h3 className="mb-1 text-sm font-semibold">{t("lens.item.triggers")}</h3>
                <ul className="flex flex-wrap gap-1">
                  {[...(d.triggers.paths ?? []), ...(d.triggers.code_patterns ?? [])].map((x) => (
                    <li key={x}>
                      <code className="rounded-sm bg-surface-2 px-1.5 py-px text-xs">{x}</code>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            {d.history?.length ? (
              <section>
                <h3 className="mb-1 text-sm font-semibold">{t("lens.item.history")}</h3>
                <ol className="space-y-0.5 text-sm text-muted">
                  {d.history.map((h, i) => {
                    const o = obj(h);
                    return (
                      <li key={i}>
                        {num(o.version) !== undefined ? t("lens.versionShort", { v: num(o.version) ?? "" }) : ""} {str(o.change) ?? str(o.status) ?? ""} {str(o.detail) ?? ""}
                      </li>
                    );
                  })}
                </ol>
              </section>
            ) : null}
          </>
        ) : null}
      </div>
    </Sheet>
  );
}
