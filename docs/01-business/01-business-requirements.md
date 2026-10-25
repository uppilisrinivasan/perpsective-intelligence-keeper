# Business requirements document (BRD)

| Field | Value |
|---|---|
| Product | Keeper: a maintainer's eye that scales |
| Framework | Perspective Intelligence (idea paper v2) |
| Competition | Nebius × NVIDIA Global AI Hackathon, Coding & Agentic Engineering track |
| Version | 1.0 (hackathon build) |
| Date | 25 October 2026 |

## 1. Background

Open source runs the economy: 98% of audited commercial codebases contain it, and its value is estimated at $8.8 trillion, produced mostly by 5% of developers. Those few people are stretched: 60% of maintainers are unpaid, and 60% have quit or considered quitting. Their scarcest resource is the attention needed to decide whether a change is safe (UC §3).

AI made three things worse:
1. **Contribution volume.** Contributions became nearly free and often low quality. curl ended its bug bounty, tldraw auto-closes outside PRs, and GitHub shipped settings to restrict PRs.
2. **Review to the average.** More than 95% of AI review comments fall into two categories, and AI suggestions are adopted far less often than human ones (16.6% against 56.5%). Defects are only 14% of what human reviewers comment on; the rest is project-specific judgment.
3. **A thinning successor pipeline.** One-time contributors' merge rates fell 18% against the expected trend, AI-assisted learners scored lower on concept checks, and junior developer employment fell.

The xz utils backdoor (March 2024) was planted in build scripts and binary test files that no reviewer looked at. It was caught by someone else's way of seeing.

## 2. Problem statement

A maintainer cannot give every incoming PR the attention it needs. Generic AI review adds noise instead of their judgment. Nobody routes the rare dangerous change to the right human eye. And the maintainer's way of seeing, written down publicly in thousands of review comments, is neither used to scale them nor handed down to successors.

## 3. Business objectives

| ID | Objective | Measure of success in v1 (demonstrated on the demo project and on at least one imported real repository) |
|---|---|---|
| BO-1 | Cut maintainer review time without cutting safety | Estimated attention for the Monday queue ≤ 40% of reviewing every PR in full. Zero risk-signal PRs in *Handled for you*. |
| BO-2 | Carry the maintainer's own judgment, not the average | On held-out PRs, Keeper recovers significantly more of the maintainer's substantive comments than the generic baseline (paired bootstrap, 95%), with no more noise per PR, and passes the caricature check. |
| BO-3 | Turn findings into tested fixes | ≥ 70% of fixable shared-ground and edge findings in the demo queue end in a fix that passes the full test suite within the configured iteration limit. |
| BO-4 | Route what nobody can see to someone who can | Every planted unknown-to-both PR goes to *Needs another reviewer* with a hand-off note naming the risk signals. |
| BO-5 | Grow successors | Practice shows a learner's unassisted recall of the maintainer's findings before and after, with costly misses named. Demo learner data shows a measurable change, stated as illustrative. |
| BO-6 | Keep the maintainer in control of their lens | Opt-in consent, private by default, exportable, revocable. Keeper never posts, merges or closes. |
| BO-7 | Win on the judging criteria | Aha within 30 s of video and within 2 minutes of use. Visible model tiering. Published limits. |

## 4. Stakeholders

| Stakeholder | Interest | Influence on v1 |
|---|---|---|
| Maintainers of widely used projects | Time, safety, succession, owning their lens | Primary user; drives the Queue, PR view and Lens |
| Contributors and would-be successors | Learn the project's taste; earn trust | Practice |
| Security, performance or release reviewers | Receive the right PRs with context | Hand-offs |
| Projects and foundations | Sustainability, fewer incidents | Proof metrics, export |
| Hackathon judges (Nebius, NVIDIA, Tavily) | Effective Nemotron and Token Factory use; product completeness | Tour, model labels, Proof, Settings → Usage |
| Authors of review comments (copyright holders) | Attribution and consent | Import consent, attribution |

## 5. Business requirements

| ID | Requirement | Priority |
|---|---|---|
| BR-1 | Keeper MUST learn a specific maintainer's lens from their review behaviour (comments, change requests, rejections) and from outcomes, never from a self-description or persona prompt. | Must |
| BR-2 | Keeper MUST measure that lens against a pinned, inspectable open-model baseline (Nemotron on Token Factory) and show the difference. | Must |
| BR-3 | Keeper MUST triage open PRs into the four lanes and estimate the maintainer attention they need against a weekly budget. | Must |
| BR-4 | Keeper MUST draft reviews in the maintainer's lens, citing the maintainer's own past reviews as evidence, labelled as Keeper's. | Must |
| BR-5 | Keeper MUST write, test and iterate on fixes in an isolated sandbox using the project's own tests, and present the passing diff with its test log. | Must |
| BR-6 | Keeper MUST route PRs with risk signals outside the maintainer's competence to another person's lens, with a hand-off note, and MUST never route a risk signal down. | Must |
| BR-7 | Keeper MUST prove its fidelity on held-out PRs against the baseline, with uncertainty, and MUST show the falsifiers from the papers as live checks. | Must |
| BR-8 | Keeper MUST offer contributors an unassisted held-out review check, before and after a practice session, and report growth without flattering. | Must |
| BR-9 | Keeper MUST calibrate lens items against outcomes and flag concerns that track a group of contributors rather than the code. | Must |
| BR-10 | Keeper MUST version the lens, show a lens diff, and show the maintainer's growth residual and health state. | Must |
| BR-11 | Keeper MUST give the maintainer ownership: consent, a private-by-default lens, export as a skill package, pausing, editing and revoking. | Must |
| BR-12 | Keeper MUST provide a conversational assistant that answers questions and starts actions over all of the above, with citations. | Must |
| BR-13 | Keeper MUST work out of the box on a committed synthetic demo project whose data matches the GitHub API schema, and MUST be explorable without an API key. | Must |
| BR-14 | Keeper SHOULD import a public repository's history through the GitHub API with the same adapters, under a consent and attribution policy. | Should |
| BR-15 | Keeper MUST run locally with one command and MUST be deployable to Nebius for judging, using Token Factory for all inference. | Must |
| BR-16 | Keeper MUST be usable by a first-time user (a judge) without instructions. | Must |
| BR-17 | Keeper SHOULD show where the maintainer's eye matters most (the edge map), and where generic review is enough. | Should |
| BR-18 | Keeper SHOULD check new dependencies against OSV and, when configured, Tavily, for the unknown lane. | Should |

## 6. Constraints

- **Deadline:** submission by Fri 30 Oct 2026, 10:00 PT. The demo stays live until Dec 15, 2026.
- **Platform:** all inference on Nebius Token Factory with NVIDIA Nemotron models. Other services are optional.
- **Data:** no real person's private data in the demo. Real review comments are used for evaluation with attribution; maintainers are named publicly only with permission.
- **Budget:** hackathon credits (about $25–50 of Token Factory). Spend caps are mandatory.
- **Team:** small; AI agents build most of the code from these documents.

## 7. Assumptions

1. Nemotron model IDs listed in the README index remain served, or the fallback chain covers removals.
2. Token Factory supports structured output (`json_schema` or `json_object`) and tool calling for these models. The gateway probes this and degrades gracefully.
3. Token Factory Sandboxes access may or may not be granted; the local runner suffices.
4. Judges use a laptop or desktop browser (latest Chrome, Edge, Firefox or Safari).

## 8. Success criteria for the hackathon

- [ ] Every Must requirement above is demonstrated in the deployed app.
- [ ] The Proof headline on the demo project passes its configured criteria, and an imported real repository result is reported, whatever it shows.
- [ ] The video is under 3:00, with the aha by 0:30.
- [ ] Zero secrets in git history; `./run.sh` works on a clean clone on macOS and Linux.

## 9. Risks

| Risk | Likelihood | Impact | Response |
|---|---|---|---|
| The lens does not beat the baseline on real data | Medium | High | Report it honestly; the papers name it as a falsifier. Show the demo result and the real result side by side. |
| Synthetic data looks contrived | Medium | Medium | Schema validation against GitHub's OpenAPI; real code and tests; varied voices; planted phenomena have realistic base rates. |
| The judge cannot find the aha | Low | High | The tour opens automatically on first visit; a "Show me" button on Queue. |
| Cost overrun during judging | Medium | High | Spend caps, cached analyses, judges' access code, Batch API. |
| Impersonation concerns | Low | High | Never posts; Keeper labels; consent flow; private lens. |
