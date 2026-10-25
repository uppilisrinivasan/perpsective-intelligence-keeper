/**
 * Test-only factories. Values are neutral placeholders (never demo names or numbers from data/),
 * built on the generated API types so they stay in sync with openapi.json.
 */
import type { Provenance, QueueRow, RoutedFinding } from "@/api/types";

export const provenance = (p: Partial<Provenance> = {}): Provenance => ({ origin: "live", computed_at: "2030-01-02T10:00:00Z", simulated: false, ...p });

export function queueRow(p: Partial<QueueRow> = {}): QueueRow {
  return {
    number: 9001,
    title: "Add a widget loader",
    author: { login: "person-a", first_time: true, id: "per_a" },
    lane: "edge",
    reasons: [{ kind: "pattern", label: "Touches a sensitive loader", detail: "path containment" }],
    signals: [],
    attention_minutes: 20,
    counts: { edge: 2, blind_spot: 0, shared: 1, baseline_only: 0 },
    head_sha: "abc",
    analysis_id: "ana_1",
    provenance: provenance(),
    areas: ["pkg/loaders"],
    status: "open",
    ...p,
  };
}

export function finding(p: Partial<RoutedFinding> = {}): RoutedFinding {
  return {
    id: "rf_1",
    finding_id: "fnd_1",
    lane: "edge",
    action: "raise",
    title: "Include paths can escape the base directory",
    statement_md: "Resolve the path and check it stays inside the base.",
    category: "security",
    category_label: "Security",
    severity: "high",
    kind: "change_request",
    source: "lens",
    anchor: { scope: "line", path: "pkg/loaders/yaml.py", side: "RIGHT", start_line: 44, end_line: 44 },
    confidence: "high",
    fixable: true,
    evidence: { lens_items: [{ id: "li_1", title: "Safe include paths" }], past_comments: [{ id: "c1", pr_number: 11, excerpt: "Please keep includes inside the config dir." }] },
    user_state: "open",
    ...p,
  };
}
