# Scope and release plan

## 1. v1 scope (hackathon, due 30 Oct 2026)

### Must (the demo fails without these)

| Area | Included |
|---|---|
| Data | Synthetic demo project generated and committed: GitHub-shaped mirror, git bundle, ground truth, snapshot. The data loader. |
| Pipeline | H extraction, baseline and ruler, matching and residual, lens build (v1, v2), lens apply, routing, triage (including slop), outcomes, calibration (including bias), fix loop with the local runner, fidelity test, growth (Practice plus G and health state), lens diff, export and revoke. |
| UI | Shell, tour, Queue, PR view (Diff and Compare), Fix panel, Ask (full page and drawer), Lens, Proof, Practice, Settings, no-key mode, responsive matrix. |
| Platform | Token Factory gateway with tiering, fallbacks, caps, cache and audit. `./run.sh` with `--check`, `--test`, `--dev` and `--reset`. |
| Deployment | One container; Nebius Serverless Endpoint; access code; judging operations. |
| Docs | README with the models table, limits and feedback. |

### Should (planned; dropped in this order if time runs out)

1. Token Factory Sandboxes runner (`contree`).
2. Nebius Serverless Jobs runner for recalibration and Proof (`JOB_RUNNER=nebius`).
3. Batch API for Proof runs.
4. Real-repository import, plus one real-repository Proof result in the README.
5. Edge map (Find).
6. OSV and Tavily checks for new dependencies.
7. Docker runner.
8. Lens package import.

### Could

- Maintainer-pushed commits as findings (FR-H-5).
- Auto-fix of the shared lane in the background (FR-TRI-7).
- The CodeReviewer dataset as a second evaluation set.

## 2. Out of scope for v1, with the reason

| Item | Why not now | Where it goes |
|---|---|---|
| Posting reviews or suggestions to GitHub; a GitHub App with webhooks | Consent and impersonation risk; not needed to prove the idea | [Beyond the hackathon](../09-deployment/05-beyond-the-hackathon.md) |
| Multi-user accounts and tenancy | Single-workspace demo | same |
| Steering-vector or LoRA lenses | Needs self-hosted weights on GPUs; the lens card plus exemplars is enough to test fidelity | same |
| Languages other than Python for fixes | The test runner recipes are Python-only in v1. Analysis (H, C, R, lens) is language-agnostic. | same |
| The commons speed (absorption into the next model) | Needs model generations | Documented in Proof's limits |
| Vigil and Margins | Same engine, different adapters | same |

## 3. Release checkpoints

| Checkpoint | Content | Gate |
|---|---|---|
| R0 Data | `data/` generated, validated, committed | `python -m keeper.datagen validate` is green; size ≤ budget |
| R1 Engine | The pipeline produces the snapshot on the demo project; `./run.sh --eval` meets thresholds | `config/eval.yaml` thresholds |
| R2 Product | All screens on the snapshot; no-key mode; responsive matrix | E2E green |
| R3 Live | Live analysis, fix, Ask and Proof with a key | Manual live run recorded in `docs/build-log.md` |
| R4 Deployed | Nebius endpoint live; access code; caps | Smoke test in [Deployment steps](../09-deployment/02-nebius-deployment-steps.md) §8 |
| R5 Submitted | Video, README, Devpost form, feedback | [Submission checklist](../09-deployment/04-hackathon-submission.md) |

The day-by-day plan is in [Implementation plan](../10-build/02-implementation-plan.md).
