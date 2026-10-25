# Non-functional requirements

| ID | Area | Requirement | How verified |
|---|---|---|---|
| **Safety** ||||
| NFR-SAFE-1 | No write actions on GitHub | The GitHub client exposes only `GET` methods. No code path posts, merges, closes or labels. | `test_no_github_write_calls`; import-linter contract |
| NFR-SAFE-2 | Attention never lowered | A risk-signal PR can never reach `shared` through any path (routing, override, assistant). | `test_risk_signal_never_shared` (property test) |
| NFR-SAFE-3 | Sandboxed execution | Tests and fixes run only inside a sandbox runner. The local runner uses a temp copy, a separate virtual environment, a timeout, CPU and memory limits where the OS supports them, no inherited secrets, and network disabled where possible. | `test_sandbox_env_has_no_secrets`, `test_timeout_kills` |
| NFR-SAFE-4 | Untrusted PR content | PR text, diffs and comments are untrusted. They are passed only inside delimited data blocks, never as instructions; tool calls never come from PR content. | Prompt-injection fixtures in `tests/security/` |
| **Privacy** ||||
| NFR-PRIV-1 | Minimum data to models | Only what a prompt needs is sent (diff hunks, findings, item texts). Secrets and e-mail addresses are redacted before sending. | `test_no_secret_shapes_in_prompts` |
| NFR-PRIV-2 | Local by default | Locally, all data stays in `.runtime/` and `data/`. Nothing goes to third parties other than Token Factory, plus GitHub, OSV and Tavily when those features are used. | Network allow-list in the gateway and HTTP clients |
| NFR-PRIV-3 | Zero retention | The deployment documentation requires enabling Token Factory zero data retention for the organisation. | Deployment checklist |
| NFR-PRIV-4 | Learner privacy | Practice results are visible only to the learner role (and in the demo, to the judge acting as learner). | API authorisation test |
| **Ethics** ||||
| NFR-ETH-1 | No flattery | Practice feedback states misses plainly. The assistant does not praise without evidence. | Copy review; prompt rules |
| NFR-ETH-2 | Bias visible to the owner | Bias-suspected items are always shown to the lens owner, never silently removed. | UI test |
| NFR-ETH-3 | Not an evaluation tool | Practice is not exposed to project leads; there is no ranking of learners. | No API exists for cross-learner listing |
| NFR-ETH-4 | Honest demo | Synthetic data is labelled "Demo project (fictional)" everywhere it appears. | UI test |
| **Performance** (local, Apple M-series or 4-vCPU Linux) ||||
| NFR-PERF-1 | Startup | `./run.sh` after the first run reaches a served UI in ≤ 10 s. The first run (installs plus build) takes ≤ 5 min on a normal connection. | Manual, CI timing |
| NFR-PERF-2 | UI responsiveness | Route transitions ≤ 200 ms with cached data; queue render of 100 PRs ≤ 100 ms; the PR diff virtualises above 2,000 lines. | Playwright performance marks |
| NFR-PERF-3 | API latency | Non-LLM endpoints p95 ≤ 150 ms on the demo data. | pytest benchmark |
| NFR-PERF-4 | Analysis latency | Analysis of one typical PR (≤ 400 changed lines) takes ≤ 60 s live; first streamed event ≤ 2 s. | Timed E2E with a live key (manual) |
| NFR-PERF-5 | Fix loop | Demo test suite ≤ 15 s per run; a typical fix completes in ≤ 3 min. | Datagen validation asserts the suite duration |
| **Cost** ||||
| NFR-COST-1 | Caps | Spend caps (`KEEPER_SPEND_CAP_USD` per `KEEPER_SPEND_CAP_PERIOD`) and a daily token limit are enforced before every call. | `test_spend_cap_blocks` |
| NFR-COST-2 | Caching | Identical requests (same prompt hash, inputs and model) are served from the cache unless `LLM_CACHE=off`. | `test_cache_hit` |
| NFR-COST-3 | Budget targets | Full demo analysis (12 queue PRs) ≤ $0.50; a Proof run over 40 held-out PRs ≤ $1.50; full data generation ≤ $15. | Usage report after each run |
| **Reliability** ||||
| NFR-REL-1 | Model fallback | A failing or removed model falls back along the chain; the UI notes "Used Super (Ultra unavailable)". | Gateway tests with the fake provider |
| NFR-REL-2 | Retries | 429 and 5xx responses are retried with exponential backoff and jitter, honouring `Retry-After`; 402 stops with "Credits exhausted". | Gateway tests |
| NFR-REL-3 | Structured output | Invalid JSON is repaired once (re-ask with the validation error); then the step fails cleanly. | Gateway tests |
| NFR-REL-4 | Crash safety | Jobs persist state per step; a restart does not corrupt the database. | Kill-and-restart test |
| NFR-REL-5 | No-key mode | With no key, every screen works on saved results, and live actions are disabled with an explanation. | E2E `no_key.spec.ts` |
| **Usability and responsiveness** ||||
| NFR-UX-1 | Self-explanatory | A first-time user completes J1 (the tour) without help. Every screen has a one-line purpose statement. | Hallway test with 3 people; copy review |
| NFR-UX-2 | Time to aha | ≤ 1 click from landing to the aha (the tour's first step). | E2E |
| NFR-RESP-1 | Fluid layout | No fixed pixel widths for layout containers. Widths use `rem`, `%`, `fr`, `min()`, `max()` and `clamp()`, with container queries. | Lint rule (stylelint) and review |
| NFR-RESP-2 | Viewports | Fully usable at 1280×720, 1366×768, 1440×900, 1536×864, 1920×1080, 2560×1440 and 3440×1440. Usable (read and act) at 1024×768 and 768×1024, and read-only friendly at 390×844. Browser zoom 50–200% works without horizontal page scroll (except the diff's own scroller). | Playwright viewport matrix with screenshots |
| **Accessibility** ||||
| NFR-A11Y-1 | WCAG 2.2 AA | Contrast, keyboard operation, focus visibility, ARIA for custom widgets, reduced motion. | axe-core in E2E; manual keyboard pass |
| **Security** ||||
| NFR-SEC-1 | Secrets | Secrets only in `.env` or the environment; never logged or returned by the API; `.env` is git-ignored. | Secret scan (gitleaks) in `./run.sh --check` and CI |
| NFR-SEC-2 | Cloud access | In cloud mode: an access-code sign-in, an HttpOnly, Secure, SameSite=Lax cookie, CSRF protection for state-changing requests, and a rate limit per session and per IP. | API tests |
| NFR-SEC-3 | Dependency hygiene | Lockfiles committed; `pip-audit` and `npm audit --omit=dev` run in `--check`. | `--check` |
| **Portability** ||||
| NFR-PORT-1 | OS | macOS 13+ and Linux (Ubuntu 22.04+). Windows via WSL2. | CI matrix (Linux), manual (macOS) |
| NFR-PORT-2 | Prerequisites | Python ≥ 3.11, Node ≥ 20.19, git ≥ 2.34. Docker is optional. | `./run.sh` checks |
| **Observability** ||||
| NFR-OBS-1 | Logs | Structured JSON logs to `.runtime/logs/keeper.log` (rotated), human-readable to the console. | Manual |
| NFR-OBS-2 | LLM audit | Every call stored in `llm_calls` with role, model, prompt ID and version, tokens, cost, latency, cache hit, fallback used and job ID. | Settings → Usage |
| NFR-OBS-3 | Health | `GET /api/v1/health` (liveness) and `GET /api/v1/status` (readiness, with model probes). | API tests |
| **Maintainability** ||||
| NFR-MAINT-1 | Nothing hardcoded | Model IDs, URLs, thresholds, prompts, copy, colours and demo values live in env, config, data or the copy file. | Hardcode-guard test; lint |
| NFR-MAINT-2 | Types | Python type-checked (mypy strict on `keeper/`); TypeScript `strict: true`; API types generated from OpenAPI. | CI |
| NFR-MAINT-3 | Tests offline | The full test suite runs offline with the `fake` provider and fixtures. | CI |
