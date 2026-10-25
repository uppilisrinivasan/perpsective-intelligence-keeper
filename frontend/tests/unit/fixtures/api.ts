/**
 * Test-only API fixtures for the route smoke test. Neutral placeholder values (no demo data), shaped by the
 * generated OpenAPI types so they break when the contract changes.
 */
import type { Schemas } from "@/api/types";
import { finding, provenance, queueRow } from "./factories";

const person = (id: string, login: string, role: string) => ({ id, login, display_name: login.replace(/-/g, " "), role });
const prov = provenance({ origin: "snapshot", simulated: true });

export const status: Schemas["Status"] = {
  mode: "demo",
  live: false,
  provider: "Provider P",
  version: "0.0.0",
  default_project_id: "prj_t",
  demo_now: "2030-01-05T08:00:00Z",
  auth_mode: "none",
  simulated: true,
  auto_approve_usd: 0.05,
  batch_enabled: false,
  import_allowed: true,
  estimates: { analyze_pr: 0.01, ask_answer: 0.01 },
  models: [{ role: "judge", model_id: "model/judge", display: "Judge Model", purpose: "Reviews", probe: { exists: "ok", chat: "ok", json_object: "ok", json_schema: "ok", reasoning: "n/a", tools: "ok" }, fallback_active: false }],
  sandbox: { provider: "local", requested: "local", isolation: "process", reason: null },
  spend: { used_usd: 0, cap_usd: 20, period: "month", reached: false },
  data: { loading: false, snapshot: true, snapshot_simulated: true, snapshot_created_at: "2030-01-04T08:00:00Z", snapshot_models: [], manifest_sha: "sha" },
};

const maintainer = person("per_m", "maint-a", "maintainer");
const reviewer = person("per_r", "rev-b", "reviewer");

export const fixtures: Record<string, unknown> = {
  "/api/v1/status": status,
  "/api/v1/projects": { items: [{ id: "prj_t", owner: "org-t", repo: "repo-t", kind: "demo", fictional: true, counts: { pulls: 3, open: 2, reviewers: 2 }, primary_maintainer: maintainer }] },
  "/api/v1/projects/prj_t": { id: "prj_t", owner: "org-t", repo: "repo-t", kind: "demo", fictional: true, counts: { pulls: 3, open: 2, reviewers: 2 }, primary_maintainer: maintainer },
  "/api/v1/projects/prj_t/people": { items: [{ ...maintainer, has_lens: true, lens_id: "lns_1", fictional: true }, { ...reviewer, has_lens: true, lens_id: "lns_2", fictional: true }] },
  "/api/v1/projects/prj_t/queue": {
    items: [queueRow({ provenance: prov }), queueRow({ number: 9002, title: "Add a dependency", lane: "unknown", handoff: { person_id: "per_r", display_name: "rev b" }, provenance: prov })],
    summary: { by_lane: { edge: 1, unknown: 1, shared: 0, blind_spot: 0 }, attention_by_lane: { edge: 20, unknown: 15 }, attention_minutes_total: 35, budget_minutes: 120, over_budget: false, need_count: 2, total: 2, naive_minutes: 60, handoff_suggestion: null },
    provenance: prov,
    maintainer,
  },
  "/api/v1/projects/prj_t/queue/digest": { markdown: "A short digest.", cards: [] },
  "/api/v1/projects/prj_t/pulls/9001": {
    number: 9001, title: "Add a widget loader", author: { login: "person-a", first_time: true }, body_md: "Body", state: "open", labels: [], base: "main", head: "feature", head_sha: "abc",
    created_at: "2030-01-01T00:00:00Z", additions: 3, deletions: 1, commits: 2, files: [{ filename: "pkg/loaders/yaml.py", status: "modified", additions: 3, deletions: 1, binary: false }], checks: [{ name: "tests", conclusion: "success" }], has_human_review: true, merged: false,
  },
  "/api/v1/projects/prj_t/pulls/9001/analysis": {
    analysis_id: "ana_1", pr_number: 9001, lane: "edge", attention_minutes: 20, baseline_only_count: 0, summary_md: "Adds a loader.", signals: [{ key: "new_dep", label: "New dependency", covered: false }], reasons: [], findings: [finding(), finding({ id: "rf_2", lane: "shared", title: "Type hints", fixable: false })], provenance: prov, stats: {}, lens_version: 1,
  },
  "/api/v1/projects/prj_t/pulls/9001/diff": { files: [{ filename: "pkg/loaders/yaml.py", status: "modified", binary: false, too_large: false, patch: "@@ -40,3 +40,5 @@\n def f():\n-    old\n+    new\n+    path = base / ref\n+    return path\n     pass" }] },
  "/api/v1/projects/prj_t/pulls/9001/compare": {
    pr_number: 9001, baseline: [{ id: "b1", title: "Type hints", statement: "s", category: "style", category_label: "Style", kind: "k", severity: "low", source: "baseline", anchor: { scope: "pr", side: "RIGHT" }, substantive: false }],
    lens: [{ id: "l1", title: "Type hints", statement: "s", category: "style", category_label: "Style", kind: "k", severity: "low", source: "lens", anchor: { scope: "pr", side: "RIGHT" }, substantive: false }, { id: "l2", title: "Path escape", statement: "s", category: "security", category_label: "Security", kind: "k", severity: "high", source: "lens", anchor: { scope: "line", path: "pkg/loaders/yaml.py", start_line: 42, side: "RIGHT" }, substantive: true }],
    pairs: [{ baseline_id: "b1", lens_id: "l1", decision: "match" }], residual: { r_plus: ["l2"], r_minus: [] }, human: [], human_pairs: [], provenance: prov, maintainer,
  },
  "/api/v1/projects/prj_t/pulls/9001/review-draft": { body_md: "Draft body", comments: [{ path: "pkg/loaders/yaml.py", line: 42, side: "RIGHT", body_md: "Check this" }], edited_by_user: false, event: "COMMENT", header: "Review draft", label: "Drafted by Keeper", provenance: prov },
  "/api/v1/projects/prj_t/lenses": { items: [{ id: "lns_1", person: maintainer, status: "active", latest_version: 2, health_state: "healthy", shared_in_project: true }] },
  "/api/v1/lenses/lns_1": {
    id: "lns_1", person: maintainer, status: "active", current_version: 2, health_state: "healthy", fictional: true, unconsumed_feedback: 3, update_min_events: 1,
    consent: { id: "c", granted_at: "2030-01-01T00:00:00Z", granted_by: "maint-a", scope: "build_lens", synthetic: true, text_version: "v1" },
    versions: [{ id: "lv1", version: 1, created_at: "2029-06-01T00:00:00Z", change_reason: "initial build", cutoff_at: "2029-06-01T00:00:00Z", origin: "snapshot", status: "superseded" }, { id: "lv2", version: 2, created_at: "2030-01-01T00:00:00Z", change_reason: "feedback", cutoff_at: "2029-06-01T00:00:00Z", origin: "snapshot", status: "active", counts: { added: 1, removed: 0, changed: 1 } }],
  },
  "/api/v1/lenses/lns_1/versions/2": { id: "lv2", version: 2, card_md: "- Watches include paths [[lens_item:li_1]]", change_reason: "feedback", cutoff_at: "2029-06-01T00:00:00Z", ruler_id: "rul", ruler_display: "Judge Model", build_stats: { reviewed_prs: 40 }, items_count: { edge: 3 }, key_facts: {}, provenance: prov },
  "/api/v1/lenses/lns_1/versions/2/items": { items: [{ id: "li_1", stable_key: "k", type: "edge", title: "Safe include paths", statement_md: "Keep includes inside.", category: "security", category_label: "Security", severity_typical: "high", triggers: { paths: ["pkg/loaders"] }, stats: { support: 9, posterior_mean: 0.82, ci90: { low: 0.65, high: 0.93 } }, status: "validated" }] },
  "/api/v1/lenses/lns_1/edge-map": { areas: ["pkg/loaders"], categories: ["security"], cells: [{ area: "pkg/loaders", category: "security", category_label: "Security", cost: 1, kind: "edge", residual_rate: 0.5, shared_rate: 0.1, value: 2.1, volume: 10, multiplier: 3.4 }], top: [{ area: "pkg/loaders", category: "security", category_label: "Security", cost: 1, kind: "edge", residual_rate: 0.5, shared_rate: 0.1, value: 2.1, volume: 10, multiplier: 3.4, open_prs: [9001] }], enough: [], gaps: [], summary_md: "Summary" },
  "/api/v1/lenses/lns_1/growth": { health_state: "healthy", explanation_md: "Fine.", snapshots: [{ period: "Q1", period_start: "2029-01-01", period_end: "2029-03-31", measures: { r_plus_rate: 0.4, g: 0.1 } }] },
  "/api/v1/lenses/lns_1/audit": { items: [] },
  "/api/v1/lenses/lns_1/diff": { from_version: 1, to_version: 2, added: [], removed: [], changed: [], summary_md: "Little changed." },
  "/api/v1/projects/prj_t/fidelity-runs": { items: [{ id: "fid_1", lens_version: 1, created_at: "2030-01-02T00:00:00Z", pass_overall: true, origin: "snapshot", prs: 10, simulated: true }] },
  "/api/v1/fidelity-runs/fid_1": {
    id: "fid_1", lens_version: 1, person: maintainer, holdout: { prs: 10 }, cases_count: 10, cost_usd: 0.1, created_at: "2030-01-02T00:00:00Z", pass_overall: true, provenance: prov,
    metrics: {
      keeper: { substantive_recall: { value: 0.6, low: 0.5, high: 0.7, n: 10 }, noise_per_pr: { value: 0.9 }, precision: { value: 0.7 }, residual_recall: { value: 0.5, low: 0.3, high: 0.6 } },
      lens: { substantive_recall: { value: 0.5, low: 0.4, high: 0.6, n: 10 }, noise_per_pr: { value: 1 }, precision: { value: 0.6 }, residual_recall: { value: 0.45, low: 0.3, high: 0.6 } },
      baseline: { substantive_recall: { value: 0.3, low: 0.2, high: 0.4, n: 10 }, noise_per_pr: { value: 1.2 }, precision: { value: 0.5 } },
    },
    paired_difference: { value: 0.3, low: 0.2, high: 0.4 },
    criteria: [{ key: "diff", label: "Beats generic review", passed: true, detail: "+30 points" }],
    falsifiers: [{ key: "f1", name: "The residual predicts something", description_md: "Details", result: "ok", passed: true }],
    sensitivity: { window_3: { value: 0.58 } },
  },
  "/api/v1/fidelity-runs/fid_1/cases": { items: [{ pr_number: 9100, title: "A held-out change", maintainer_findings: 3, baseline_matched: 1, lens_matched: 2, keeper_matched: 2, lens_extra: 0, outcome: "caught" }] },
  "/api/v1/projects/prj_t/practice/overview": { learner_key: "me", learner: maintainer, target: maintainer, sessions: [{ id: "prs_1", kind: "before", status: "completed", created_at: "2030-01-01T00:00:00Z", items: 5, recall: 0.32, origin: "snapshot" }], bank_size: 15, next_kind: "learn", lens_shared: true, scoring_available: false },
  "/api/v1/settings": { editable: [{ key: "theme", label: "Theme", type: "enum", value: "system", default: "system", options: ["system", "light", "dark"] }, { key: "attention_budget_minutes", label: "Budget", type: "int", value: 120, default: 120, min: 15, max: 600 }], readonly: {}, secrets: { provider_api_key: { configured: false } } },
  "/api/v1/usage": { cap: { used_usd: 0, cap_usd: 20, period: "month" }, group_by: "feature", period: "month", rows: [], total: { key: "total", calls: 0, cost_usd: 0, input_tokens: 0, output_tokens: 0 } },
  "/api/v1/jobs": { items: [] },
  "/api/v1/tour": { steps: [] },
  "/api/v1/glossary": { terms: [{ key: "residual", label: "Residual", short: "What only the maintainer notices", long_md: "" }] },
  "/api/v1/chat/threads": { items: [] },
  "/api/v1/chat/suggestions": { items: [{ text: "What needs me today?" }] },
  "/api/v1/chat/examples": { items: [{ id: "ex1", question: "What needs me today?", answer_md: "Two PRs [[pull:9001]].", cards: [{ type: "pull", data: { number: 9001, title: "Add a widget loader", lane: "edge" } }] }], simulated: true },
};
