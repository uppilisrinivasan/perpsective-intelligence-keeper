# Idea-to-feature traceability

Every claim or mechanism in the two papers that Keeper must embody is listed here, with the requirement that implements it, the module that builds it, and the test that proves it. *IP* = idea paper, *UC* = use-case paper. If a row has no test, the feature is not done.

| # | Paper source | Claim or mechanism | Requirement | Module | Proven by |
|---|---|---|---|---|---|
| T1 | IP §4 | A perspective is a residual R(S) = H(S) − C(S) | FR-RES-1…5 | `keeper.residual` | `test_residual_partition` (every H and C finding lands in exactly one of shared, R+ or R−) |
| T2 | IP §5 L0, §8 | The baseline is pinned and inspectable; the ruler must hold still | FR-BASE-1…6 | `keeper.baseline` | `test_ruler_immutability` (changing any ruler field creates a new ruler; residuals under different rulers are never compared) |
| T3 | IP §5 L1 | Learn the lens from behaviour (flags, change requests, rejections), not from self-description | FR-H-1…6, FR-LENS-1 | `keeper.findings`, `keeper.lens.build` | `test_lens_inputs_are_behavioural` (lens building reads only findings and outcomes; no persona prompt exists) |
| T4 | IP §5 L2 | A lens is portable, composable, inspectable and revocable; the lens card and the skill | FR-LENS-6…12 | `keeper.lens.package` | `test_export_import_roundtrip`, `test_revoke_blocks_use` |
| T5 | IP §5 L3 | Agents look through the lens and return observations with reasons; they never take the bet | FR-APPLY-1…6 | `keeper.lens.apply` | `test_lens_findings_cite_items_and_exemplars` |
| T6 | IP §5 L4 | Compose lenses without averaging; lens distance as a design variable | FR-ROUTE-8…10 | `keeper.route.handoff` | `test_handoff_prefers_distant_competent_lens` |
| T7 | IP §5 L5 | Ownership, consent, revocation, provenance, calibration record | FR-GOV-1…8 | `keeper.lens.governance` | `test_no_lens_without_consent`, `test_provenance_on_every_item` |
| T8 | IP §6.1 | Find: perspective–problem fit, where the residual is large, a miss is costly, and reality answers fast | FR-FIND-1…4 | `keeper.find` | `test_edge_map_ranks_planted_areas_first` (demo ground truth) |
| T9 | IP §6.2, UC §3 | Four cases: automate, learn, teach, bring in another lens | FR-ROUTE-1…7 | `keeper.route` | `test_routing_accuracy_on_ground_truth` ≥ the threshold in `config/eval.yaml` |
| T10 | IP §6.2 | If the edge is not yet validated, build both versions and let reality decide | FR-FIX-9 | `keeper.fix` | `test_unvalidated_edge_builds_both` |
| T11 | IP §6.2 | Blind spots taught only where they matter (calibration is the filter) | FR-ROUTE-4, FR-CAL-3 | `keeper.route`, `keeper.calibrate` | `test_uncalibrated_baseline_only_is_not_blind_spot` |
| T12 | IP §6.3 | The lens is versioned (v1, v2, v3) with a lens diff | FR-LENS-8…10 | `keeper.lens.version` | `test_lens_diff_categories` |
| T13 | IP §6.3 | Growth residual G = H − L; healthy growth means costly R− shrinks while validated R+ holds | FR-GROW-7…10 | `keeper.growth` | `test_growth_residual_on_drift_slot` (the planted drift appears in G for v1 and disappears for v2) |
| T14 | IP §6.3 table | Health states: healthy, absorbed, self-caricature, deskilling, replaced | FR-GROW-9 | `keeper.growth.health` | `test_health_state_rules` (table-driven) |
| T15 | IP §6.5 | Help without hollowing: route, keep difficulty, test without the tool, do not flatter | FR-GROW-1…6, NFR-ETH-* | `keeper.growth.practice` | `test_practice_before_after_unassisted` (no hints or lens shown during before and after sessions) |
| T16 | IP §7 P4 | Perspective Fidelity Test: predict better than the baseline, without caricature | FR-FID-1…9 | `keeper.fidelity` | `test_fidelity_metrics_known_answer` (synthetic fixtures with known recall, noise and caricature) |
| T17 | IP §7 | The Growth Test: before and after, unassisted, on held-out situations | FR-GROW-1…6 | `keeper.growth` | `test_parallel_forms_balanced` |
| T18 | IP §7 P5 | Calibration: insight versus bias versus noise; outcomes arrive late | FR-CAL-1…7 | `keeper.calibrate` | `test_beta_posterior_and_status` |
| T19 | UC §3 | Concern that tracks a group, not the code, is flagged as bias | FR-CAL-5, FR-CAL-6 | `keeper.calibrate.bias` | `test_bias_slot_detected` (the planted first-timer bias is `bias_suspected`) |
| T20 | UC §3 | Triage the flood; routine and AI-generated changes go to the shared lane | FR-TRI-1…7 | `keeper.route.triage` | `test_slop_prs_in_shared_lane`, `test_slop_ignores_author_association` |
| T21 | UC §3 | The build-script change from the trusted newcomer goes to a person with a security lens | FR-ROUTE-5…7 | `keeper.route.risk` | `test_risk_signal_never_shared` |
| T22 | UC §3 demo | The baseline lists style points; the maintainer caught something subtle; Keeper, trained only on earlier reviews, catches it | FR-TOUR-1, FR-FID-4 | `keeper.fidelity`, frontend tour | `test_no_leakage_cutoff` and the tour's aha case being from the held-out set |
| T23 | UC §3 demo | Keeper writes the fix, runs the tests in a sandbox, reads the failure, repairs and passes | FR-FIX-1…12 | `keeper.fix` | `test_fix_loop_repairs_after_failure` (fake provider), E2E `fix_live.spec.ts` |
| T24 | UC §3 | Two fixes tried from one checkpoint; keep the passing one | FR-FIX-6 | `keeper.fix.branches` | `test_branching_keeps_passing` |
| T25 | UC §3 | A held-out review check for contributors | FR-GROW-1…6 | `keeper.growth.practice` | E2E `practice.spec.ts` |
| T26 | UC §3 risks | Opt-in; never posts as the maintainer; every comment labelled as Keeper's | FR-GOV-1, FR-REV-5 | `keeper.review` | `test_exported_review_has_keeper_label` |
| T27 | UC §3 risks | Never merges on its own | FR-FIX-11, NFR-SAFE-1 | (no merge code path exists) | `test_no_github_write_calls` (the GitHub client exposes read methods only) |
| T28 | UC §3 risks | Gaming: the lens is not published by default; unusual changes go to the unknown lane | FR-GOV-4, FR-ROUTE-5 | `keeper.lens.governance` | `test_lens_private_by_default` |
| T29 | UC §3 risks | Drift: the lens is versioned, refreshed and re-tested on recent PRs | FR-LENS-10, FR-FID-8 | `keeper.lens`, `keeper.fidelity` | `test_rebuild_reruns_fidelity_on_recent` |
| T30 | UC §3 data | Review comments are their authors' copyright: use them to evaluate, attribute quotations, ask before naming | FR-IMP-4…6 | `keeper.sources.github.importer` | `test_imported_quotes_attributed`, `test_import_requires_consent_ack` |
| T31 | UC §3 build | Lightning holds history and the PR together; triage on Lightning; review on Super; fixes on Ultra; Sandboxes run tests | FR-LLM-*, config | `keeper.llm`, `config/models.yaml` | `test_prompt_roles_match_catalog` |
| T32 | UC §3 | Fallback to a local container if Sandboxes access is missing, with the reason stated in the README | FR-FIX-3 | `keeper.sandbox` | `test_runner_selection_and_banner` |
| T33 | IP §8 | Zero-retention inference; minimal data sent | NFR-PRIV-* | `keeper.llm.redact` | `test_no_secret_shapes_in_prompts` |
| T34 | IP §10, UC §5 | What would prove us wrong: published as live checks | FR-FID-9 | `keeper.fidelity.falsifiers` | Proof shows each falsifier as pass or fail |
| T35 | IP §6.4 | Three speeds: build (minutes), grow (weeks), commons (model generations) | FR-GROW-11 (documented; commons is out of scope for v1, see scope) | `keeper.growth` | n/a for commons; build and grow are tested above |
