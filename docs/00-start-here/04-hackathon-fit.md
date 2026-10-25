# Hackathon fit

Track: **Coding & Agentic Engineering**. The official goal is "coding agents and developer tools: agents that write, run, and test code in Token Factory". The stand-out bar is "an agent that plans, writes, tests, and iterates on a real repo with minimal human input" (Hackathon ref 02).

## 1. Hard requirements, and how Keeper meets each

| # | Requirement (Hackathon ref 00) | How Keeper meets it | Where |
|---|---|---|---|
| 1 | Runtime call to the Token Factory inference API | Every model call goes to `https://api.tokenfactory.nebius.com/v1/` through the LLM gateway. The live features (analysis, fixes, Ask, Proof runs, Practice scoring) all call it. | [LLM gateway](../04-architecture/03-llm-gateway.md) |
| 2 | An NVIDIA open model served on Nebius | Nemotron 3.5 Lightning, Nemotron 3 Super and Nemotron 3 Ultra, by role | [Overview](01-solution-overview.md) §5 |
| 3 | A genuine attempt at the track goal | An agent that plans, writes and tests fixes, then reads failures and repairs them in a loop on a real repository (the demo repository's real pytest suite, or an imported repository) | [Fix loop](../02-methodology/08-fix-loop.md) |
| 4 | Installs and runs consistently | One command, `./run.sh`; offline tests; `./run.sh --check` | [`./run.sh`](../08-run/01-run-sh.md) |
| 5 | Demo URL free to use until Dec 15 | A Nebius Serverless Endpoint with an access-code gate (code given in the testing instructions), spend caps and a model fallback | [Judging operations](../09-deployment/03-judging-operations.md) |
| 6 | Video under 3 minutes | The product is designed around a 4-act, 2:50 story; the tour mirrors it | [Submission](../09-deployment/04-hackathon-submission.md) |
| 7 | Public repo, licence, README | Apache-2.0 `LICENSE` at the root; a README with a models-and-Nebius table | [Submission](../09-deployment/04-hackathon-submission.md) |
| 8 | Description, track, feedback | Templates in the submission document | same |
| 9 | New work after Aug 26, 2026 | All code is new; the prior-work statement says so | same |
| 10 | English | All materials | — |

## 2. Judging criteria: how each one is earned

| Criterion (equal weight) | What judges look for (Hackathon ref 04) | What Keeper shows |
|---|---|---|
| **Technological implementation** (also the first tie-breaker) | Effective use of Token Factory and Nemotron; which model does which task; "one thing done well" | Deliberate tiering (Lightning, Super, Ultra), shown on every Keeper note ("Super · 2.1 s"). A real plan-write-test-repair loop with sandbox branching. The Batch API and Serverless Jobs for bulk work. Structured outputs, retries, fallbacks and spend caps. |
| **Design** | A complete product, not a proof of concept; action first; aha within 2 minutes | It opens on the queue with a tour. The aha takes one click. Plain-language lanes. Chat where chat is the natural interface. Responsive from laptop to ultrawide. |
| **Potential impact** | A real problem and audience, backed by what is demonstrated | Maintainer attention (Tidelift, curl, xz). The demo shows minutes saved, a risky PR routed correctly and a contributor's measured growth. |
| **Quality of the idea** | Non-obvious; genuine understanding; published limits | The open model as the *ruler*, not the oracle. A residual you can measure. The Fidelity Test and Growth Test, with falsifiers shown live. Bias detection. Limits published in-app. |

## 3. Track baseline versus stand-out, per feature

| Track bar | Keeper |
|---|---|
| Baseline: "a code-completion wrapper" | Not applicable: Keeper never completes code in an editor. |
| Stand-out: plans | Ultra plans a fix from a finding, with the files to read, the edits and the tests to run. |
| Stand-out: writes | It applies the edits in a sandbox checkout of the PR head. |
| Stand-out: tests | It runs the project's own pytest suite (and ruff on changed lines). |
| Stand-out: iterates | It reads failures, repairs (up to N iterations) and branches two candidates from one checkpoint. |
| Stand-out: real repo | The demo repository is a real, runnable Python project (generated, then validated by its own tests), and import works on any public Python repository. |
| Stand-out: minimal human input | The shared lane is fully automatic. Edge fixes run on one click. Every result is test-verified. |

## 4. Optional extras, ranked by value for the score

1. **Token Factory Sandboxes** for the test loop. Request access per project now; the local runner is the fallback, and the README states why if it is used.
2. **Nebius Serverless Jobs** for lens recalibration and Proof runs (visible to the Serverless product manager on the panel).
3. **Batch API** for Proof runs over the held-out set.
4. **Tavily** (optional, off without a key) is used only in the *Needs another reviewer* lane. When a PR adds a dependency, Keeper searches for its advisories and maintainer reputation and cites what it finds in the hand-off note. This makes it eligible for the Best Use of Tavily bonus. OSV.dev is always queried for known vulnerabilities, with no key needed.

## 5. Risks to compliance, and the mitigations built in

| Risk | Mitigation |
|---|---|
| A model ID is removed before Dec 15 | IDs come from config and env; a probe runs at start-up; a fallback chain (Ultra → Super, Lightning → Super); an alert on the status page |
| Credits run out (HTTP 402) | A spend cap per day and in total, per-session rate limits, a judges' access code; the snapshot keeps the app explorable; a banner states which features are live |
| Sandboxes access is not granted | The `local` or `docker` runner is used, and the README and Settings state it |
| Judges do not run it | The video and README carry the story, and the tour and screenshots match the video |
