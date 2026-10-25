import { useState } from "react";
import { Link, useSearchParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Download, Pause, Play, ShieldAlert, Upload } from "lucide-react";
import { api, call, downloadWithHeaders, urls } from "@/api/client";
import { buildHeaders } from "@/api/headers";
import { ApiError } from "@/api/errors";
import { useEdgeMap, useGrowth, useLensAudit, useLensDiff, useLensItems } from "@/api/hooks/lens";
import type { LensItem, LensOverview, LensSummary, LensVersion } from "@/api/types";
import { CellList, EdgeMap, EdgeTopList } from "@/components/keeper/EdgeMap";
import { GrowthTrend } from "@/components/keeper/GrowthTrend";
import { HealthBadge } from "@/components/keeper/HealthBadge";
import { LensDiffView } from "@/components/keeper/LensDiffView";
import { LensItemCard, LensItemChip } from "@/components/keeper/LensItem";
import { EmptyState, InlineError } from "@/components/keeper/States";
import { Badge } from "@/components/ui/Badge";
import { Button, buttonClass } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Checkbox, SelectField, TextField } from "@/components/ui/Field";
import { Markdown } from "@/components/ui/Markdown";
import { RelativeTime } from "@/components/ui/Formatted";
import { Skeleton } from "@/components/ui/Skeleton";
import { Tooltip } from "@/components/ui/Tooltip";
import { t, tDynamic } from "@/copy/t";
import { formatDate, formatInterval, formatPercent, humanise } from "@/lib/format";
import { indexCards, prepareMarkers } from "@/lib/markers";
import { num, obj, str } from "@/lib/unknown";
import { toast } from "@/state/toasts";

/** The confirmation word for revoking a lens (an API contract value, shown in the copy as a variable). */
export const REVOKE_WORD = "REVOKE";

export function KeyFacts({ version }: { version: LensVersion }) {
  const facts = obj(version.key_facts);
  const precision = obj(facts.precision);
  const counts = Object.entries(version.items_count ?? {});
  const lastConfirmed = str(facts.last_confirmed_at) ?? str(facts.last_confirmed);
  return (
    <dl className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(min(100%,14rem),1fr))]">
      <div className="k-card p-3">
        <dt className="text-xs text-muted">{t("lens.facts.items")}</dt>
        <dd className="mt-1 text-sm">
          {counts.length ? counts.map(([k, v]) => <span key={k} className="mr-3 inline-block">{t("lens.facts.itemCount", { n: v, type: tDynamic(`lens.itemType.${k}`) || humanise(k) })}</span>) : t("format.none")}
        </dd>
      </div>
      <div className="k-card p-3">
        <dt className="text-xs text-muted">{t("lens.facts.precision")}</dt>
        <dd className="mt-1 text-lg font-semibold tabular">
          {num(precision.value) !== undefined ? formatPercent(num(precision.value)) : num(facts.precision) !== undefined ? formatPercent(num(facts.precision)) : t("format.none")}{" "}
          <span className="text-sm font-normal text-muted">{formatInterval(num(precision.low), num(precision.high))}</span>
        </dd>
      </div>
      <div className="k-card p-3">
        <dt className="text-xs text-muted">{t("lens.facts.lastConfirmed")}</dt>
        <dd className="mt-1 text-sm">{lastConfirmed ? <RelativeTime at={lastConfirmed} /> : t("format.none")}</dd>
      </div>
    </dl>
  );
}

export function CardTab({ version, items }: { version: LensVersion; items: LensItem[] }) {
  const cards = indexCards(items.map((i) => ({ type: "lens_item" as const, data: { id: i.id, title: i.title, support: i.stats.support, kind: i.type } })));
  return (
    <div className="space-y-5">
      <div className="k-card p-4">
        <Markdown
          source={prepareMarkers(version.card_md, cards, true)}
          className="text-base"
          renderCitation={(type, id) => {
            const it = items.find((x) => x.id === id);
            return type === "lens_item" && it ? <LensItemChip item={{ id: it.id, title: it.title, support: it.stats.support }} lane={it.type === "blind_spot" ? "blind_spot" : "edge"} /> : null;
          }}
        />
      </div>
      <KeyFacts version={version} />
    </div>
  );
}

export function ItemsTab({ lensId, version, onOpen }: { lensId: string; version: number; onOpen: (id: string) => void }) {
  const [params, setParams] = useSearchParams();
  const f = { type: params.get("type") ?? "", category: params.get("category") ?? "", status: params.get("status") ?? "", q: params.get("q") ?? "" };
  const items = useLensItems(lensId, version, f);
  const all = useLensItems(lensId, version);
  const set = (k: string, v: string) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v);
    else next.delete(k);
    setParams(next, { replace: true });
  };
  const categories = [...new Map((all.data?.items ?? []).map((i) => [i.category, i.category_label || i.category])).entries()];
  const types = [...new Set((all.data?.items ?? []).map((i) => i.type))];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <SelectField label={t("lens.filter.type")} value={f.type} onChange={(e) => set("type", e.target.value)} options={[{ value: "", label: t("lens.filter.any") }, ...types.map((x) => ({ value: x, label: tDynamic(`lens.itemType.${x}`) || x }))]} />
        <SelectField label={t("lens.filter.category")} value={f.category} onChange={(e) => set("category", e.target.value)} options={[{ value: "", label: t("lens.filter.any") }, ...categories.map(([value, label]) => ({ value, label }))]} />
        <SelectField
          label={t("lens.filter.status")}
          value={f.status}
          onChange={(e) => set("status", e.target.value)}
          options={[{ value: "", label: t("lens.filter.any") }, ...["active", "muted", "low_confidence"].map((x) => ({ value: x, label: tDynamic(`lens.itemStatus.${x}`) }))]}
        />
        <TextField label={t("lens.filter.search")} type="search" data-shortcut="search" value={f.q} onChange={(e) => set("q", e.target.value)} className="flex-[1_1_14rem]" />
      </div>
      {items.isLoading ? <Skeleton lines={6} /> : null}
      {items.error ? <InlineError error={items.error} onRetry={() => void items.refetch()} /> : null}
      {items.data && items.data.items.length === 0 ? <EmptyState compact title={t("lens.items.none")} /> : null}
      <div className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(min(100%,22rem),1fr))]">
        {(items.data?.items ?? []).map((it) => (
          <LensItemCard key={it.id} item={it} onOpen={onOpen} />
        ))}
      </div>
    </div>
  );
}

export function MapTab({ lensId, version, maintainer }: { lensId: string; version: number; maintainer: string }) {
  const map = useEdgeMap(lensId, version);
  const [full, setFull] = useState(false);
  if (map.isLoading) return <Skeleton lines={8} />;
  if (map.error) return <InlineError error={map.error} onRetry={() => void map.refetch()} />;
  const m = map.data!;
  return (
    <div className="space-y-5">
      {m.summary_md ? <Markdown source={m.summary_md} className="text-base" /> : null}
      <div className="grid gap-6 [grid-template-columns:repeat(auto-fit,minmax(min(100%,26rem),1fr))]">
        <section aria-labelledby="edge-top">
          <h2 id="edge-top" className="mb-2 text-lg font-semibold">
            {t("edge.topTitle", { name: maintainer })}
          </h2>
          <EdgeTopList cells={m.top} maintainer={maintainer} />
        </section>
        <div className="space-y-5">
          <section aria-labelledby="edge-enough">
            <h2 id="edge-enough" className="mb-2 text-lg font-semibold">
              {t("edge.enoughTitle")}
            </h2>
            <CellList cells={m.enough} kind="enough" empty={t("edge.enoughNone")} />
          </section>
          <section aria-labelledby="edge-gaps">
            <h2 id="edge-gaps" className="mb-2 text-lg font-semibold">
              {t("edge.gapsTitle")}
            </h2>
            <CellList cells={m.gaps} kind="gap" empty={t("edge.gapsNone")} />
          </section>
        </div>
      </div>
      <Button onClick={() => setFull((v) => !v)} aria-expanded={full}>
        {full ? t("edge.hideMap") : t("edge.showMap")}
      </Button>
      {full ? <EdgeMap map={m} /> : null}
    </div>
  );
}

export function VersionsTab({ lens, current }: { lens: LensOverview; current: number }) {
  const [params, setParams] = useSearchParams();
  const versions = [...lens.versions].sort((a, b) => b.version - a.version);
  const latest = versions[0]?.version ?? current;
  const from = Number(params.get("from") ?? versions[1]?.version ?? latest);
  const to = Number(params.get("to") ?? latest);
  const diff = useLensDiff(lens.id, from, to);
  const justUpdated = params.get("updated") === "1";
  const set = (k: string, v: string) => {
    const next = new URLSearchParams(params);
    next.set(k, v);
    next.delete("updated");
    setParams(next, { replace: true });
  };
  return (
    <div className="space-y-5">
      {justUpdated ? <p className="rounded-md bg-success-bg p-3 text-sm text-success-fg">{t("lens.versions.nowActive", { v: to })}</p> : null}
      <ol className="space-y-2">
        {versions.map((v) => (
          <li key={v.version} className="k-card flex flex-wrap items-baseline gap-x-3 gap-y-1 p-3 text-sm">
            <span className="font-semibold">{t("lens.versionShort", { v: v.version })}</span>
            <span className="text-muted">{formatDate(v.created_at, true)}</span>
            <span>{v.change_reason}</span>
            {v.counts ? (
              <span className="text-muted tabular">
                {t("lens.versions.counts", { added: v.counts.added ?? 0, removed: v.counts.removed ?? 0, changed: v.counts.changed ?? 0 })}
              </span>
            ) : null}
            {v.origin === "snapshot" ? <Badge>{t("common.saved_run")}</Badge> : null}
            {v.version === lens.current_version ? <Badge tone="success">{t("lens.versions.active")}</Badge> : null}
          </li>
        ))}
      </ol>
      {versions.length > 1 ? (
        <section className="space-y-3" aria-labelledby="lens-compare">
          <h2 id="lens-compare" className="text-lg font-semibold">
            {t("lens.versions.compare")}
          </h2>
          <div className="flex flex-wrap gap-3">
            <SelectField label={t("lens.versions.from")} value={String(from)} onChange={(e) => set("from", e.target.value)} options={versions.map((v) => ({ value: String(v.version), label: t("lens.versionShort", { v: v.version }) }))} />
            <SelectField label={t("lens.versions.to")} value={String(to)} onChange={(e) => set("to", e.target.value)} options={versions.map((v) => ({ value: String(v.version), label: t("lens.versionShort", { v: v.version }) }))} />
          </div>
          {from === to ? <p className="text-sm text-muted">{t("lens.versions.same")}</p> : null}
          {diff.isLoading ? <Skeleton lines={5} /> : null}
          {diff.error ? <InlineError error={diff.error} onRetry={() => void diff.refetch()} /> : null}
          {diff.data ? <LensDiffView diff={diff.data} /> : null}
        </section>
      ) : (
        <p className="text-sm text-muted">{t("lens.versions.single")}</p>
      )}
    </div>
  );
}

export function GrowthTab({ lensId, personId, maintainer }: { lensId: string; personId: string; maintainer: string }) {
  const growth = useGrowth(lensId);
  if (growth.isLoading) return <Skeleton lines={6} />;
  if (growth.error) return <InlineError error={growth.error} onRetry={() => void growth.refetch()} />;
  const g = growth.data!;
  return (
    <div className="space-y-5">
      <section className="k-card space-y-2 p-4">
        <HealthBadge state={g.health_state} />
        {g.health_state === "insufficient_data" ? <p className="text-sm">{t("growth.insufficient")}</p> : null}
        <Markdown source={g.explanation_md} className="text-sm" />
      </section>
      <GrowthTrend snapshots={g.snapshots} />
      {g.g_examples?.length ? (
        <section>
          <h2 className="mb-2 text-lg font-semibold">{t("growth.examples", { name: maintainer })}</h2>
          <ul className="space-y-1.5 text-sm">
            {g.g_examples.map((f) => (
              <li key={f.id} className="k-card p-2.5">
                <p className="font-medium">{f.title}</p>
                <p className="text-muted">{f.statement}</p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <p className="text-sm">
        <Link to={`/practice?learner=${encodeURIComponent(personId)}`} className="text-primary hover:underline">
          {t("growth.practiceLink")}
        </Link>
      </p>
    </div>
  );
}

function ConsentDialog({ open, onOpenChange, pid, personId, login }: { open: boolean; onOpenChange: (o: boolean) => void; pid: string; personId: string; login: string }) {
  const qc = useQueryClient();
  const [scope, setScope] = useState<"build_lens" | "evaluation_only" | "share_in_project">("build_lens");
  const [attest, setAttest] = useState(false);
  const [typed, setTyped] = useState("");
  const [error, setError] = useState<unknown>(null);
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={t("lens.consent.recordTitle")}
      description={t("lens.consent.recordBody")}
      footer={
        <>
          <Button onClick={() => onOpenChange(false)}>{t("common.cancel")}</Button>
          <Button
            variant="primary"
            disabled={!attest || typed !== login}
            onClick={async () => {
              try {
                await call(api.POST("/api/v1/projects/{pid}/people/{person_id}/consent", { params: { path: { pid, person_id: personId } }, body: { scope, attest, typed_login: typed } }));
                void qc.invalidateQueries({ queryKey: ["lens"] });
                void qc.invalidateQueries({ queryKey: ["people"] });
                onOpenChange(false);
              } catch (e) {
                setError(e);
              }
            }}
          >
            {t("lens.consent.record")}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <SelectField
          label={t("lens.consent.scope")}
          value={scope}
          onChange={(e) => setScope(e.target.value as typeof scope)}
          options={["build_lens", "evaluation_only", "share_in_project"].map((s) => ({ value: s, label: tDynamic(`lens.consent.scope.${s}`) }))}
        />
        <TextField label={t("lens.consent.typeLogin", { login })} value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
        <Checkbox checked={attest} onCheckedChange={setAttest} label={t("lens.consent.attest")} />
        {error ? <InlineError error={error} /> : null}
      </div>
    </Dialog>
  );
}

export function ControlsTab({ pid, lens, summary, ownerGate }: { pid: string; lens: LensOverview; summary?: LensSummary; ownerGate?: string }) {
  const qc = useQueryClient();
  const audit = useLensAudit(lens.id);
  const [revokeOpen, setRevokeOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [consentOpen, setConsentOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const paused = lens.status === "paused";
  const revoked = lens.status === "revoked";

  const act = async (name: string, fn: () => Promise<unknown>) => {
    setBusy(name);
    setError(null);
    try {
      await fn();
      void qc.invalidateQueries({ queryKey: ["lens"] });
      void qc.invalidateQueries({ queryKey: ["queue"] });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(null);
    }
  };

  const importPackage = async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    await act("import", async () => {
      const res = await fetch(`/api/v1/projects/${encodeURIComponent(pid)}/lenses/import`, { method: "POST", body: form, headers: buildHeaders("POST"), credentials: "same-origin" });
      if (!res.ok) throw ApiError.fromBody(res.status, await res.json().catch(() => null), res.headers.get("x-request-id"));
      toast({ tone: "success", title: t("lens.controls.imported") });
    });
  };

  const c = lens.consent;
  return (
    <div className="space-y-6">
      <section className="k-card space-y-2 p-4" aria-labelledby="consent-h">
        <h2 id="consent-h" className="text-lg font-semibold">
          {t("lens.consent.title")}
        </h2>
        {c ? (
          <p className="text-sm">
            {t("lens.consent.granted", { by: c.granted_by, date: formatDate(c.granted_at, true), scope: tDynamic(`lens.consent.scope.${c.scope}`) || c.scope, version: c.text_version })}
            {c.synthetic ? ` ${t("lens.consent.synthetic")}` : ""}
            {c.revoked_at ? ` ${t("lens.consent.revoked", { date: formatDate(c.revoked_at, true) })}` : ""}
          </p>
        ) : (
          <p className="text-sm text-muted">{t("lens.consent.none")}</p>
        )}
        {!lens.fictional ? (
          <Button size="sm" disabled={Boolean(ownerGate)} title={ownerGate} onClick={() => setConsentOpen(true)}>
            {t("lens.consent.record")}
          </Button>
        ) : null}
        <p className="text-sm text-muted">{summary?.shared_in_project ? t("lens.sharing.on") : t("lens.sharing.off")}</p>
      </section>

      <section className="k-card space-y-3 p-4" aria-labelledby="controls-h">
        <h2 id="controls-h" className="text-lg font-semibold">
          {t("lens.controls.title")}
        </h2>
        <div className="flex flex-wrap gap-2">
          <Tooltip content={ownerGate}>
            <span>
              {paused ? (
                <Button icon={Play} disabled={Boolean(ownerGate) || revoked} loading={busy === "resume"} onClick={() => void act("resume", () => call(api.POST("/api/v1/lenses/{lid}/resume", { params: { path: { lid: lens.id } } })))}>
                  {t("lens.controls.resume")}
                </Button>
              ) : (
                <Button icon={Pause} disabled={Boolean(ownerGate) || revoked} loading={busy === "pause"} onClick={() => void act("pause", () => call(api.POST("/api/v1/lenses/{lid}/pause", { params: { path: { lid: lens.id } } })))}>
                  {t("lens.controls.pause")}
                </Button>
              )}
            </span>
          </Tooltip>
          {ownerGate ? (
            <Tooltip content={ownerGate}>
              <span>
                <Button icon={Download} disabled>
                  {t("lens.controls.export")}
                </Button>
              </span>
            </Tooltip>
          ) : (
            <Button icon={Download} loading={busy === "export"} onClick={() => void act("export", () => downloadWithHeaders(urls.lensExport(lens.id), `lens-${lens.id}.zip`))}>
              {t("lens.controls.export")}
            </Button>
          )}
          <label className={buttonClass("secondary", "md", ownerGate ? "pointer-events-none opacity-55" : undefined)}>
            <Upload className="size-4" aria-hidden />
            {t("lens.controls.import")}
            <input
              type="file"
              accept=".zip,.json,application/zip,application/json"
              className="sr-only"
              disabled={Boolean(ownerGate)}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void importPackage(f);
                e.target.value = "";
              }}
            />
          </label>
        </div>
        <p className="text-xs text-muted">{t("lens.controls.pauseHelp")}</p>
        {error ? <InlineError error={error} /> : null}
      </section>

      <section className="space-y-2 rounded-md border border-danger/50 p-4" aria-labelledby="danger-h">
        <h2 id="danger-h" className="flex items-center gap-2 text-lg font-semibold text-danger-fg">
          <ShieldAlert className="size-5" aria-hidden />
          {t("lens.revoke.title")}
        </h2>
        <p className="text-sm">{t("lens.revoke.body")}</p>
        <Tooltip content={ownerGate}>
          <span>
            <Button variant="danger" disabled={Boolean(ownerGate) || revoked} onClick={() => setRevokeOpen(true)}>
              {t("lens.revoke.button")}
            </Button>
          </span>
        </Tooltip>
      </section>

      <section aria-labelledby="audit-h">
        <h2 id="audit-h" className="mb-2 text-lg font-semibold">
          {t("lens.audit.title")}
        </h2>
        {audit.isLoading ? <Skeleton lines={4} /> : null}
        {audit.error ? <InlineError error={audit.error} /> : null}
        <ol className="divide-y divide-border rounded-md border border-border text-sm">
          {(audit.data?.items ?? []).slice(0, 50).map((a, i) => (
            <li key={i} className="flex flex-wrap gap-x-3 px-3 py-2">
              <span className="text-muted tabular">{formatDate(a.at, true)}</span>
              <span className="font-medium">{humanise(a.action)}</span>
              <span className="text-muted">{a.actor_role}</span>
              {Object.keys(a.details ?? {}).length ? <span className="font-mono text-xs text-muted k-anywhere">{JSON.stringify(a.details)}</span> : null}
            </li>
          ))}
          {audit.data && audit.data.items.length === 0 ? <li className="px-3 py-2 text-muted">{t("lens.audit.none")}</li> : null}
        </ol>
      </section>

      <Dialog
        open={revokeOpen}
        onOpenChange={(o) => {
          setRevokeOpen(o);
          if (!o) setTyped("");
        }}
        role="alertdialog"
        title={t("lens.revoke.confirmTitle")}
        description={t("lens.revoke.confirmBody", { word: REVOKE_WORD })}
        footer={
          <>
            <Button onClick={() => setRevokeOpen(false)}>{t("common.cancel")}</Button>
            <Button
              variant="danger"
              disabled={typed !== REVOKE_WORD}
              loading={busy === "revoke"}
              onClick={() =>
                void act("revoke", async () => {
                  await call(api.POST("/api/v1/lenses/{lid}/revoke", { params: { path: { lid: lens.id } }, body: { confirm: typed } }));
                  setRevokeOpen(false);
                  setTyped("");
                })
              }
            >
              {t("lens.revoke.button")}
            </Button>
          </>
        }
      >
        <TextField label={t("lens.revoke.type", { word: REVOKE_WORD })} value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
      </Dialog>
      <ConsentDialog open={consentOpen} onOpenChange={setConsentOpen} pid={pid} personId={lens.person.id} login={lens.owner_login ?? lens.person.login} />
    </div>
  );
}
