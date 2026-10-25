import { useEffect } from "react";
import { Link, useSearchParams } from "react-router";
import { Download, MessageSquare, MoreHorizontal, RefreshCw, Scale, Sparkles } from "lucide-react";
import { api, call, downloadWithHeaders, urls } from "@/api/client";
import { useConfirmableAction } from "@/api/hooks/confirm";
import { useJob } from "@/api/hooks/jobs";
import { useLensItems, useLensVersion } from "@/api/hooks/lens";
import { useJobs, useProjectId, useStatus } from "@/api/hooks/system";
import { AnswerHeader } from "@/components/keeper/AnswerHeader";
import { HealthBadge } from "@/components/keeper/HealthBadge";
import { JobProgress } from "@/components/keeper/JobProgress";
import { ProvenanceBadge } from "@/components/keeper/Provenance";
import { PersonAvatar } from "@/components/keeper/PersonAvatar";
import { EmptyState, InlineError, KeyRequired, PageError } from "@/components/keeper/States";
import { Button, buttonClass } from "@/components/ui/Button";
import { IconButton } from "@/components/ui/IconButton";
import { Menu } from "@/components/ui/Menu";
import { SelectField } from "@/components/ui/Field";
import { Delayed, Skeleton } from "@/components/ui/Skeleton";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { Tooltip } from "@/components/ui/Tooltip";
import { t } from "@/copy/t";
import { formatDate, formatMonthYear, personName } from "@/lib/format";
import { num, obj, str } from "@/lib/unknown";
import { ask } from "@/state/ask";
import { toast } from "@/state/toasts";
import { errorMessage } from "@/lib/errors";
import { useGate } from "@/screens/shared/permissions";
import { useActiveLens } from "@/screens/shared/lens";
import { useKeyEnvVar } from "@/shell/AppShell";
import { ItemSheet } from "./ItemSheet";
import { CardTab, ControlsTab, GrowthTab, ItemsTab, MapTab, VersionsTab } from "./tabs";

const TABS = ["card", "items", "map", "versions", "growth", "controls"] as const;
type Tab = (typeof TABS)[number];
const LENS_JOBS = new Set(["learn", "lens_update", "recalibrate"]);

export default function LensScreen() {
  const pid = useProjectId();
  const status = useStatus();
  const envVar = useKeyEnvVar();
  const [params, setParams] = useSearchParams();
  const tab = (TABS as readonly string[]).includes(params.get("tab") ?? "") ? (params.get("tab") as Tab) : "card";
  const itemId = params.get("item");
  const { summary, overview, lenses } = useActiveLens(pid);
  const lens = overview.data;
  const v = Number(params.get("v") ?? "") || lens?.current_version || undefined;
  const version = useLensVersion(lens?.id, v);
  const items = useLensItems(lens?.id, v);
  const jobs = useJobs(false);
  const runningLensJob = (jobs.data?.items ?? []).find((j) => LENS_JOBS.has(j.kind) && ["queued", "running"].includes(j.status) && (str(obj(j.params).lens_id) ?? lens?.id) === lens?.id);
  const ownerGate = useGate({ maintainer: true, ownerId: lens?.person.id ?? null });
  const liveOwnerGate = useGate({ live: true, maintainer: true, ownerId: lens?.person.id ?? null });
  const name = lens ? personName(lens.person) : summary ? personName(summary.person) : "";

  const set = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, val] of Object.entries(patch)) {
      if (val === null || val === "") next.delete(k);
      else next.set(k, val);
    }
    setParams(next, { replace: true });
  };

  const update = useConfirmableAction<void>((_v, token) => call(api.POST("/api/v1/lenses/{lid}/update", { params: { path: { lid: lens!.id } }, body: { confirm_token: token ?? null } })), {
    title: t("lens.update.confirmTitle", { name }),
    description: t("lens.update.confirmBody", { n: lens?.unconsumed_feedback ?? 0 }),
  });
  const rebuild = useConfirmableAction<void>((_v, token) => call(api.POST("/api/v1/lenses/{lid}/rebuild", { params: { path: { lid: lens!.id } }, body: { confirm_token: token ?? null, reason: "manual" } })), {
    title: t("lens.rebuild.confirmTitle", { name }),
    description: t("lens.rebuild.confirmBody"),
  });
  const recalibrate = useConfirmableAction<void>((_v, token) => call(api.POST("/api/v1/lenses/{lid}/recalibrate", { params: { path: { lid: lens!.id } }, body: { confirm_token: token ?? null } })), {
    title: t("lens.recalibrate.confirmTitle"),
    description: t("lens.recalibrate.confirmBody"),
  });
  const activeJobId = update.jobId ?? rebuild.jobId ?? recalibrate.jobId ?? runningLensJob?.id ?? null;
  const activeJob = useJob(activeJobId);

  // After an update, land on Versions with the new version against its parent.
  useEffect(() => {
    if (activeJob?.phase !== "completed") return;
    const ready = [...activeJob.events].reverse().find((e) => e.type === "lens.version.ready");
    const newV = num(obj(ready?.data).version) ?? num(activeJob.result?.version);
    void overview.refetch();
    if (newV) set({ tab: "versions", to: String(newV), from: String(Math.max(1, newV - 1)), v: null, updated: "1" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeJob?.phase]);

  if (!pid || lenses.isLoading || (summary && overview.isLoading))
    return (
      <div className="k-page">
        <Delayed>
          <Skeleton shape="block" className="mb-4 h-16" />
          <Skeleton lines={8} />
        </Delayed>
      </div>
    );
  if (lenses.error) return <PageError error={lenses.error} onRetry={() => void lenses.refetch()} />;
  if (!summary || !lens)
    return (
      <div className="k-page">
        <AnswerHeader title={t("lens.none.title")} />
        <EmptyState
          title={t("lens.none.body")}
          body={t("lens.none.why")}
          action={
            <Link to="/settings?tab=projects" className={buttonClass("primary")}>
              {t("lens.none.import")}
            </Link>
          }
        />
      </div>
    );
  if (overview.error) return <PageError error={overview.error} onRetry={() => void overview.refetch()} />;

  const all = lenses.data?.items ?? [];
  const stats = obj(version.data?.build_stats);
  const prs = num(stats.reviewed_prs) ?? num(stats.prs) ?? num(stats.pulls);
  const from = str(stats.from) ?? str(stats.window_start) ?? str(stats.since);
  const to = str(stats.to) ?? str(stats.window_end) ?? version.data?.cutoff_at;
  const unconsumed = lens.unconsumed_feedback ?? 0;
  const paused = lens.status === "paused";
  const building = Boolean(activeJob && !["completed", "failed", "cancelled"].includes(activeJob.phase));
  const noVersion = lens.versions.length === 0 || lens.current_version === null || lens.current_version === undefined;

  const header = (
    <AnswerHeader
      tour="lens_header"
      title={
        <span className="inline-flex flex-wrap items-center gap-2">
          <PersonAvatar personId={lens.person.id} size="lg" />
          {t("lens.title", { name })}
        </span>
      }
      eyebrow={
        <>
          <HealthBadge state={lens.health_state ?? summary.health_state} href="/lens?tab=growth" />
          {version.data ? <ProvenanceBadge provenance={version.data.provenance} /> : null}
        </>
      }
      subtitle={
        version.data ? (
          <span className="text-sm">
            {prs !== undefined ? t("lens.learnedFrom", { n: prs, from: from ? formatMonthYear(from) : "", to: to ? formatMonthYear(to) : "" }) : t("lens.cutoff", { date: formatDate(version.data.cutoff_at, true) })}
            {version.data.ruler_display ? ` · ${t("lens.ruler", { ruler: version.data.ruler_display })}` : ""}
          </span>
        ) : null
      }
      actions={
        <>
          {all.length > 1 ? (
            <SelectField label={t("lens.person")} hideLabel value={summary.person.id} onChange={(e) => set({ person: e.target.value, v: null, item: null })} options={all.map((l) => ({ value: l.person.id, label: t("lens.title", { name: personName(l.person) }) }))} />
          ) : null}
          {lens.versions.length > 0 ? (
            <SelectField
              label={t("lens.version")}
              hideLabel
              value={String(v ?? "")}
              onChange={(e) => set({ v: e.target.value })}
              options={[...lens.versions].sort((a, b) => b.version - a.version).map((x) => ({ value: String(x.version), label: t("lens.versionOption", { v: x.version, date: formatDate(x.created_at) }) }))}
            />
          ) : null}
          {unconsumed > 0 ? (
            <Tooltip content={liveOwnerGate}>
              <span>
                <Button variant="primary" icon={Sparkles} disabled={Boolean(liveOwnerGate) || building} loading={update.pending} onClick={() => void update.run()}>
                  {t("lens.update.button", { n: unconsumed })}
                </Button>
              </span>
            </Tooltip>
          ) : null}
          <Menu
            label={t("common.more")}
            trigger={<IconButton icon={MoreHorizontal} label={t("common.more")} />}
            items={[
              { key: "rebuild", label: t("lens.rebuild.label"), icon: RefreshCw, onSelect: () => void rebuild.run(), disabled: Boolean(liveOwnerGate), disabledReason: liveOwnerGate },
              { key: "recal", label: t("lens.recalibrate.label"), icon: Scale, onSelect: () => void recalibrate.run(), disabled: Boolean(liveOwnerGate), disabledReason: liveOwnerGate },
              { key: "export", label: t("lens.controls.export"), icon: Download, onSelect: () => void downloadWithHeaders(urls.lensExport(lens.id), `lens-${lens.id}.zip`).catch((e) => toast({ tone: "danger", title: errorMessage(e) })), disabled: Boolean(ownerGate), disabledReason: ownerGate },
              { key: "ask", label: t("lens.ask"), icon: MessageSquare, onSelect: () => ask.open({ screen: "lens", lens_id: lens.id, person_name: name }) },
            ]}
          />
        </>
      }
    />
  );

  const actionErrors = [update, rebuild, recalibrate].map((a, i) =>
    a.keyRequired ? <KeyRequired key={i} what={t("lens.needsKey")} provider={status.data?.provider ?? ""} envVar={envVar} /> : a.error ? <InlineError key={i} error={a.error} /> : null,
  );

  return (
    <div className="k-page mx-auto w-full max-w-[130rem] space-y-5">
      {header}
      {actionErrors}
      {paused ? (
        <div className="flex flex-wrap items-center gap-3 rounded-md border border-warning/50 bg-warning-bg p-3 text-sm text-warning-fg" role="status">
          <span className="flex-1">{t("lens.paused")}</span>
          <Button size="sm" disabled={Boolean(ownerGate)} title={ownerGate} onClick={() => void call(api.POST("/api/v1/lenses/{lid}/resume", { params: { path: { lid: lens.id } } })).then(() => overview.refetch())}>
            {t("lens.controls.resume")}
          </Button>
        </div>
      ) : null}
      {activeJobId && building ? (
        <div className="space-y-1">
          <JobProgress jobId={activeJobId} />
          <p className="text-xs text-muted">{t("lens.building")}</p>
        </div>
      ) : null}
      {noVersion && !building ? (
        <EmptyState
          title={t("lens.noVersion", { name })}
          body={lens.consent ? t("lens.noVersionBody") : t("errors.consent_required", { name })}
          action={
            lens.consent ? (
              <Button variant="primary" disabled={Boolean(liveOwnerGate)} title={liveOwnerGate} onClick={() => void rebuild.run()}>
                {t("lens.build")}
              </Button>
            ) : (
              <Button variant="primary" onClick={() => set({ tab: "controls" })}>
                {t("lens.consent.record")}
              </Button>
            )
          }
        />
      ) : null}
      <Tabs
        value={tab}
        onValueChange={(x) => set({ tab: x === "card" ? null : x, item: null })}
        label={t("lens.tabs.label")}
        tabs={TABS.map((x) => ({ value: x, label: t(`lens.tab.${x}` as "lens.tab.card") }))}
      >
        <TabPanel value="card" className="pt-5">
          {version.isLoading ? <Skeleton lines={6} /> : version.error ? <InlineError error={version.error} /> : version.data ? <CardTab version={version.data} items={items.data?.items ?? []} /> : null}
        </TabPanel>
        <TabPanel value="items" className="pt-5">
          {v !== undefined ? <ItemsTab lensId={lens.id} version={v} onOpen={(id) => set({ item: id })} /> : null}
        </TabPanel>
        <TabPanel value="map" className="pt-5">
          {v !== undefined ? <MapTab lensId={lens.id} version={v} maintainer={name} /> : null}
        </TabPanel>
        <TabPanel value="versions" className="pt-5">
          <VersionsTab lens={lens} current={v ?? 0} />
        </TabPanel>
        <TabPanel value="growth" className="pt-5">
          <GrowthTab lensId={lens.id} personId={lens.person.id} maintainer={name} />
        </TabPanel>
        <TabPanel value="controls" className="pt-5">
          <ControlsTab pid={pid} lens={lens} summary={summary} ownerGate={ownerGate} />
        </TabPanel>
      </Tabs>
      <ItemSheet itemId={itemId} onClose={() => set({ item: null })} ownerGate={ownerGate} maintainer={name} />
    </div>
  );
}
