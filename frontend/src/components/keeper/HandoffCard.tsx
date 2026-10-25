import { useState } from "react";
import { Copy, ExternalLink, ShieldCheck, ShieldAlert, UserRoundSearch } from "lucide-react";
import type { HandoffOut, PersonRef } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Disclosure } from "@/components/ui/Disclosure";
import { Markdown } from "@/components/ui/Markdown";
import { Badge } from "@/components/ui/Badge";
import { t } from "@/copy/t";
import { copyText } from "@/lib/clipboard";
import { personName } from "@/lib/format";
import { toast } from "@/state/toasts";
import { PersonAvatar } from "./PersonAvatar";
import { ProvenanceBadge } from "./Provenance";

function roleLabel(p: PersonRef): string {
  return p.role ? t("people.withRole", { name: personName(p), role: p.role.replace(/_/g, " ") }) : personName(p);
}

/** "Keeper won't guess here": the signals, the suggested reviewer and why, OSV results, the drafted note, the checklist. */
export function HandoffCard({ handoff, primary = true }: { handoff: HandoffOut; primary?: boolean }) {
  const [chosen, setChosen] = useState<PersonRef | null>(handoff.target ?? null);
  const [choosing, setChoosing] = useState(false);
  const target = chosen ?? handoff.target ?? null;
  const targetCandidate = handoff.candidates.find((c) => c.person.id === target?.id);
  const signals = handoff.signals.map((s) => s.label).join(", ");
  const note = (() => {
    if (!handoff.target || !chosen || chosen.id === handoff.target.id) return handoff.note_md;
    return handoff.note_md.split(personName(handoff.target)).join(personName(chosen));
  })();
  return (
    <section className="rounded-md border border-unknown-border bg-unknown-bg/40 p-4 space-y-3" aria-labelledby="handoff-title" data-tour="handoff">
      <div className="flex items-start gap-2">
        <UserRoundSearch className="mt-0.5 size-5 shrink-0 text-unknown-fg" aria-hidden />
        <div className="min-w-0 flex-1">
          <h3 id="handoff-title" className="text-base font-semibold">
            {t("handoff.title")}
          </h3>
          {signals ? <p className="text-sm">{t("handoff.signals", { signals })}</p> : null}
        </div>
        <ProvenanceBadge provenance={handoff.provenance} compact />
      </div>

      {target ? (
        <div className="flex items-start gap-3 rounded-md bg-surface p-3">
          <PersonAvatar personId={target.id} size="lg" />
          <div className="min-w-0 flex-1 text-sm">
            <p>
              {t("handoff.suggested")} <strong className="font-semibold">{roleLabel(target)}</strong>
            </p>
            {targetCandidate?.why.length ? (
              <ul className="mt-1 list-disc pl-4 text-muted">
                {targetCandidate.why.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            ) : null}
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted">{handoff.no_candidate_message ?? t("handoff.noCandidate")}</p>
      )}

      {handoff.candidates.length > 1 ? (
        <Disclosure summary={t("handoff.candidates", { n: Math.min(3, handoff.candidates.length) })} open={choosing} onOpenChange={setChoosing}>
          <ul className="space-y-2">
            {handoff.candidates.slice(0, 3).map((c) => (
              <li key={c.person.id} className="flex items-start gap-2 text-sm">
                <PersonAvatar personId={c.person.id} size="sm" />
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{roleLabel(c.person)}</p>
                  <p className="text-muted">{c.why.join(" · ")}</p>
                </div>
                {target?.id !== c.person.id ? (
                  <Button size="sm" variant="ghost" onClick={() => setChosen(c.person)}>
                    {t("handoff.choose")}
                  </Button>
                ) : (
                  <Badge tone="unknown">{t("handoff.chosen")}</Badge>
                )}
              </li>
            ))}
          </ul>
        </Disclosure>
      ) : null}

      {handoff.osv && handoff.osv.length ? (
        <div className="space-y-1">
          <h4 className="text-sm font-semibold">{t("handoff.osv")}</h4>
          <ul className="space-y-1 text-sm">
            {handoff.osv.map((p) => (
              <li key={`${p.name}@${p.version ?? ""}`} className="flex flex-wrap items-start gap-1.5">
                {p.vulns?.length ? <ShieldAlert className="mt-0.5 size-4 text-danger" aria-hidden /> : <ShieldCheck className="mt-0.5 size-4 text-success" aria-hidden />}
                <span className="font-mono">{p.version ? `${p.name} ${p.version}` : p.name}</span>
                <span className="text-muted">
                  {p.error ? t("handoff.osvError", { error: p.error }) : p.vulns?.length ? t("handoff.osvVulns", { n: p.vulns.length }) : t("handoff.osvNone")}
                </span>
                {p.vulns?.length ? (
                  <ul className="w-full pl-6 text-xs">
                    {p.vulns.map((v) => (
                      <li key={v.id}>
                        {v.url ? (
                          <a href={v.url} target="_blank" rel="noopener noreferrer" className="font-mono text-primary hover:underline">
                            {v.id}
                            <ExternalLink className="ml-0.5 inline size-3" aria-hidden />
                          </a>
                        ) : (
                          <span className="font-mono">{v.id}</span>
                        )}
                        {v.summary ? ` · ${v.summary}` : ""}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : handoff.osv_status && handoff.osv_status !== "ok" ? (
        <p className="text-xs text-muted">{t("handoff.osvStatus", { status: handoff.osv_status })}</p>
      ) : null}

      {handoff.tavily && handoff.tavily.length ? (
        <Disclosure summary={t("handoff.web", { n: handoff.tavily.length })}>
          <ul className="space-y-1 text-sm">
            {handoff.tavily.map((r) => (
              <li key={r.url}>
                <a href={r.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                  {r.title}
                </a>
                {r.snippet ? <p className="text-xs text-muted">{r.snippet}</p> : null}
              </li>
            ))}
          </ul>
        </Disclosure>
      ) : null}

      <div className="space-y-1">
        <h4 className="flex items-center gap-2 text-sm font-semibold">
          {t("handoff.note")}
          <Badge tone="outline">{t("common.drafted")}</Badge>
        </h4>
        <div className="rounded-md border border-border bg-surface p-3">
          <Markdown source={note} className="text-sm" />
        </div>
      </div>

      {handoff.checklist.length ? (
        <div>
          <h4 className="text-sm font-semibold">{t("handoff.checklist")}</h4>
          <ul className="mt-1 list-disc pl-5 text-sm">
            {handoff.checklist.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button
          variant={primary ? "primary" : "secondary"}
          icon={Copy}
          onClick={async () => {
            if (await copyText(note)) toast({ tone: "success", title: t("handoff.copied") });
          }}
        >
          {t("handoff.copyNote")}
        </Button>
        {handoff.candidates.length > 1 ? <Button onClick={() => setChoosing(true)}>{t("handoff.someoneElse")}</Button> : null}
      </div>
    </section>
  );
}
