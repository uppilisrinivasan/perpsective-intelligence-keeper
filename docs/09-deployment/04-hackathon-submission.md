# Hackathon submission

Deadline: **Fri 30 Oct 2026, 10:00 PT (22:30 IST)**. Submit (not just save) on Devpost. Requirements: Hackathon ref 03.

## 1. Repository README (template for the root `README.md`)

The root README is written at the end of the build from this outline. Numbers come from the actual Proof run and the usage meter; never from these docs.

```markdown
# Keeper: a maintainer's eye that scales

> Keeper learns what one open-source maintainer notices in code review that generic AI misses, uses it to
> triage their pull-request queue, writes and tests the fixes they'd ask for, and proves it on PRs it never saw.
> Built on NVIDIA Nemotron via Nebius Token Factory.

[Demo](<url>) (access code in the Devpost testing instructions) · [Video](<youtube>) · Apache-2.0

![Keeper queue](docs/assets/screenshot-queue.png)

## Quick start
    git clone <repo> && cd <repo> && ./run.sh
Opens http://127.0.0.1:8430. Without a key you see saved results from a real run.
To run live: put NEBIUS_API_KEY=<your key> in .env (created by ./run.sh) and restart.
Requirements: Python 3.11+, Node 20.19+, git. Docker optional.

## What it does
(The loop in 5 bullets: Find, Build, Grow; four lanes; fix and test; proof; practice.)

## How NVIDIA Nemotron and Nebius are used
| Task | Model (Token Factory ID) | Why this model |
|---|---|---|
| Reading review history, lens recall over a long digest, triage signals, fix verification | nvidia/Nemotron-3_5-Lightning | 1M context, cheapest, fast |
| Generic review (the ruler), lens review, matching, review drafts, hand-off notes, Ask | nvidia/nemotron-3-super-120b-a12b | Strong reviewer at moderate cost; the pinned ruler |
| Building the lens, planning and repairing fixes, calibration notes | nvidia/Nemotron-3-Ultra-550b-a55b | Hardest reasoning, used sparingly |
Other Nebius services: Token Factory Batch API (Proof runs), Token Factory Sandboxes (fix-and-test, if access granted), Serverless Endpoint (the demo), Serverless Jobs (lens building and Proof runs), Object Storage, SecretStash, [Managed PostgreSQL].
Where Token Factory sped up our workflow: (data generation volume, batch evaluation, model comparison in the Playground, …: fill in with facts).

## Results (from the committed Proof run)
(Recall Keeper vs generic review with intervals, noise per PR, caricature ratio, falsifiers; cost per PR analysed; with the caveat that the demo world is synthetic and the real-repository run.)

## Architecture
(The diagram from docs/04-architecture/01-system-architecture.md, and a link to docs/.)

## Data
Synthetic demo world with the exact GitHub REST API schema; AI generated the values only. Ground truth kept separate. See docs/03-data/.

## Known limitations and failure cases
(Synthetic data; small held-out set; matching judged by a model; local sandbox isolation; what isn't tested (falsifiers marked "not tested"); consent model for real people; ...)

## Configuration and secrets
.env (never committed) · .env.example · docs/07-configuration/

## Prior work
All code was written after 26 Aug 2026. The idea papers (docs/*.docx) predate the build and are the design input.

## Licence
Apache-2.0
```

## 2. Video script (target 2:50)

Follows the organisers' guidance: problem first, aha by about 0:30, Nemotron and Token Factory named in the audio, which model does what.

| Time | Screen | Voice-over (outline) |
|---|---|---|
| 0:00–0:15 | A real-looking queue, numbers on screen | "Open-source maintainers are the bottleneck of software. Every PR waits for one person's eye, and generic AI review doesn't see what they see." |
| 0:15–0:35 | Tour step 1: Compare on the aha PR | "This is a past PR. A strong generic reviewer, NVIDIA Nemotron 3 Super, missed this. The maintainer caught it. Keeper, trained only on earlier reviews, catches it too, and shows why." |
| 0:35–1:15 | Fix and test, live | "Keeper's agent plans the fix with Nemotron 3 Ultra, writes it, and runs the project's real tests in a sandbox (Token Factory Sandboxes if access was granted; otherwise say "an isolated sandbox"). The first try fails; it reads the failure, repairs, and passes." |
| 1:15–1:50 | Queue, lanes, unknown row, hand-off | "On Monday's queue, Keeper splits PRs into what's handled, what needs the maintainer's eye, what they tend to miss, and what neither knows. A build-script change goes to the security reviewer, with an OSV and web check." |
| 1:50–2:10 | Practice result | "A contributor practises on past PRs and learns to notice what the maintainer notices, measured before and after." |
| 2:10–2:35 | Proof and the models slide | "On held-out PRs, Keeper recovers X% of what the maintainer raised against Y% for generic review, without exaggerating them. Lightning reads the history, Super reviews and judges, Ultra builds the lens and the fixes, all on Nebius Token Factory, with Batch and Serverless Jobs for evaluation." |
| 2:35–2:50 | Limits and close | "It's synthetic data in the demo; we show our limits in the app. Keeper: a maintainer's eye that scales." |

Record from the deployed URL (or local with the same data), 1920×1080, browser zoom 100–125%, with no personal data on screen. Use no copyrighted music. Upload to YouTube as public; check that it plays logged out.

## 3. Devpost form

| Field | Content |
|---|---|
| Name and tagline | "Keeper" · "A maintainer's eye that scales" |
| Track | Coding & Agentic Engineering |
| Description | Inspiration · What it does · How we built it (models table) · Challenges · Accomplishments · What we learned · What's next |
| Built With | Nebius Token Factory, NVIDIA Nemotron 3.5 Lightning, Nemotron 3 Super, Nemotron 3 Ultra, Nebius AI Cloud Serverless (Endpoints, Jobs), Token Factory Batch API, Token Factory Sandboxes (if used), Tavily (if used), OSV.dev, FastAPI, React, Python, TypeScript |
| Demo URL | The endpoint URL |
| Testing instructions | "Open <url>, enter the access code <code>. The 3-minute tour starts automatically. Live actions (Analyse, Fix and test, Ask, Run Proof) call Nemotron on Token Factory; a daily budget keeps it available until Dec 15. To run locally: `git clone … && ./run.sh`." |
| Video | YouTube URL |
| Repository | Public URL, Apache-2.0 detected in About |
| Prior work | As in the README |
| Feedback | Section 4 |
| City | Only if attended in person |

## 4. Feedback (required; also judged for Most Valuable Feedback)

Fill one block per tool, from notes kept during the build (`docs/09-deployment/feedback-notes.md`, created during the build):

```markdown
### <Tool: Token Factory API | Batch API | Sandboxes | Serverless Endpoints | Serverless Jobs | Nemotron 3.5 Lightning | Nemotron 3 Super | Nemotron 3 Ultra>
- What we used it for:
- What worked well: (specific: latencies measured, structured output behaviour, …)
- What needs improvement: (specific: e.g. json_schema support per model, reasoning-control parameters, model-ID removals, 402 behaviour, rate-limit headers, Sandboxes access)
- Onboarding, zero to hello world: (time taken, blockers)
- Would we build with it again, and why:
```

Collect the gateway's metrics for this: per-model median and p95 latency, structured-output repair rate, and fallback events (`python -m keeper.cli usage --report feedback`).

## 5. Final checklist

Use Hackathon ref 03 §8 in full. In addition:
- [ ] `git log -p | gitleaks detect --pipe` is clean; `.env` was never committed.
- [ ] `data/` is committed and the manifest verifies on a clean clone.
- [ ] A clean clone runs with `./run.sh` on macOS and Linux (no key → saved results; with key → live).
- [ ] The README numbers match the committed Proof run.
- [ ] The tag `v1.0.0` is pushed; the deployment runs that tag.
