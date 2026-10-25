import { CheckCircle2, CircleX, LoaderCircle, Star, CircleDashed } from "lucide-react";
import type { ReactNode } from "react";
import { Disclosure } from "@/components/ui/Disclosure";
import { Markdown } from "@/components/ui/Markdown";
import { t, tDynamic } from "@/copy/t";
import { cx } from "@/lib/cx";
import { formatDurationMs } from "@/lib/format";
import type { FixBranchVM, FixStep, FixVM } from "@/lib/fix";

function StepIcon({ ok }: { ok: boolean | null | undefined }) {
  if (ok === true) return <CheckCircle2 className="size-4 shrink-0 text-success" aria-hidden />;
  if (ok === false) return <CircleX className="size-4 shrink-0 text-danger" aria-hidden />;
  return <LoaderCircle className="size-4 shrink-0 animate-spin text-muted motion-reduce:animate-none" aria-hidden />;
}

function Row({ ok, title, children, extra }: { ok: boolean | null | undefined; title: ReactNode; children?: ReactNode; extra?: ReactNode }) {
  const status = ok === true ? t("fix.ok") : ok === false ? t("fix.notOk") : t("fix.running");
  return (
    <li className="flex gap-2">
      <StepIcon ok={ok} />
      <div className="min-w-0 flex-1">
        <span className="sr-only">{status}: </span>
        {children ? (
          <Disclosure summary={<span className="font-normal">{title}</span>} headerClassName="text-sm">
            <div className="pl-5 text-sm">{children}</div>
          </Disclosure>
        ) : (
          <p className="text-sm">{title}</p>
        )}
        {extra}
      </div>
    </li>
  );
}

function stepTitle(s: FixStep): string {
  switch (s.kind) {
    case "plan":
      return s.plan ? t("fix.step.planWith", { plan: firstLine(s.plan) }) : t("fix.step.plan");
    case "repair":
      return t("fix.step.repair", { n: s.iteration });
    case "apply":
      return s.ok === false ? t("fix.step.applyFailed", { n: s.errors?.length ?? 0 }) : t("fix.step.apply");
    case "test":
      return s.ok ? t("fix.step.testsPassed", { n: s.passed ?? 0 }) : s.failures?.[0]?.test ? t("fix.step.testsFailedFirst", { n: s.failed ?? 0, first: s.failures[0].test }) : t("fix.step.testsFailed", { n: s.failed ?? 0 });
    case "verify":
      return s.ok ? t("fix.step.verified") : s.ok === false ? t("fix.step.notVerified") : t("fix.step.verifying");
  }
}

function firstLine(md: string): string {
  const line = md.split("\n").find((l) => l.trim()) ?? "";
  const s = line.replace(/^[#*\-\s]+/, "");
  return s.length > 90 ? `${s.slice(0, 88)}…` : s;
}

function StepDetail({ s }: { s: FixStep }) {
  if (s.kind === "plan" || s.kind === "repair") return s.plan ? <Markdown source={s.plan} className="text-sm" /> : null;
  if (s.kind === "apply" && s.errors?.length)
    return (
      <ul className="list-disc pl-4 font-mono text-xs">
        {s.errors.map((e, i) => (
          <li key={i} className="k-anywhere">
            {e}
          </li>
        ))}
      </ul>
    );
  if (s.kind === "test" && s.failures?.length)
    return (
      <ul className="space-y-1">
        {s.failures.map((f, i) => (
          <li key={i}>
            <p className="font-mono text-xs font-medium k-anywhere">{f.test}</p>
            <pre className="max-h-40 overflow-auto rounded-sm bg-surface-2 p-2 font-mono text-xs whitespace-pre-wrap">{f.message}</pre>
          </li>
        ))}
      </ul>
    );
  if (s.kind === "verify" && s.explanation) return <p className="text-sm text-muted">{s.explanation}</p>;
  return null;
}

function hasDetail(s: FixStep): boolean {
  return Boolean((s.kind === "plan" || s.kind === "repair") && s.plan) || Boolean(s.errors?.length) || Boolean(s.failures?.length) || Boolean(s.kind === "verify" && s.explanation);
}

function BranchColumn({ b, vm }: { b: FixBranchVM; vm: FixVM }) {
  const won = vm.winning && vm.winning === b.name;
  const last = b.steps[b.steps.length - 1];
  const working = vm.running && (!last || last.kind !== "verify");
  return (
    <section className={cx("rounded-md border p-3", won ? "border-success bg-success-bg/40" : "border-border")} aria-label={t("fix.branch", { name: b.name })}>
      <h4 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
        {t("fix.branch", { name: b.name })}
        {won ? (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-success-fg">
            <Star className="size-3.5" aria-hidden />
            {t("fix.keeps")}
          </span>
        ) : null}
      </h4>
      {b.approach ? <p className="mb-2 text-xs text-muted">{b.approach}</p> : null}
      <ol className="space-y-1.5">
        {b.steps.map((s, i) => (
          <Row
            key={i}
            ok={s.ok}
            title={
              <>
                {stepTitle(s)}
                {s.durationMs ? <span className="text-muted"> · {formatDurationMs(s.durationMs)}</span> : null}
                {s.model ? <span className="text-muted"> · {s.model}</span> : null}
              </>
            }
          >
            {hasDetail(s) ? <StepDetail s={s} /> : null}
          </Row>
        ))}
        {working ? <Row ok={null} title={t("fix.working")} /> : null}
      </ol>
      {b.output ? (
        <Disclosure summary={t("fix.output")} className="mt-2" headerClassName="text-xs text-muted">
          <pre className="max-h-64 overflow-auto rounded-sm bg-surface-2 p-2 font-mono text-xs whitespace-pre-wrap" aria-live="off">
            {b.output}
          </pre>
        </Disclosure>
      ) : null}
    </section>
  );
}

/** Renders the fix job: sandbox, baseline tests, branch columns (stacked below container md), verification. */
export function FixTimeline({ vm }: { vm: FixVM }) {
  return (
    <div className="@container space-y-3" data-tour="fix_timeline">
      <ol className="space-y-1.5">
        <Row ok={vm.sandboxReady ? true : vm.running ? null : false} title={vm.sandboxReady ? t("fix.sandboxReady", { provider: vm.provider ?? "" }) : t("fix.sandboxStarting")} />
        {vm.baseline || vm.sandboxReady ? (
          <Row
            ok={vm.baseline ? true : vm.running ? null : undefined}
            title={vm.baseline ? t("fix.baseline", { passed: vm.baseline.passed, failed: vm.baseline.failed }) : t("fix.baselineRunning")}
          />
        ) : null}
      </ol>
      {vm.branches.length ? (
        <div className={cx("grid gap-3", vm.branches.length > 1 && "@md:grid-cols-2")}>
          {vm.branches.map((b) => (
            <BranchColumn key={b.name} b={b} vm={vm} />
          ))}
        </div>
      ) : vm.running ? (
        <p className="flex items-center gap-2 text-sm text-muted">
          <CircleDashed className="size-4" aria-hidden />
          {t("fix.planning")}
        </p>
      ) : null}
      {vm.verified ? (
        <ol>
          <Row ok={vm.verified.addresses} title={vm.verified.addresses ? t("fix.verifiedFinal") : t("fix.notVerifiedFinal")}>
            {vm.verified.explanation ? <p className="text-sm text-muted">{vm.verified.explanation}</p> : null}
          </Row>
        </ol>
      ) : null}
      {!vm.running ? (
        <p className="sr-only" role="status">
          {tDynamic(`fix.status.${vm.status}`) || vm.status}
        </p>
      ) : null}
    </div>
  );
}
