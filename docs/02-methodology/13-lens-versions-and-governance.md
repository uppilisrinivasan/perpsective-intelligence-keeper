# Lens versions, ownership and governance

> "A lens may be the most personal artefact a person can produce: not a record of what they did, but of how they see." (IP §5 L5)

## 1. Versions

- A `lens` belongs to one person in one project. It has `status` ∈ `active`, `paused`, `revoked`.
- A `lens_version` is immutable: `{version, cutoff_at, ruler_id, change_reason, parent_version, items, digest, card, build_stats}`.
- `change_reason` ∈ `initial_build`, `rebuild_new_reviews`, `feedback_update`, `recalibration`, `owner_edit`, `ruler_change`.
- The **current version** is the latest version with `status = ready`. Proof and Practice may pin older versions.

### Producing v_{k+1}

| Trigger | What changes |
|---|---|
| New reviews by the person (import refresh, or held-out data rolling into training) | Re-run L2–L7 with the new cutoff |
| Feedback in Keeper (accept, edit, dismiss, add note) | Feedback events become residual samples (`accept` → the lens finding becomes a human finding of P with `kind = comment`, `evidence = accepted_suggestion`, weight `feedback.accept_weight` 0.7; `edit` → the same with the edited text, weight 0.9; `dismiss` → a counter-example for the cited items; `add note` → a human finding, weight 1.0). Then incremental L6: re-cluster with the new samples, keeping item IDs stable where a cluster's membership overlap (Jaccard) ≥ 0.5. |
| Owner edits (wording, turn off) | A copy with the edited items; no model call |
| Recalibration | Statistics and status only |
| A new ruler | Full re-measure |

Accepted suggestions are weighted below independent comments because they risk the lens learning from itself (performative prediction, IP §6.3). The weight is configurable, and Proof's growth panel reports the share of training samples coming from accepted suggestions.

## 2. The lens diff (FR-LENS-9)

`keeper.lens.diff(v_a, v_b)` matches items across versions by ID; for new IDs, by statement similarity ≥ 0.75 and the same category. It reports:

| Change | Rule | UI phrasing (copy file) |
|---|---|---|
| `added` | In b, with no match in a | "Started noticing: …" |
| `retired` | In a, missing or retired in b | "Stopped flagging: …" |
| `reworded` | Matched; statement similarity < 0.9 | "Now described as: …" |
| `strengthened` / `weakened` | Support or hit rate changed by ≥ 25% relative | "More sure: …" / "Less sure: …" |
| `status_changed` | Any status change | "Now proven by outcomes", "Possible bias found", … |
| `blind_spot_closed` | A blind-spot item in a, not in b, because P now flags it (P's R− for the item fell below the threshold) | "Blind spot closing: …" |

The `lens_diff_summary` prompt (`judge`) writes a 3-bullet human summary of the computed diff. It sees the diff only and cannot add changes.

## 3. Consent (FR-GOV-1)

A `consent` row: `{person_id, project_id, scope: build_lens | evaluation_only | share_in_project, granted_by, granted_at, revoked_at, text_version, synthetic: bool}`.

- **Demo:** the generator creates `synthetic = true` consent rows for the demo maintainer and the security reviewer. The UI shows "Fictional person; consent simulated".
- **Import:** the importing user acknowledges the attribution terms (FR-IMP-4), which creates `evaluation_only` for the named maintainer. Turning it into `build_lens` requires "I am this maintainer, or I have their permission" (a checkbox plus a typed login). This is a soft control appropriate to a local tool, and it is documented as such.

## 4. Privacy and sharing (FR-GOV-4)

- Lenses are used only for routing in their project, and are visible only to their owner (the maintainer role) by default.
- `share_in_project` lets contributors' Practice use the lens. In the demo it is on, because Practice is the point.
- The lens card section *Possible bias* is never shared without the owner opting in per export.

## 5. Export and import (FR-LENS-11, FR-LENS-12)

The export package `keeper-lens-<login>-v<k>.zip`:

| File | Content |
|---|---|
| `lens.json` | Items (without owner-only fields unless chosen), version metadata, ruler, statistics. Validated by `config/schemas/lens_package.schema.json`. |
| `LENS.md` | The lens card |
| `SKILL.md` | Agent Skills format: front matter (`name: review-like-<login>`, `description: …`), then instructions for applying the lens to a PR (the lens-review procedure in prose, referencing `lens.json`), and the rule "label your output as a lens suggestion; never post as <login>" |
| `exemplars.jsonl` | Exemplars as `{statement, path, hunk, pr_url, created_at}`, **only if** the owner ticks "Include my past comments". Imported projects require attribution fields. |
| `LICENSE.txt` | The owner's chosen terms (default "All rights reserved. Personal use by the owner.") |
| `PROVENANCE.json` | Ruler, model IDs, build jobs, cutoff, counts |

Import validates the schema, creates a new lens (or a new version of an existing lens of the same person), and requires consent.

## 6. Pause and revoke (FR-GOV-2, FR-GOV-3)

- **Pause:** routing and Practice stop using the lens immediately. The UI shows lens findings as "(paused)" and routes as if no lens existed: baseline findings become `baseline_only`, and risk signals still force `unknown`.
- **Revoke:** a confirmation dialog requires typing the login. Then lens versions, items, digests, packages, and residual samples derived from feedback are deleted. A tombstone `{lens_id, person_id, revoked_at, counts}` remains in the audit log. `consent.revoked_at` is set. Rebuilding requires new consent.

## 7. Audit log (FR-GOV-8)

`audit_events {id, at, actor_role, action, object_type, object_id, details_json}` for builds, edits, exports, imports, pauses, resumes, revokes, consent changes and lane overrides. It is visible in Lens → History.
