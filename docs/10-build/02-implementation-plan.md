# Implementation plan

The deadline is **Fri 30 Oct 2026, 10:00 PT (22:30 IST)**. Work is organised as **milestones** with exit gates, mapped to days. Milestones can run in parallel across agents where the dependencies allow (shown in the "Needs" column). Each milestone lists the documents to read. An agent reads only those, plus [Rules for AI agents](04-rules-for-ai-agents.md).

## 1. Milestones

| ID | Milestone | Needs | Read | Exit gate |
|---|---|---|---|---|
| M0 | **Skeleton:** repository tree, `run.sh` (install, build, serve a "hello" page), `.env.example`, `.gitignore`, pre-commit, CI, config loader with schemas, DB + migrations, FastAPI app with `/health` and `/status`, the React shell with routes and tokens | — | 10-build/01, 07-configuration/*, 08-run/01, 04-architecture/01-02, 06-frontend/02-04 | `./run.sh` on a clean clone serves the shell; `./run.sh --check` and `--test` pass; gitleaks is clean |
| M1 | **LLM gateway:** providers (nebius, fake), roles, probe, fallback, structured output and repair, retries, rate limits, cache, meter, spend caps, redaction; prompt loader with `versions.lock` | M0 | 04-architecture/03, 02-methodology/15 | Gateway tests with the fake provider; a live probe with a key |
| M2 | **Sources and ingest:** GitHub schemas extracted; mirror reader; ingest to DB; git bundle unbundle; JUnit parsing; code index | M0 | 03-data/02, 03, 09 | Ingest of a small hand-written fixture mirror passes schema validation |
| M3 | **Data generation** (G0–G12), validations V1–V9b, commit `data/` | M1, M2 | 03-data/05-08 | `python -m keeper.datagen validate --deep` green; `data/` ≤ 35 MB; committed (R0) |
| M4 | **Engine, learning:** findings extraction, baseline and ruler, matching, residual, lens build, outcomes, calibration, bias, edge map, digest, lens card | M1, M2 (uses M3 data when ready; fixtures until then) | 02-methodology/01-05, 09, 10, 13 | `./run.sh --eval` extraction, matching and edge-map targets met on the demo data |
| M5 | **Engine, analysis:** context, lens apply (recall, review), routing, risk signals, triage, slop, attention, review drafts, hand-offs with OSV and Tavily | M4 | 02-methodology/06, 07, 14 | Routing macro-F1 and unknown recall = 1.0 on the live queue; the absolute-rule property test passes |
| M6 | **Fix loop and sandboxes:** local runner first, then docker, then contree; fix runner with branches and repair | M1, M2 | 02-methodology/08, 04-architecture/05 | The demo's fix PR gets a passing fix with at least one repair on the local runner |
| M7 | **Proof and Practice:** fidelity runs (with batch), falsifiers; item bank, forms, sessions, scoring, G and health | M4, M5 | 02-methodology/11, 12 | Fidelity pass criteria computed on the demo; Practice end-to-end via the API |
| M8 | **API, jobs, assistant:** all endpoints, SSE, jobs, confirmations, the assistant loop with tools and cards, tour service, snapshot loading, no-key mode | M5–M7 (endpoints can be stubbed earlier from schemas) | 05-api/*, 04-architecture/04, 06 | OpenAPI snapshot test; contract tests per endpoint; no-key mode serves every screen's data |
| M9 | **Frontend screens:** Queue, PR (Diff, Compare, Fix, Draft, Hand-off), Ask and drawer, Lens (all tabs), Proof, Practice, Settings, states, tour | M0 for the shell; M8 for real data (use the OpenAPI types and MSW mocks before) | 06-frontend/* | E2E flows pass at all viewports; axe clean; no hardcoded strings or values |
| M10 | **Snapshot:** run the full pipeline live on the demo, commit the snapshot (G12) | M3–M8 | 03-data/06 §G12, 08 | A clean clone in no-key mode shows the full tour from the snapshot |
| M11 | **Deploy:** image, endpoint, secrets, smoke test; optional Jobs runner, PostgreSQL | M10 | 09-deployment/01-02 | The smoke test passes on the public URL (R4) |
| M12 | **Submit:** README, screenshots, video, Devpost form, feedback | M11 | 09-deployment/03-04 | The checklist is complete; submitted (R5) |

## 2. Day plan (all times IST)

| Day | Focus | Milestones |
|---|---|---|
| Sun 25 Oct | Skeleton; gateway; GitHub schema extraction; fixture mirror; start datagen G0–G2 (world, repository code) | M0, M1, M2, M3 (start) |
| Mon 26 Oct | Datagen G3–G9 (history, PRs, reviews, outcomes); learning engine on fixtures; local sandbox runner; frontend shell, design tokens, Queue and PR on mocks | M3, M4, M6, M9 (start) |
| Tue 27 Oct | Data validated and committed (R0); analysis engine; fix loop; API endpoints and SSE; Ask backend; PR Diff, Compare and Fix panel UIs | M3 done, M5, M6, M8, M9 |
| Wed 28 Oct | Proof and Practice engine; tour service; Lens, Proof, Practice, Ask and Settings UIs; `./run.sh --eval` meets targets (R1) | M7, M8, M9 |
| Thu 29 Oct | Snapshot (M10); E2E and the responsive matrix (R2); live run recorded (R3); deploy to Nebius (R4); README and screenshots | M10, M11, M12 (start) |
| Fri 30 Oct (until 22:30 IST) | Video; Devpost form and feedback; final checklist; tag `v1.0.0`; submit by 20:00 IST at the latest, leaving buffer | M12 |

**Cut line** (if behind on Wed evening): drop the "Should" items in the order given in [Scope](../01-business/05-scope-and-release-plan.md) §1. Never drop: the absolute rule, no-key mode, `./run.sh`, the tour, Proof, the Keeper label, or the secret hygiene.

## 3. Parallel work by several agents

| Agent | Owns |
|---|---|
| A: platform | M0, M1, M8 (API and jobs), M11 |
| B: data | M2, M3, M10 |
| C: engine | M4, M5, M7 |
| D: agentic | M6, the assistant part of M8 |
| E: frontend | M9 (from day 1 against OpenAPI types and mocks) |

Interfaces between agents are the **pydantic models in `keeper.core.types`**, the **OpenAPI document**, and the **config schemas**. They are fixed in M0 and changed only with a note in `docs/build-log.md`.
