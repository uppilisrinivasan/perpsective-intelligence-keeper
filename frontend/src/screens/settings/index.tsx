import { useState } from "react";
import { useSearchParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleMinus, CircleX, RefreshCw, RotateCcw, Trash2, Upload } from "lucide-react";
import { api, call, urls } from "@/api/client";
import { useConfirmableAction } from "@/api/hooks/confirm";
import { patchSettings, resetSettings, useSettings, useUsage, type UsageGroup, type UsagePeriod } from "@/api/hooks/settings";
import { useProjects, useStatus } from "@/api/hooks/system";
import { keys } from "@/api/keys";
import type { EditableSetting, UsageRow } from "@/api/types";
import { AnswerHeader } from "@/components/keeper/AnswerHeader";
import { JobProgress } from "@/components/keeper/JobProgress";
import { ProgressBar } from "@/components/keeper/JobProgress";
import { InlineError, KeyHowTo, PageError } from "@/components/keeper/States";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Checkbox, SelectField, Switch, TextField } from "@/components/ui/Field";
import { Segmented } from "@/components/ui/Segmented";
import { Skeleton } from "@/components/ui/Skeleton";
import { TabPanel, Tabs } from "@/components/ui/Tabs";
import { t, tDynamic } from "@/copy/t";
import { formatDate, formatDateTime, formatMoney, formatNumber, humanise } from "@/lib/format";
import { setPref, usePrefs } from "@/state/prefs";
import { useGate } from "@/screens/shared/permissions";
import { useKeyEnvVar } from "@/shell/AppShell";

const TABS = ["models", "usage", "sandbox", "projects", "preferences", "about"] as const;

function ProbeChip({ name, value }: { name: string; value: string | undefined }) {
  const v = (value ?? "n/a").toLowerCase();
  const ok = v === "ok" || v === "yes" || v === "true";
  const bad = v === "fail" || v === "no" || v === "false" || v === "error";
  return (
    <Badge tone={ok ? "success" : bad ? "danger" : "neutral"} icon={ok ? CheckCircle2 : bad ? CircleX : CircleMinus}>
      {tDynamic(`settings.probe.${name}`) || humanise(name)}
    </Badge>
  );
}

function ModelsTab() {
  const status = useStatus();
  const settings = useSettings();
  const envVar = useKeyEnvVar();
  const gate = useGate({ maintainer: true });
  const probe = useConfirmableAction<void>(() => call(api.POST("/api/v1/settings/probe")), { title: t("settings.models.check") });
  const s = status.data;
  if (!s) return <Skeleton lines={5} />;
  const configured = Object.entries(settings.data?.secrets ?? {}).find(([k]) => k.endsWith("_api_key"))?.[1]?.configured ?? s.live;
  return (
    <div className="space-y-4">
      <section className="k-card space-y-2 p-4">
        <h2 className="text-lg font-semibold">{t("settings.models.provider")}</h2>
        {configured ? (
          <p className="flex items-center gap-2 text-sm">
            <CheckCircle2 className="size-4 text-success" aria-hidden />
            {t("settings.models.keyOk", { provider: s.provider })}
          </p>
        ) : (
          <div className="space-y-2 text-sm">
            <p>{t("key.noKey")}</p>
            <KeyHowTo provider={s.provider} envVar={envVar} />
          </div>
        )}
        <p className="text-xs text-muted">{t("settings.models.keysNote")}</p>
      </section>
      <ul className="space-y-3">
        {s.models.map((m) => (
          <li key={m.role} className="k-card space-y-2 p-4">
            <div className="flex flex-wrap items-baseline gap-x-3">
              <h3 className="font-semibold">{tDynamic(`settings.role.${m.role}`) || m.purpose || humanise(m.role)}</h3>
              <span className="text-sm">{m.display}</span>
              <code className="text-xs text-muted k-anywhere">{m.model_id}</code>
            </div>
            {m.purpose ? <p className="text-sm text-muted">{m.purpose}</p> : null}
            <div className="flex flex-wrap gap-1.5">
              {(["exists", "chat", "json_schema", "json_object", "reasoning", "tools"] as const).map((k) => (
                <ProbeChip key={k} name={k} value={m.probe[k]} />
              ))}
            </div>
            {m.fallback_active ? <p className="text-sm text-warning-fg">{t("settings.models.fallback", { fallback: m.fallback_model ?? "" })}</p> : null}
          </li>
        ))}
      </ul>
      <Button icon={RefreshCw} disabled={Boolean(gate) || !s.live} title={gate ?? (!s.live ? t("common.needsKey") : undefined)} loading={probe.pending} onClick={() => void probe.run()}>
        {t("settings.models.check")}
      </Button>
      {probe.jobId ? <JobProgress jobId={probe.jobId} compact /> : null}
      {probe.error ? <InlineError error={probe.error} /> : null}
      <p className="text-xs text-muted">{t("settings.models.changeNote")}</p>
    </div>
  );
}

function UsageTable({ rows, label, keyLabel }: { rows: UsageRow[]; label: string; keyLabel: (k: string) => string }) {
  if (!rows.length) return <p className="text-sm text-muted">{t("settings.usage.none")}</p>;
  return (
    <div className="@container">
      <table className="hidden w-full text-sm @md:table" aria-label={label}>
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted">
            <th scope="col" className="py-1.5 font-medium">{label}</th>
            <th scope="col" className="py-1.5 text-right font-medium">{t("settings.usage.calls")}</th>
            <th scope="col" className="py-1.5 text-right font-medium">{t("settings.usage.tokens")}</th>
            <th scope="col" className="py-1.5 text-right font-medium">{t("settings.usage.cost")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className="border-b border-border">
              <th scope="row" className="py-1.5 text-left font-normal">{keyLabel(r.key)}</th>
              <td className="py-1.5 text-right tabular">{formatNumber(r.calls)}</td>
              <td className="py-1.5 text-right tabular">{formatNumber(r.input_tokens + r.output_tokens)}</td>
              <td className="py-1.5 text-right tabular">{formatMoney(r.cost_usd, true)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <ul className="space-y-2 @md:hidden" aria-label={label}>
        {rows.map((r) => (
          <li key={r.key} className="rounded-md border border-border p-2.5 text-sm">
            <p className="font-medium">{keyLabel(r.key)}</p>
            <p className="text-muted tabular">{t("settings.usage.card", { calls: formatNumber(r.calls), tokens: formatNumber(r.input_tokens + r.output_tokens), cost: formatMoney(r.cost_usd, true) })}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function UsageTab() {
  const [period, setPeriod] = useState<UsagePeriod>("month");
  const feature = useUsage(period, "feature");
  const model = useUsage(period, "model");
  const day = useUsage(period, "day");
  const settings = useSettings();
  const cap = feature.data?.cap;
  const auto = settings.data?.editable.find((e) => e.key === "auto_approve_usd");
  const maxDay = Math.max(...(day.data?.rows ?? []).map((r) => r.cost_usd), 0.0001);
  return (
    <div className="space-y-5">
      <Segmented
        label={t("settings.usage.period")}
        value={period}
        onChange={(v) => setPeriod(v as UsagePeriod)}
        options={(["day", "month", "total"] as const).map((p) => ({ value: p, label: tDynamic(`settings.usage.period.${p}`) }))}
      />
      {feature.error ? <InlineError error={feature.error} onRetry={() => void feature.refetch()} /> : null}
      {cap ? (
        <section className="k-card space-y-2 p-4" aria-labelledby="spend-h">
          <h2 id="spend-h" className="text-lg font-semibold">{t("settings.usage.spend")}</h2>
          <ProgressBar value={cap.cap_usd > 0 ? cap.used_usd / cap.cap_usd : 0} label={t("settings.usage.spendAria")} tone={cap.reached ? "danger" : cap.used_usd / Math.max(cap.cap_usd, 0.0001) > 0.8 ? "warning" : "primary"} />
          <p className="text-sm tabular">{t("settings.usage.spendLine", { used: formatMoney(cap.used_usd), cap: formatMoney(cap.cap_usd), period: cap.period })}</p>
          {cap.resets_at ? <p className="text-xs text-muted">{t("settings.usage.resets", { date: formatDateTime(cap.resets_at) })}</p> : null}
        </section>
      ) : null}
      <section className="space-y-2" aria-labelledby="by-feature">
        <h2 id="by-feature" className="text-lg font-semibold">{t("settings.usage.byFeature")}</h2>
        {feature.isLoading ? <Skeleton lines={4} /> : <UsageTable rows={feature.data?.rows ?? []} label={t("settings.usage.feature")} keyLabel={(k) => tDynamic(`settings.feature.${k}`) || humanise(k)} />}
        {feature.data?.snapshot_rows?.length ? (
          <>
            <h3 className="pt-2 text-sm font-semibold">{t("settings.usage.snapshot")}</h3>
            <UsageTable rows={feature.data.snapshot_rows} label={t("settings.usage.feature")} keyLabel={(k) => tDynamic(`settings.feature.${k}`) || humanise(k)} />
          </>
        ) : null}
      </section>
      <section className="space-y-2" aria-labelledby="by-model">
        <h2 id="by-model" className="text-lg font-semibold">{t("settings.usage.byModel")}</h2>
        {model.isLoading ? <Skeleton lines={3} /> : <UsageTable rows={model.data?.rows ?? []} label={t("settings.usage.model")} keyLabel={(k) => k} />}
      </section>
      <section className="space-y-2" aria-labelledby="by-day">
        <h2 id="by-day" className="text-lg font-semibold">{t("settings.usage.byDay")}</h2>
        <ul className="space-y-1">
          {(day.data?.rows ?? []).map((r) => (
            <li key={r.key} className="grid grid-cols-[minmax(6rem,8rem)_1fr_minmax(4rem,auto)] items-center gap-2 text-sm">
              <span className="text-muted">{formatDate(r.key)}</span>
              <span className="h-2 rounded-full bg-primary" style={{ width: `${(r.cost_usd / maxDay) * 100}%` }} aria-hidden />
              <span className="text-right tabular">{formatMoney(r.cost_usd, true)}</span>
            </li>
          ))}
        </ul>
      </section>
      {auto ? <EditableRow setting={auto} /> : null}
    </div>
  );
}

function SandboxTab() {
  const status = useStatus();
  const settings = useSettings();
  const gate = useGate({ maintainer: true });
  const check = useConfirmableAction<void>(() => call(api.POST("/api/v1/settings/sandbox-check")), { title: t("settings.sandbox.check") });
  const sb = status.data?.sandbox;
  if (!sb) return <Skeleton lines={4} />;
  const readonly = settings.data?.readonly ?? {};
  const recipe = (readonly as Record<string, unknown>).test_recipe ?? (readonly as Record<string, unknown>).sandbox_recipe;
  return (
    <div className="space-y-4">
      <section className="k-card space-y-2 p-4">
        <h2 className="text-lg font-semibold">{t("settings.sandbox.provider", { provider: sb.provider })}</h2>
        {sb.provider !== sb.requested ? <p className="text-sm text-warning-fg">{t("settings.sandbox.fallback", { requested: sb.requested, reason: sb.reason ?? "" })}</p> : sb.reason ? <p className="text-sm text-muted">{sb.reason}</p> : null}
        <p className="text-sm">{t("settings.sandbox.isolation", { isolation: sb.isolation })}</p>
        {recipe ? <pre className="overflow-x-auto rounded-md bg-surface-2 p-2 font-mono text-xs">{typeof recipe === "string" ? recipe : JSON.stringify(recipe, null, 2)}</pre> : null}
      </section>
      <Button disabled={Boolean(gate)} title={gate} loading={check.pending} onClick={() => void check.run()}>
        {t("settings.sandbox.check")}
      </Button>
      {check.jobId ? <JobProgress jobId={check.jobId} /> : null}
      {check.error ? <InlineError error={check.error} /> : null}
    </div>
  );
}

function ProjectsTab() {
  const projects = useProjects();
  const status = useStatus();
  const qc = useQueryClient();
  const gate = useGate({ maintainer: true });
  const [url, setUrl] = useState("");
  const [login, setLogin] = useState("");
  const [since, setSince] = useState("");
  const [maxPulls, setMaxPulls] = useState("");
  const [ack, setAck] = useState(false);
  const [del, setDel] = useState<string | null>(null);
  const [delError, setDelError] = useState<unknown>(null);
  const importAction = useConfirmableAction<void>(
    (_v, token) =>
      call(
        api.POST("/api/v1/projects/import", {
          body: { repo_url: url, maintainer_login: login || null, since: since || null, max_pulls: maxPulls ? Number(maxPulls) : null, consent_ack: ack, confirm_token: token ?? null },
        }),
      ),
    { title: t("settings.import.confirmTitle"), description: t("settings.import.confirmBody") },
  );
  const allowed = status.data?.import_allowed !== false;
  return (
    <div className="space-y-5">
      <ul className="space-y-2">
        {(projects.data?.items ?? []).map((p) => (
          <li key={p.id} className="k-card flex flex-wrap items-center gap-3 p-3 text-sm">
            <span className="font-mono font-medium">{t("shell.project", { owner: p.owner, repo: p.repo })}</span>
            {p.id === status.data?.default_project_id ? <Badge tone="success">{t("settings.projects.active")}</Badge> : null}
            {p.fictional ? <Badge tone="outline">{t("shell.demoWorld")}</Badge> : null}
            <span className="text-muted">{t("settings.projects.counts", { pulls: p.counts.pulls ?? 0, open: p.counts.open ?? 0, reviewers: p.counts.reviewers ?? 0 })}</span>
            {p.kind !== "demo" ? (
              <Button size="sm" variant="danger" icon={Trash2} className="ml-auto" disabled={Boolean(gate)} title={gate} onClick={() => setDel(p.id)}>
                {t("settings.projects.delete")}
              </Button>
            ) : null}
          </li>
        ))}
      </ul>
      <section className="k-card space-y-3 p-4" aria-labelledby="import-h">
        <h2 id="import-h" className="text-lg font-semibold">{t("settings.import.title")}</h2>
        {!allowed ? <p className="text-sm text-muted">{t("settings.import.notAllowed")}</p> : null}
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            void importAction.run();
          }}
        >
          <div className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(min(100%,16rem),1fr))]">
            <TextField label={t("settings.import.url")} value={url} onChange={(e) => setUrl(e.target.value)} required type="url" inputMode="url" />
            <TextField label={t("settings.import.login")} hint={t("settings.import.loginHint")} value={login} onChange={(e) => setLogin(e.target.value)} />
            <TextField label={t("settings.import.since")} type="date" value={since} onChange={(e) => setSince(e.target.value)} />
            <TextField label={t("settings.import.max")} type="number" min={1} value={maxPulls} onChange={(e) => setMaxPulls(e.target.value)} />
          </div>
          <p className="text-xs text-muted">{t("settings.import.notes")}</p>
          <Checkbox checked={ack} onCheckedChange={setAck} label={t("settings.import.ack")} />
          <Button type="submit" variant="primary" icon={Upload} disabled={!allowed || !ack || !url || Boolean(gate)} title={gate} loading={importAction.pending}>
            {t("settings.import.start")}
          </Button>
        </form>
        {importAction.jobId ? <JobProgress jobId={importAction.jobId} /> : null}
        {importAction.error ? <InlineError error={importAction.error} /> : null}
      </section>
      <Dialog
        open={del !== null}
        onOpenChange={(o) => !o && setDel(null)}
        role="alertdialog"
        title={t("settings.projects.deleteTitle")}
        description={t("settings.projects.deleteBody")}
        footer={
          <>
            <Button onClick={() => setDel(null)}>{t("common.cancel")}</Button>
            <Button
              variant="danger"
              onClick={async () => {
                try {
                  await call(api.DELETE("/api/v1/projects/{pid}", { params: { path: { pid: del! } } }));
                  setDel(null);
                  void qc.invalidateQueries({ queryKey: keys.projects() });
                } catch (e) {
                  setDelError(e);
                }
              }}
            >
              {t("common.delete")}
            </Button>
          </>
        }
      >
        {delError ? <InlineError error={delError} /> : null}
      </Dialog>
    </div>
  );
}

function EditableRow({ setting }: { setting: EditableSetting }) {
  const qc = useQueryClient();
  const gate = useGate({ maintainer: true });
  const [draft, setDraft] = useState<string>(String(setting.value ?? ""));
  const [error, setError] = useState<unknown>(null);
  const label = tDynamic(`settings.pref.${setting.key}`) || setting.label;
  const save = async (value: unknown) => {
    setError(null);
    try {
      const out = await patchSettings({ [setting.key]: value });
      qc.setQueryData(keys.settings(), out);
      void qc.invalidateQueries({ queryKey: keys.status() });
    } catch (e) {
      setError(e);
    }
  };
  const reset = async () => {
    try {
      const out = await resetSettings([setting.key]);
      qc.setQueryData(keys.settings(), out);
      const v = out.editable.find((e) => e.key === setting.key)?.value;
      setDraft(String(v ?? ""));
    } catch (e) {
      setError(e);
    }
  };
  const disabled = Boolean(gate);
  let control: React.ReactNode;
  if (setting.type === "bool") {
    control = <Switch checked={Boolean(setting.value)} onCheckedChange={(v) => void save(v)} label={label} disabled={disabled} />;
  } else if (setting.type === "enum" && setting.options) {
    control = (
      <SelectField
        label={label}
        value={String(setting.value ?? "")}
        disabled={disabled}
        onChange={(e) => void save(e.target.value)}
        options={setting.options.map((o) => ({ value: o, label: tDynamic(`settings.option.${setting.key}.${o}`) || tDynamic(`settings.option.${o}`) || humanise(o) }))}
      />
    );
  } else {
    const numeric = setting.type === "int" || setting.type === "float";
    control = (
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void save(numeric ? Number(draft) : draft);
        }}
      >
        <TextField
          label={label}
          type={numeric ? "number" : "text"}
          step={setting.type === "float" ? "0.01" : "1"}
          min={setting.min ?? undefined}
          max={setting.max ?? undefined}
          value={draft}
          disabled={disabled}
          onChange={(e) => setDraft(e.target.value)}
          hint={setting.min !== null && setting.min !== undefined && setting.max !== null && setting.max !== undefined ? t("settings.pref.range", { min: setting.min, max: setting.max }) : undefined}
        />
        <Button type="submit" size="sm" disabled={disabled}>
          {t("common.save")}
        </Button>
      </form>
    );
  }
  return (
    <div className="flex flex-wrap items-start gap-3 border-b border-border py-3">
      <div className="min-w-0 flex-[1_1_18rem]">{control}</div>
      <Button size="sm" variant="ghost" icon={RotateCcw} disabled={disabled || setting.value === setting.default} title={gate} onClick={() => void reset()}>
        {t("common.reset")}
      </Button>
      {error ? <InlineError className="w-full" error={error} /> : null}
    </div>
  );
}

function PreferencesTab() {
  const settings = useSettings();
  const prefs = usePrefs();
  if (settings.isLoading) return <Skeleton lines={6} />;
  if (settings.error) return <InlineError error={settings.error} onRetry={() => void settings.refetch()} />;
  return (
    <div className="space-y-2">
      {(settings.data?.editable ?? []).map((s) => (
        <EditableRow key={s.key} setting={s} />
      ))}
      <div className="border-b border-border py-3">
        <Switch checked={prefs.shortcuts} onCheckedChange={(v) => setPref("shortcuts", v)} label={t("settings.pref.shortcuts")} hint={t("settings.pref.shortcutsHint")} />
      </div>
    </div>
  );
}

function AboutTab() {
  const status = useStatus();
  const qc = useQueryClient();
  const gate = useGate({ maintainer: true });
  const reset = useConfirmableAction<void>(() => call(api.POST("/api/v1/settings/reset-saved-results")), { title: t("settings.about.resetSaved") });
  const s = status.data;
  if (!s) return <Skeleton lines={4} />;
  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
        <dt className="text-muted">{t("settings.about.version")}</dt>
        <dd>{s.version}</dd>
        <dt className="text-muted">{t("settings.about.mode")}</dt>
        <dd>{tDynamic(`settings.mode.${s.mode}`) || s.mode}</dd>
        <dt className="text-muted">{t("settings.about.manifest")}</dt>
        <dd className="font-mono text-xs k-anywhere">{s.data.manifest_sha ?? t("format.none")}</dd>
        <dt className="text-muted">{t("settings.about.loaded")}</dt>
        <dd>{formatDateTime(s.data.loaded_at)}</dd>
        {s.data.snapshot ? (
          <>
            <dt className="text-muted">{t("settings.about.snapshot")}</dt>
            <dd>
              {formatDateTime(s.data.snapshot_created_at)}
              {s.data.snapshot_simulated ? ` · ${t("provenance.savedSimulated")}` : ""}
            </dd>
          </>
        ) : null}
        {s.data.snapshot_models?.length && !s.data.snapshot_simulated ? (
          <>
            <dt className="text-muted">{t("settings.about.models")}</dt>
            <dd className="font-mono text-xs">{s.data.snapshot_models.join(", ")}</dd>
          </>
        ) : null}
      </dl>
      <p className="text-sm text-muted">{t("settings.about.synthetic")}</p>
      <p className="text-sm text-muted">{t("settings.about.licences")}</p>
      <p className="text-sm">
        <a href={urls.apiDocs} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
          {t("settings.about.apiDocs")}
        </a>
      </p>
      <Button icon={RotateCcw} disabled={Boolean(gate)} title={gate} loading={reset.pending} onClick={() => void reset.run().then(() => qc.invalidateQueries())}>
        {t("settings.about.resetSaved")}
      </Button>
      {reset.jobId ? <JobProgress jobId={reset.jobId} compact /> : null}
      {reset.error ? <InlineError error={reset.error} /> : null}
    </div>
  );
}

export default function SettingsScreen() {
  const [params, setParams] = useSearchParams();
  const status = useStatus();
  const tab = (TABS as readonly string[]).includes(params.get("tab") ?? "") ? params.get("tab")! : "models";
  if (status.error && !status.data) return <PageError error={status.error} onRetry={() => void status.refetch()} />;
  return (
    <div className="k-page mx-auto w-full max-w-[72rem] space-y-5">
      <AnswerHeader title={t("settings.title")} subtitle={status.data ? (status.data.live ? t("settings.subtitleLive", { provider: status.data.provider }) : t("settings.subtitleSaved")) : undefined} />
      <Tabs
        value={tab}
        onValueChange={(v) => setParams(v === "models" ? {} : { tab: v }, { replace: true })}
        label={t("settings.tabs")}
        tabs={TABS.map((x) => ({ value: x, label: t(`settings.tab.${x}` as "settings.tab.models") }))}
      >
        <TabPanel value="models" className="pt-5"><ModelsTab /></TabPanel>
        <TabPanel value="usage" className="pt-5"><UsageTab /></TabPanel>
        <TabPanel value="sandbox" className="pt-5"><SandboxTab /></TabPanel>
        <TabPanel value="projects" className="pt-5"><ProjectsTab /></TabPanel>
        <TabPanel value="preferences" className="pt-5"><PreferencesTab /></TabPanel>
        <TabPanel value="about" className="pt-5"><AboutTab /></TabPanel>
      </Tabs>
    </div>
  );
}

export type { UsageGroup };
