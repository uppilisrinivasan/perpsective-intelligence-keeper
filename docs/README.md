# Keeper: build documentation

**Keeper is a maintainer's eye that scales.** It learns what one open-source maintainer notices in code review that a generic AI reviewer does not, using the maintainer's public review history. It then uses that lens to triage the incoming pull-request queue, to draft the reviews that maintainer would write, and to write and test the fixes they would ask for. It also routes risky changes to a different human reviewer, proves on held-out pull requests that the lens is faithful, and trains contributors to notice what the maintainer notices.

Keeper is the first application of **Perspective Intelligence**. In that framework, a perspective is a *residual*: what a person notices minus what an open foundation model notices in the same situation. NVIDIA Nemotron on Nebius Token Factory is the pinned, inspectable ruler that the residual is measured against.

This folder holds everything needed to build Keeper: business requirements, methodology, data design and generation, architecture, API, frontend specifications, configuration, run instructions, deployment on Nebius for the competition, and the build plan. The two idea papers in this folder are the source of truth for the idea:

- [`perspective-intelligence-hackathon-idea-paper.docx`](perspective-intelligence-hackathon-idea-paper.docx): the central idea (residual, lens, Perspective Stack, Perspective Loop, Fidelity Test and Growth Test).
- [`perspective-intelligence-use-cases.docx`](perspective-intelligence-use-cases.docx): the use cases. Section 3 (Keeper) is the one built here.

The competition reference (rules, tracks, judging, platform facts) is in the workspace-level `docs/` folder (`../../../docs/` from here). Where these documents rely on it, they cite it as *Hackathon ref 0X*.

## Start here

| If you are… | Read, in this order |
|---|---|
| New to the project | [Solution overview](00-start-here/01-solution-overview.md) → [Glossary](00-start-here/02-glossary.md) → [Hackathon fit](00-start-here/04-hackathon-fit.md) |
| A product or business reader | [BRD](01-business/01-business-requirements.md) → [Personas and journeys](01-business/02-personas-and-journeys.md) → [Scope and release plan](01-business/05-scope-and-release-plan.md) |
| An AI agent about to build | [Rules for AI agents](10-build/04-rules-for-ai-agents.md) → [Implementation plan](10-build/02-implementation-plan.md) → [Repository structure](10-build/01-repository-structure.md) → the documents your milestone lists |
| Building the data | [Data index](03-data/README.md) → [Synthetic world scenario](03-data/05-synthetic-world-scenario.md) → [Synthetic data generation](03-data/06-synthetic-data-generation.md) |
| Building the frontend | [Frontend index](06-frontend/README.md) |
| Setting up a machine | [`./run.sh`](08-run/01-run-sh.md) → [The `.env` file](07-configuration/01-env-file.md) |
| Deploying for the competition | [Nebius architecture](09-deployment/01-nebius-architecture.md) → [Deployment steps](09-deployment/02-nebius-deployment-steps.md) → [Judging operations](09-deployment/03-judging-operations.md) → [Submission](09-deployment/04-hackathon-submission.md) |

## Contents

### 00 · Start here
- [Solution overview](00-start-here/01-solution-overview.md): what Keeper is, the loop, what v1 contains, the principles
- [Glossary](00-start-here/02-glossary.md): one name per concept, used the same way in code, API, database and UI
- [Idea-to-feature traceability](00-start-here/03-idea-to-feature-traceability.md): every claim in the papers mapped to a requirement, module and test
- [Hackathon fit](00-start-here/04-hackathon-fit.md): compliance, track, and how each judging criterion is earned

### 01 · Business
- [Business requirements document (BRD)](01-business/01-business-requirements.md)
- [Personas and user journeys](01-business/02-personas-and-journeys.md)
- [Functional requirements (FRD)](01-business/03-functional-requirements.md)
- [Non-functional requirements](01-business/04-non-functional-requirements.md)
- [Scope and release plan](01-business/05-scope-and-release-plan.md)

### 02 · Methodology (how Keeper thinks)
- [Overview and pipeline](02-methodology/README.md)
- [Situations and findings](02-methodology/01-situations-and-findings.md)
- [What the maintainer noticed (H)](02-methodology/02-human-findings.md)
- [The baseline, or ruler (C)](02-methodology/03-baseline-the-ruler.md)
- [Matching and the residual (R)](02-methodology/04-matching-and-residual.md)
- [The lens: representation and building](02-methodology/05-lens-representation-and-building.md)
- [Applying the lens](02-methodology/06-applying-the-lens.md)
- [Routing (four cases) and triage](02-methodology/07-routing-and-triage.md)
- [The fix loop](02-methodology/08-fix-loop.md)
- [Outcomes, calibration and bias](02-methodology/09-outcomes-calibration-bias.md)
- [Find: where the maintainer's eye matters most](02-methodology/10-find-edge-map.md)
- [The Perspective Fidelity Test](02-methodology/11-fidelity-test.md)
- [The Growth Test and health states](02-methodology/12-growth-test-and-health.md)
- [Lens versions, ownership and governance](02-methodology/13-lens-versions-and-governance.md)
- [Guardrails and safety](02-methodology/14-guardrails-and-safety.md)
- [LLM prompt catalog](02-methodology/15-prompt-catalog.md)

### 03 · Data
- [Index](03-data/README.md)
- [Data inventory](03-data/01-data-inventory.md)
- [Source schema: GitHub REST API](03-data/02-source-schema-github.md)
- [Source schema: git, CI and repository files](03-data/03-source-schema-git-ci-files.md)
- [External data: real repositories, CodeReviewer, OSV](03-data/04-external-data.md)
- [Synthetic world scenario](03-data/05-synthetic-world-scenario.md)
- [Synthetic data generation](03-data/06-synthetic-data-generation.md)
- [Ground truth and validation](03-data/07-ground-truth-and-validation.md)
- [The `data/` folder and git](03-data/08-data-folder-and-git.md)
- [Internal data model (database)](03-data/09-internal-data-model.md)

### 04 · Architecture
- [System architecture](04-architecture/01-system-architecture.md)
- [Backend modules](04-architecture/02-backend-modules.md)
- [LLM gateway](04-architecture/03-llm-gateway.md)
- [Jobs and streaming](04-architecture/04-jobs-and-streaming.md)
- [Sandbox runners](04-architecture/05-sandbox-runners.md)
- [The assistant (Ask)](04-architecture/06-assistant.md)
- [Security and privacy](04-architecture/07-security-and-privacy.md)

### 05 · API
- [Conventions](05-api/01-conventions.md)
- [Endpoints](05-api/02-endpoints.md)
- [Streaming events](05-api/03-streaming-events.md)
- [Frontend integration](05-api/04-frontend-integration.md)

### 06 · Frontend
- [Index](06-frontend/README.md)
- [UX principles and information architecture](06-frontend/01-ux-principles-and-ia.md)
- [Design system](06-frontend/02-design-system.md)
- [Responsive layout](06-frontend/03-responsive-layout.md)
- [App shell, navigation and the guided tour](06-frontend/04-app-shell-and-tour.md)
- Screens: [Queue](06-frontend/screens/01-queue.md) · [Pull request](06-frontend/screens/02-pull-request.md) · [Ask](06-frontend/screens/03-ask.md) · [Lens](06-frontend/screens/04-lens.md) · [Proof](06-frontend/screens/05-proof.md) · [Practice](06-frontend/screens/06-practice.md) · [Settings](06-frontend/screens/07-settings.md) · [First run, empty and error states](06-frontend/screens/08-first-run-and-states.md)
- [Component catalog](06-frontend/05-component-catalog.md)
- [Copy guide](06-frontend/06-copy-guide.md)
- [Accessibility](06-frontend/07-accessibility.md)

### 07 · Configuration
- [The `.env` file](07-configuration/01-env-file.md)
- [`.gitignore` and secrets](07-configuration/02-gitignore-and-secrets.md)
- [Config files](07-configuration/03-config-files.md)

### 08 · Run
- [`./run.sh`](08-run/01-run-sh.md)
- [Local development](08-run/02-local-development.md)
- [Troubleshooting](08-run/03-troubleshooting.md)

### 09 · Deployment (competition)
- [Nebius architecture](09-deployment/01-nebius-architecture.md)
- [Deployment steps](09-deployment/02-nebius-deployment-steps.md)
- [Judging operations (Oct 30 – Dec 15)](09-deployment/03-judging-operations.md)
- [Hackathon submission](09-deployment/04-hackathon-submission.md)
- [Beyond the hackathon](09-deployment/05-beyond-the-hackathon.md)

### 10 · Build
- [Repository structure](10-build/01-repository-structure.md)
- [Implementation plan](10-build/02-implementation-plan.md)
- [Testing strategy](10-build/03-testing-strategy.md)
- [Rules for AI agents](10-build/04-rules-for-ai-agents.md)
- [Definition of done](10-build/05-definition-of-done.md)

## Conventions used in these documents

- **MUST, SHOULD, MAY** carry their RFC 2119 meanings. Requirement IDs (`BR-…`, `FR-…`, `NFR-…`) are stable; code, tests and commits cite them.
- **Example values** such as the demo project name `strata` or the maintainer login `mira-k` illustrate shapes only. The real values are produced by data generation and read from `data/`. The code MUST NOT contain them (a test enforces this; see [Testing strategy](10-build/03-testing-strategy.md) §6).
- **`[verify]`** marks an external fact (an API parameter, CLI flag or model ID) that was correct when written but may change. The build checks it at runtime (`./run.sh --check`) instead of assuming it.
- Paths are relative to the repository root unless a link says otherwise.

## Facts this documentation relies on (checked 25 October 2026)

| Fact | Value | Where it is used |
|---|---|---|
| Token Factory base URL | `https://api.tokenfactory.nebius.com/v1/` (OpenAI-compatible) | [LLM gateway](04-architecture/03-llm-gateway.md) |
| Nemotron model IDs | `nvidia/Nemotron-3_5-Lightning`, `nvidia/nemotron-3-super-120b-a12b`, `nvidia/Nemotron-3-Ultra-550b-a55b` | [`config/models.yaml`](07-configuration/03-config-files.md) |
| Prices per 1M tokens (in / out) | Lightning $0.06 / $0.24 · Super $0.30 / $0.90 · Ultra $1.00 / $3.00 | [`config/pricing.yaml`](07-configuration/03-config-files.md) |
| GitHub REST API version header | `X-GitHub-Api-Version: 2022-11-28` | [GitHub schema](03-data/02-source-schema-github.md) |
| GitHub authenticated rate limit | 5,000 requests per hour per token | [Importer](03-data/04-external-data.md) |
| Hackathon deadline | Fri 30 Oct 2026, 10:00 PT (22:30 IST); judging until 15 Dec 2026 | [Implementation plan](10-build/02-implementation-plan.md), [Judging operations](09-deployment/03-judging-operations.md) |

Model IDs were removed from Token Factory without rerouting in June and August 2026. Keeper therefore reads every model ID from configuration, probes them at start-up, and falls back along a configured chain (see [LLM gateway](04-architecture/03-llm-gateway.md) §4).
