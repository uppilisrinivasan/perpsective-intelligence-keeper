# Solution overview

## 1. The problem in one paragraph

Critical open source rests on a few overloaded maintainers, and 60% of them are unpaid. Their scarcest resource is attention: every change needs someone who knows the project to decide whether it is safe. AI has made contributions nearly free (curl ended its bug bounty because about one submission in five was AI slop). AI reviewers also review to the average: more than 95% of AI review comments fall into two categories, and developers adopt 16.6% of AI suggestions against 56.5% of human ones. AI is also thinning the pipeline of successors. The xz utils backdoor showed what is at stake: the payload sat in build scripts and binary test files that no reviewer looked at. *(Use-case paper §3.)*

## 2. What Keeper is

Keeper learns **what this maintainer notices that a generic reviewer does not** (the *maintainer's residual*) from the public record of their reviews. It turns that into a **lens**: a versioned, inspectable review skill that the maintainer owns. It then runs the **Perspective Loop** on the project.

| Loop step | What Keeper does | Where the user sees it |
|---|---|---|
| **Find** | Mines the review history for the areas where the maintainer's residual is large *and* costly, meaning a miss there led to reverts or bugs. | Lens → *Where your eye matters most* |
| **Build** | Triages the incoming queue into four lanes, reviews each pull request (PR) through the lens, drafts the review the maintainer would write (citing their own past reviews), and writes and tests the fixes they would ask for in a sandbox, iterating until the tests pass. | Queue, Pull request |
| **Grow (AI)** | Learns from every accept, edit and dismiss. It recalibrates the lens against outcomes (merges, reverts, post-merge bugs), versions it (v1 → v2 → v3), and shows a lens diff. | Lens → *Versions* |
| **Grow (people)** | Contributors take a held-out review check: given real past PRs, do they flag what the maintainer flagged? They take it before and after a practice session, unassisted. | Practice |
| **Prove** | Runs the Perspective Fidelity Test on held-out PRs. It measures the share of the maintainer's substantive comments recovered, the noise avoided and caricature, each against the generic baseline. | Proof |
| **Ask** | A chat assistant over all of the above: "Why is #412 in *Needs another reviewer*?" or "What does my lens say about the include resolver?" | Ask (and the *Ask about this* drawer on every screen) |

### The four lanes (who teaches whom)

Each finding, and each PR as a whole, falls into one of four cases. Each case gives Keeper a different job.

| Case (code name) | UI label | Meaning | What Keeper does | Who grows |
|---|---|---|---|---|
| Shared ground (`shared`) | **Handled for you** | Both the generic review and the lens flag it: style, missing tests, known bug patterns. | Comments, writes the fix, runs the tests and iterates until they pass. The maintainer need not look. | Nobody needs to |
| Maintainer's edge (`edge`) | **Needs your eye** | The lens flags it and the generic review misses it: invariants, history, threat model. | Drafts the review the maintainer would write, citing their past reviews, writes the fix they would ask for, and tests it. | The lens learns from the maintainer |
| Blind spot (`blind_spot`) | **Worth a second look** | The generic review flags it, and the maintainer historically misses it in a way outcomes showed was costly. | Surfaces it with evidence. Never merges on its own. | The maintainer |
| Unknown to both (`unknown`) | **Needs another reviewer** | Risk signals fire (build or release scripts, binary files, new dependencies) where neither lens is competent. | Routes the PR to a person with a different lens (for example a security reviewer) with a drafted hand-off note. | Both, through another person |

One rule is absolute: **the lens may add attention; it never removes it.** A PR with a risk signal is never placed in *Handled for you*. Keeper never merges, never closes, and never posts as the maintainer. Everything it writes is labelled as Keeper's.

## 3. Who uses it

| Persona | Primary job in Keeper |
|---|---|
| **Maintainer** (primary) | Clear the Monday queue in the two hours they have, without missing the one PR that matters. |
| **Contributor or successor** (secondary) | Learn to review like the maintainer and earn trust, with a record of how they grew. |
| **Another-lens reviewer**, for example security (tertiary) | Receive only the PRs that need their eye, with context. |
| **Hackathon judge** (the first real user) | Understand the idea and see it work within two minutes, without reading anything. |

Details: [Personas and journeys](../01-business/02-personas-and-journeys.md).

## 4. What v1 contains

v1 is the version for the hackathon. It runs locally with `./run.sh` and is deployable to Nebius.

1. **A complete synthetic open-source project, committed to git.** It has three years of history in exactly the schema of the GitHub REST API: PRs, files, reviews, review comments, issue comments, timelines, issues and check runs. It comes with a real git repository (as a bundle) whose test suite really runs, plus a separate ground truth. AI wrote only the *values* (code, titles, comments). Code produced every structural and mechanical field, and real git and pytest produced diffs, hunks, SHAs and test results. See [Synthetic data generation](../03-data/06-synthetic-data-generation.md).
2. **Import of a real public repository**, opt-in, through the GitHub API with the same adapters. The demo of a real project shows aggregate metrics and attributes every quotation.
3. **The full pipeline:** findings extraction (H), the pinned baseline (C), matching and residual (R), lens building, lens application, routing and triage, the fix loop with a sandbox, outcomes and calibration (including a bias check), the edge map, the Fidelity Test, the Growth Test, versioning and lens diff, and export and revocation.
4. **A web app with six destinations** (Queue, Ask, Lens, Proof, Practice, Settings), the PR view and a guided tour. It is responsive from laptops to ultrawide monitors.
5. **A saved snapshot** of every analysis of the demo project, committed to git, so the app is fully explorable without an API key. Live features are enabled when `NEBIUS_API_KEY` is present.
6. **Deployment documentation for Nebius:** the app on a Serverless Endpoint, recalibration and fidelity runs as Serverless Jobs, all inference on Token Factory, test runs in Token Factory Sandboxes with a local fallback.

Out of scope for v1, and documented as next steps: posting to GitHub, a GitHub App with webhooks, multi-tenant accounts, steering-vector or LoRA lenses, Vigil and Margins. See [Scope and release plan](../01-business/05-scope-and-release-plan.md).

## 5. How Nemotron is used (model tiering)

| Step | Model (role in config) | Why this model |
|---|---|---|
| Hold the maintainer's full review history and the PR together; triage; recall relevant past reviews | **Nemotron 3.5 Lightning** (`fast`) | 1M-token context holds years of reviews plus the diff, cheaply enough to run on every PR |
| Extract and classify findings from human comments; check fixes | Lightning (`fast`) | High volume, structured output |
| The generic baseline review (the ruler) | **Nemotron 3 Super** (`judge`), pinned prompt, temperature 0 | The same model as the lens review, so the *only* difference between baseline and lens is the lens |
| Review through the lens; draft comments; match findings; score practice answers | Super (`judge`) | Judgment at moderate cost |
| Build and recalibrate the lens; plan and repair fixes inside the test loop | **Nemotron 3 Ultra** (`deep`) | The hardest reasoning and the strongest coding model on Token Factory (70.7 on SWE-Bench Verified, as reported by NVIDIA); run rarely or in batch |
| Assistant (Ask) | Super with tool calling (configurable) | Tool use with judgment |
| Running the project's tests | **Token Factory Sandboxes**, or the local runner as a fallback | VM isolation, checkpoints and branches to try two fixes and keep the passing one |

All IDs come from `config/models.yaml` and the `.env` overrides. Nothing is hardcoded. See [LLM gateway](../04-architecture/03-llm-gateway.md).

## 6. Principles that every part of the build follows

1. **The open model is the ruler, not the oracle.** The baseline is pinned (model ID, prompt version, decoding parameters and static-tool versions) and stored as a *ruler* record. Residuals are only compared under the same ruler.
2. **Learn from behaviour, not self-description.** The lens is built from what the maintainer actually flagged, requested and rejected, never from a persona prompt.
3. **Route, do not default.** The four cases decide, finding by finding, whether Keeper automates, learns, teaches or hands off.
4. **The lens may raise attention, never lower it.** Risk signals cannot be routed into *Handled for you*.
5. **Reality decides.** Tests, reverts and post-merge bugs calibrate which parts of the lens are insight and which are bias.
6. **Test without the tool.** Growth counts only when it is measured unassisted, on held-out PRs.
7. **The lens belongs to the maintainer.** It is opt-in, private by default, exportable and revocable. Keeper never posts as them.
8. **Publish the limits.** The Fidelity Test reports confidence intervals and failure cases. The demo states that its data is synthetic.
9. **Nothing hardcoded.** Model IDs, thresholds, paths, prompts, copy and demo values live in configuration or data.
10. **Self-explanatory UI.** A judge reaches the *aha* within 30 seconds and understands every screen without help.

## 7. The demo story (under 3 minutes), which the product is designed around

| Time | Shown in the product |
|---|---|
| 0:00–0:30, the aha | Tour step 1: a real PR from the project's history. The generic Nemotron review lists style points. The maintainer's actual review caught something subtle (an include path that can escape the project root, which a similar earlier PR had already caused). Keeper, built only on *earlier* reviews, catches it too, and cites that PR. |
| 0:30–1:30, the build | Keeper writes the fix the maintainer asked for, runs the project's tests in a sandbox, reads the failure, repairs it and passes. A live log is shown, and each step names the Nemotron model that did it. |
| 1:30–2:30, triage and growth | Monday's queue of 12 PRs in four lanes. "Fits in your 2 hours: 41 min." The trusted newcomer's build-script change goes to *Needs another reviewer*. A contributor's practice score before and after a session. |
| 2:30–3:00, the numbers | Proof: the share of the maintainer's substantive comments recovered by Keeper against the generic review, the noise per PR, the caricature check, and the limits. |
