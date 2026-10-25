import { describe, expect, it } from "vitest";
import { parsePatch, toSplitRows, toSuggestion } from "@/lib/diff";
import { fixFromEvents } from "@/lib/fix";
import { reduceJob, type JobState } from "@/api/jobs";
import { pickBanner } from "@/shell/Banners";
import { compareLanes } from "@/components/keeper/CompareView";
import type { FindingOut, Status } from "@/api/types";

describe("diff parsing", () => {
  const patch = "@@ -1,3 +1,4 @@\n line one\n-old two\n+new two\n+added three\n line four\n\\ No newline at end of file";
  it("parses a header-less GitHub patch with new-side line numbers", () => {
    const p = parsePatch(patch, "a.py");
    expect(p.additions).toBe(2);
    expect(p.deletions).toBe(1);
    const adds = p.lines.filter((l) => l.kind === "add").map((l) => l.newNo);
    expect(adds).toEqual([2, 3]);
    expect(p.lines.some((l) => l.text.includes("No newline"))).toBe(false);
  });
  it("pairs deletions and additions side by side", () => {
    const rows = toSplitRows(parsePatch(patch).lines);
    const changed = rows.find((r) => r.left?.kind === "del");
    expect(changed?.right?.text).toBe("new two");
  });
  it("formats a single-hunk change as a suggestion block", () => {
    expect(toSuggestion(patch)?.startsWith("```suggestion")).toBe(true);
  });
});

describe("job state", () => {
  const base: JobState = { id: "job_1", params: {}, phase: "connecting", events: [], warnings: [], startedAt: 0, connectionLost: false };
  it("tracks steps, progress, cost and completion", () => {
    let s = reduceJob(base, { type: "job.started", data: { kind: "fix" } });
    s = reduceJob(s, { type: "job.step", data: { step: "plan", label: "Planning", index: 1, total: 4 } });
    s = reduceJob(s, { type: "job.cost", data: { cost_usd: 0.02, calls: 3 } });
    s = reduceJob(s, { type: "job.completed", data: { result: { fix_id: "fix_1" } } });
    expect(s.kind).toBe("fix");
    expect(s.step?.label).toBe("Planning");
    expect(s.cost?.cost_usd).toBe(0.02);
    expect(s.phase).toBe("completed");
    expect(s.result?.fix_id).toBe("fix_1");
  });
  it("records failures", () => {
    const s = reduceJob(base, { type: "job.failed", data: { error: { code: "sandbox_unavailable", message: "no docker" } } });
    expect(s.error).toMatchObject({ code: "sandbox_unavailable" });
  });
});

describe("fix timeline from events", () => {
  it("builds branches, attempts and the winner", () => {
    const ev = (type: string, data: Record<string, unknown>) => ({ type, data });
    const vm = fixFromEvents(
      [
        ev("fix.sandbox.ready", { provider: "local" }),
        ev("fix.tests.baseline", { passed: 10, failed: 0 }),
        ev("fix.plan", { branch: "A", plan: "Do it" }),
        ev("fix.apply", { branch: "A", ok: true, errors: [] }),
        ev("fix.test.result", { branch: "A", passed: 9, failed: 1 }),
        ev("fix.repair", { branch: "A", iteration: 2 }),
        ev("fix.test.result", { branch: "A", passed: 11, failed: 0 }),
        ev("fix.verify", { branch: "A", addresses_finding: true }),
        ev("fix.completed", { status: "passed", winning_branch: "A" }),
      ],
      "completed",
    );
    expect(vm.sandboxReady).toBe(true);
    expect(vm.baseline).toEqual({ passed: 10, failed: 0 });
    expect(vm.branches[0]?.steps.map((s) => s.kind)).toEqual(["plan", "apply", "test", "repair", "test", "verify"]);
    expect(vm.winning).toBe("A");
    expect(vm.running).toBe(false);
  });
});

describe("banner priority", () => {
  const status = (p: Partial<Status>): Status =>
    ({
      live: true,
      mode: "demo",
      provider: "Provider",
      version: "0",
      models: [],
      sandbox: { provider: "local", requested: "local", isolation: "process" },
      spend: { used_usd: 0, cap_usd: 1, period: "month", reached: false },
      data: {},
      ...p,
    }) as Status;
  it("orders spend cap > no key > fallback > sandbox", () => {
    expect(pickBanner(status({ live: false, spend: { used_usd: 1, cap_usd: 1, period: "month", reached: true } }), [])).toBe("cap");
    expect(pickBanner(status({ live: false }), [])).toBe("nokey");
    expect(pickBanner(status({ live: false }), ["nokey"])).toBeNull();
    expect(pickBanner(status({ models: [{ role: "judge", model_id: "m", display: "M", purpose: "", probe: { chat: "ok", exists: "ok", json_object: "ok", json_schema: "ok", reasoning: "ok", tools: "ok" }, fallback_active: true }] }), [])).toBe("fallback");
    expect(pickBanner(status({ sandbox: { provider: "local", requested: "docker", isolation: "process" } }), [])).toBe("sandbox");
    expect(pickBanner(status({}), [])).toBeNull();
  });
});

describe("compare lanes", () => {
  const f = (id: string): FindingOut => ({ id, title: id, statement: id, category: "c", category_label: "C", kind: "k", severity: "low", source: "x", anchor: { scope: "pr", side: "RIGHT" }, substantive: true });
  it("colours matched pairs shared, lens-only edge and residual R− blind spot", () => {
    const r = compareLanes({ baseline: [f("b1"), f("b2"), f("b3")], lens: [f("l1"), f("l2")], pairs: [{ baseline_id: "b1", lens_id: "l1", decision: "match" }], residual: { r_plus: ["l2"], r_minus: ["b2"] } });
    expect(r.lane.get("l1")).toBe("shared");
    expect(r.lane.get("b1")).toBe("shared");
    expect(r.lane.get("l2")).toBe("edge");
    expect(r.lane.get("b2")).toBe("blind_spot");
    expect(r.lane.get("b3")).toBe("baseline_only");
    expect(r.edge).toBe(1);
    expect(r.blind).toBe(1);
  });
});
