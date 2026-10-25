import { api, call, urls } from "./client";
import { invalidateForJob } from "./invalidate";
import type { JobOut } from "./types";
import { num, obj, str, type Obj } from "@/lib/unknown";

/**
 * One EventSource per job, shared by reference counting (docs/05-api/04 §3, useJob).
 * Event payload schemas are the JobEvent* components in openapi.json.
 */
export const JOB_EVENT_NAMES = [
  "job.queued",
  "job.started",
  "job.step",
  "job.progress",
  "job.log",
  "job.cost",
  "job.warning",
  "job.completed",
  "job.failed",
  "job.cancelled",
  "analysis.step",
  "analysis.updated",
  "fix.started",
  "fix.sandbox.ready",
  "fix.tests.baseline",
  "fix.plan",
  "fix.apply",
  "fix.test.output",
  "fix.test.result",
  "fix.repair",
  "fix.verify",
  "fix.completed",
  "lens.stage",
  "lens.version.ready",
  "fidelity.case",
  "fidelity.batch",
  "fidelity.metrics",
  "fidelity.falsifier",
  "import.fetch",
  "import.wait",
  "handoff.osv",
  "handoff.ready",
  "practice.scored",
] as const;

const TERMINAL = new Set(["job.completed", "job.failed", "job.cancelled"]);
const TERMINAL_STATUS = new Set(["completed", "failed", "cancelled", "succeeded", "done"]);

export interface JobEvent {
  type: string;
  data: Obj;
  id?: string;
}

export type JobPhase = "connecting" | "queued" | "running" | "completed" | "failed" | "cancelled";

export interface JobState {
  id: string;
  kind?: string;
  params: Obj;
  phase: JobPhase;
  events: JobEvent[];
  step?: { step: string; label: string; index: number; total: number };
  progress?: { progress: number; done: number; total: number };
  cost?: { cost_usd: number; calls: number };
  warnings: Array<{ code: string; message: string }>;
  result?: Obj;
  error?: { code: string; message: string; details: Obj };
  startedAt: number;
  connectionLost: boolean;
}

interface Entry {
  state: JobState;
  listeners: Set<() => void>;
  refs: number;
  source: EventSource | null;
  closeTimer: ReturnType<typeof setTimeout> | null;
  fetched: boolean;
}

const entries = new Map<string, Entry>();
const terminalListeners = new Set<(s: JobState) => void>();

/** Notified once per job when it finishes (toasts, Activity). */
export function onJobTerminal(listener: (s: JobState) => void): () => void {
  terminalListeners.add(listener);
  return () => terminalListeners.delete(listener);
}

function emptyState(id: string): JobState {
  return { id, params: {}, phase: "connecting", events: [], warnings: [], startedAt: Date.now(), connectionLost: false };
}

function entry(id: string): Entry {
  let e = entries.get(id);
  if (!e) {
    e = { state: emptyState(id), listeners: new Set(), refs: 0, source: null, closeTimer: null, fetched: false };
    entries.set(id, e);
  }
  return e;
}

function update(e: Entry, patch: Partial<JobState>): void {
  e.state = { ...e.state, ...patch };
  e.listeners.forEach((l) => l());
}

function isTerminal(phase: JobPhase): boolean {
  return phase === "completed" || phase === "failed" || phase === "cancelled";
}

function finish(e: Entry): void {
  e.source?.close();
  e.source = null;
  invalidateForJob(e.state.kind);
  terminalListeners.forEach((l) => l(e.state));
}

/** Applies one event to the job state. Exported for tests. */
export function reduceJob(s: JobState, ev: JobEvent): JobState {
  const d = ev.data;
  const next: JobState = { ...s, events: [...s.events, ev], connectionLost: false };
  switch (ev.type) {
    case "job.queued":
      next.phase = "queued";
      next.kind = str(d.kind) ?? s.kind;
      next.params = obj(d.params);
      break;
    case "job.started":
      next.phase = "running";
      next.kind = str(d.kind) ?? s.kind;
      break;
    case "job.step":
      next.phase = "running";
      next.step = { step: str(d.step) ?? "", label: str(d.label) ?? "", index: num(d.index) ?? 0, total: num(d.total) ?? 0 };
      break;
    case "job.progress":
      next.progress = { progress: num(d.progress) ?? 0, done: num(d.done) ?? 0, total: num(d.total) ?? 0 };
      break;
    case "job.cost":
      next.cost = { cost_usd: num(d.cost_usd) ?? 0, calls: num(d.calls) ?? 0 };
      break;
    case "job.warning":
      next.warnings = [...s.warnings, { code: str(d.code) ?? "", message: str(d.message) ?? "" }];
      break;
    case "job.completed":
      next.phase = "completed";
      next.result = obj(d.result);
      break;
    case "job.failed": {
      const err = obj(d.error);
      next.phase = "failed";
      next.error = { code: str(err.code) ?? "unknown", message: str(err.message) ?? "", details: obj(err.details) };
      break;
    }
    case "job.cancelled":
      next.phase = "cancelled";
      break;
    default:
      if (next.phase === "connecting" || next.phase === "queued") next.phase = "running";
  }
  // Keep the log of streamed test output bounded.
  if (next.events.length > 4000) next.events = next.events.slice(-4000);
  return next;
}

function open(id: string, e: Entry): void {
  if (e.source || isTerminal(e.state.phase) || typeof EventSource === "undefined") return;
  const es = new EventSource(urls.jobEvents(id), { withCredentials: true });
  e.source = es;
  const handler = (type: string) => (msg: MessageEvent<string>) => {
    let data: Obj;
    try {
      data = obj(JSON.parse(msg.data));
    } catch {
      data = {};
    }
    const ev: JobEvent = { type, data };
    if (msg.lastEventId) ev.id = msg.lastEventId;
    e.state = reduceJob(e.state, ev);
    e.listeners.forEach((l) => l());
    if (TERMINAL.has(type)) finish(e);
  };
  for (const name of JOB_EVENT_NAMES) es.addEventListener(name, handler(name) as EventListener);
  es.onerror = () => {
    if (es.readyState === EventSource.CLOSED) {
      e.source = null;
      if (!isTerminal(e.state.phase)) {
        update(e, { connectionLost: true });
        void refreshFromServer(id, e);
      }
    } else {
      update(e, { connectionLost: true });
    }
  };
}

function applyJobOut(e: Entry, job: JobOut): void {
  const status = job.status;
  const patch: Partial<JobState> = { kind: job.kind, params: obj(job.params) };
  if (TERMINAL_STATUS.has(status)) {
    patch.phase = status === "failed" ? "failed" : status === "cancelled" ? "cancelled" : "completed";
    patch.result = obj(job.result);
    if (job.error) {
      const err = obj(job.error);
      patch.error = { code: str(err.code) ?? "unknown", message: str(err.message) ?? "", details: obj(err.details) };
    }
  } else if (e.state.phase === "connecting") {
    patch.phase = status === "queued" ? "queued" : "running";
  }
  if (!e.state.progress && job.progress) patch.progress = { progress: job.progress, done: 0, total: 0 };
  if (!e.state.cost && job.cost_usd) patch.cost = { cost_usd: job.cost_usd, calls: 0 };
  const wasTerminal = isTerminal(e.state.phase);
  update(e, patch);
  if (!wasTerminal && patch.phase && isTerminal(patch.phase)) finish(e);
}

async function refreshFromServer(id: string, e: Entry): Promise<void> {
  try {
    const job = await call(api.GET("/api/v1/jobs/{job_id}", { params: { path: { job_id: id } } }));
    applyJobOut(e, job);
  } catch {
    /* the stream state stays as it is */
  }
}

export function subscribeJob(id: string, listener: () => void): () => void {
  const e = entry(id);
  e.listeners.add(listener);
  e.refs += 1;
  if (e.closeTimer) {
    clearTimeout(e.closeTimer);
    e.closeTimer = null;
  }
  if (!e.fetched) {
    e.fetched = true;
    void refreshFromServer(id, e);
  }
  open(id, e);
  return () => {
    e.listeners.delete(listener);
    e.refs -= 1;
    if (e.refs <= 0) {
      e.closeTimer = setTimeout(() => {
        if (e.refs <= 0) {
          e.source?.close();
          e.source = null;
        }
      }, 1500);
    }
  };
}

export function getJobState(id: string): JobState {
  return entry(id).state;
}

/** Feeds an event without a network stream (tests and saved-run replays). */
export function injectJobEvent(id: string, ev: JobEvent): void {
  const e = entry(id);
  const was = isTerminal(e.state.phase);
  e.state = reduceJob(e.state, ev);
  e.listeners.forEach((l) => l());
  if (!was && TERMINAL.has(ev.type)) finish(e);
}

export async function cancelJob(id: string): Promise<void> {
  await call(api.POST("/api/v1/jobs/{job_id}/cancel", { params: { path: { job_id: id } } }));
}
