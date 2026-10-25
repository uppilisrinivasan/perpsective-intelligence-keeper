import type { FixRunDetail } from "@/api/types";
import type { JobEvent } from "@/api/jobs";
import { bool, num, obj, str, strs } from "./unknown";

/** One view model for the fix timeline, built from live job events or from a saved fix run. */
export interface FixStep {
  kind: "plan" | "apply" | "test" | "repair" | "verify";
  iteration: number;
  ok: boolean | null;
  plan?: string;
  errors?: string[];
  passed?: number;
  failed?: number;
  failures?: Array<{ test: string; message: string }>;
  durationMs?: number;
  model?: string;
  explanation?: string;
}

export interface FixBranchVM {
  name: string;
  approach?: string;
  steps: FixStep[];
  output: string;
  status?: string;
}

export interface FixVM {
  status: string;
  running: boolean;
  provider?: string;
  isolation?: string;
  sandboxReady: boolean;
  baseline?: { passed: number; failed: number };
  branches: FixBranchVM[];
  winning?: string | null;
  diffStats?: Record<string, number>;
  verified?: { branch?: string; addresses: boolean | null; explanation?: string };
  error?: string;
}

const OUTPUT_TAIL = 8000;

function branchOf(vm: FixVM, name: string | undefined): FixBranchVM {
  const n = name ?? "A";
  let b = vm.branches.find((x) => x.name === n);
  if (!b) {
    b = { name: n, steps: [], output: "" };
    vm.branches.push(b);
  }
  return b;
}

export function fixFromEvents(events: JobEvent[], phase: string): FixVM {
  const vm: FixVM = { status: phase, running: !["completed", "failed", "cancelled"].includes(phase), sandboxReady: false, branches: [] };
  const iter = new Map<string, number>();
  for (const ev of events) {
    const d = obj(ev.data);
    const branch = str(d.branch);
    switch (ev.type) {
      case "fix.sandbox.ready":
        vm.sandboxReady = true;
        vm.provider = str(d.provider);
        break;
      case "fix.tests.baseline":
        vm.baseline = { passed: num(d.passed) ?? 0, failed: num(d.failed) ?? 0 };
        break;
      case "fix.plan": {
        const b = branchOf(vm, branch);
        const it = iter.get(b.name) ?? 1;
        iter.set(b.name, it);
        b.steps.push({ kind: "plan", iteration: it, ok: true, plan: str(d.plan), model: str(d.model_display) ?? undefined, durationMs: num(d.latency_ms) });
        break;
      }
      case "fix.apply": {
        const b = branchOf(vm, branch);
        b.steps.push({ kind: "apply", iteration: iter.get(b.name) ?? 1, ok: bool(d.ok) ?? null, errors: strs(d.errors) });
        break;
      }
      case "fix.test.output": {
        const b = branchOf(vm, branch);
        b.output = (b.output + (str(d.chunk) ?? "")).slice(-OUTPUT_TAIL);
        break;
      }
      case "fix.test.result": {
        const b = branchOf(vm, branch);
        const failed = num(d.failed) ?? 0;
        b.steps.push({ kind: "test", iteration: iter.get(b.name) ?? 1, ok: failed === 0, passed: num(d.passed) ?? 0, failed, durationMs: num(d.duration_ms) });
        break;
      }
      case "fix.repair": {
        const b = branchOf(vm, branch);
        const it = num(d.iteration) ?? (iter.get(b.name) ?? 1) + 1;
        iter.set(b.name, it);
        b.steps.push({ kind: "repair", iteration: it, ok: true, model: str(d.model_display) ?? undefined });
        break;
      }
      case "fix.verify":
        vm.verified = { branch, addresses: bool(d.addresses_finding) ?? null, explanation: str(d.explanation) };
        if (branch) branchOf(vm, branch).steps.push({ kind: "verify", iteration: iter.get(branch) ?? 1, ok: bool(d.addresses_finding) ?? null, explanation: str(d.explanation) });
        break;
      case "fix.completed":
        vm.status = str(d.status) ?? vm.status;
        vm.winning = str(d.winning_branch) ?? null;
        vm.diffStats = obj(d.diff_stats) as Record<string, number>;
        break;
      case "job.failed":
        vm.error = str(obj(d.error).message);
        break;
      default:
        break;
    }
  }
  return vm;
}

export function fixFromRun(run: FixRunDetail): FixVM {
  const vm: FixVM = {
    status: run.status,
    running: run.status === "running" || run.status === "queued",
    provider: run.provider ?? undefined,
    isolation: run.isolation ?? undefined,
    sandboxReady: true,
    baseline: run.baseline_tests ? { passed: run.baseline_tests.passed ?? 0, failed: run.baseline_tests.failed ?? 0 } : undefined,
    winning: run.winning_branch,
    diffStats: run.diff_stats,
    error: run.error ?? undefined,
    branches: run.branches.map((b) => ({
      name: b.name,
      approach: b.approach ?? undefined,
      status: b.status,
      output: "",
      steps: b.attempts.flatMap((a): FixStep[] => {
        const steps: FixStep[] = [];
        steps.push({ kind: a.iteration > 1 ? "repair" : "plan", iteration: a.iteration, ok: true, plan: a.plan_md ?? undefined, model: a.model?.display ?? undefined, durationMs: a.model?.latency_ms ?? undefined });
        if (a.apply_errors !== undefined || a.edits !== undefined) steps.push({ kind: "apply", iteration: a.iteration, ok: (a.apply_errors ?? []).length === 0, errors: a.apply_errors });
        if (a.test) steps.push({ kind: "test", iteration: a.iteration, ok: (a.test.failed ?? 0) === 0 && (a.test.errors ?? 0) === 0, passed: a.test.passed, failed: a.test.failed, failures: a.test.failures, durationMs: a.test.duration_ms });
        if (a.verify) {
          const v = obj(a.verify);
          steps.push({ kind: "verify", iteration: a.iteration, ok: bool(v.addresses_finding) ?? null, explanation: str(v.explanation) });
        }
        return steps;
      }),
    })),
  };
  const verifyStep = vm.branches.find((b) => b.name === vm.winning)?.steps.find((s) => s.kind === "verify");
  if (verifyStep) vm.verified = { branch: vm.winning ?? undefined, addresses: verifyStep.ok, explanation: verifyStep.explanation };
  return vm;
}

export function isFixSuccess(status: string | undefined): boolean {
  return ["passed", "succeeded", "success", "completed", "fixed"].includes(status ?? "");
}
