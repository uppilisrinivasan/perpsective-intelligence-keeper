# Security and privacy

## 1. Threat model (summary)

| Asset | Threat | Control |
|---|---|---|
| API keys (Nebius, GitHub, Tavily) | Leak to git, logs, the browser, a sandbox or a prompt | Keys only in `.env` or the environment (Mysterybox in the cloud); `.gitignore` plus a gitleaks pre-commit hook and CI; logs filter `*_KEY`, `*_TOKEN` and `*SECRET*` values; the API returns `configured: bool` only; sandbox environment from an allow-list; prompts are redacted |
| The host machine | Untrusted PR or model code run by tests | Sandbox only (05-sandbox-runners); recipes from config; network off; resource limits; no shell from model output |
| Lens data (a person's judgment) | Misuse, use without consent, evaluation of people | Consent gate; owner-only edit; pause and revoke; no person scoring outside the person's own Growth view; export by the owner only |
| The public demo | Abuse, cost drain | Access codes; per-session and global rate limits; spend caps; import disabled; confirmations |
| Model behaviour | Prompt injection from PR text | Data fencing; schema-only outputs; citation verification; actions only after user confirmation; the lens can only raise attention |
| GitHub | Accidental writes | A client exposing only GET; no write scopes required; a test enforces it |

## 2. Secrets handling

- `.env` is loaded at startup by `keeper.config` (pydantic-settings, `env_file=".env"`). It is never re-exported to child processes except through explicit allow-lists.
- `./run.sh` creates `.env` from `.env.example` if it is missing, sets mode `600`, and never prints values.
- `SecretStr` types are used for all secrets, so `repr` and logging never print them.
- Logging uses a redaction filter for the same patterns as `config/redaction.yaml`, plus the literal values of configured secrets.
- The frontend has **no** secrets. All provider calls are server-side.
- See [.gitignore and secrets](../07-configuration/02-gitignore-and-secrets.md) for the full ignore list and the pre-commit setup.

## 3. Web security

| Control | Local | Cloud |
|---|---|---|
| Bind | `127.0.0.1` | `0.0.0.0` inside the container |
| Auth | none | Access code → signed session cookie (`itsdangerous`, `KEEPER_SESSION_SECRET`), `HttpOnly`, `Secure`, `SameSite=Lax`, 12 h |
| CSRF | n/a (same origin) | State-changing requests require the `X-Keeper-CSRF` header matching a cookie (double submit) |
| CORS | Only the dev origin in `--dev` | Disabled (same origin) |
| Headers | CSP `default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; connect-src 'self'`; `X-Content-Type-Options: nosniff`; `Referrer-Policy: same-origin`; `frame-ancestors 'none'` | same, plus HSTS |
| Rate limits | off | `API_RATE_LIMIT_PER_MINUTE` per session and per IP; stricter for action endpoints |
| Markdown | `rehype-sanitize`; links get `rel="noopener noreferrer"`; no raw HTML | same |
| Uploads | Lens package import only: ≤ 5 MB, JSON Schema validated, no code execution | same |

## 4. Privacy

- **Demo data** is synthetic, uses reserved domains and personas, and is checked against a denylist (V8).
- **Imported data** is public GitHub data. The user-facing note says Keeper stores it locally and only sends excerpts to the configured model provider. A per-project **Delete project data** action removes the rows and the repository clone.
- **Lens consent:** building a lens for a real imported person requires `consent` = `self` (that person is the user) or `recorded` (the user attests the person agreed). Otherwise Keeper shows only aggregated project-level patterns and does not build a personal lens (FR-GOV).
- **Data retention:** `.runtime/` can be removed at any time with `./run.sh --reset`. Nothing personal goes to analytics; there is no telemetry.

## 5. Supply chain

- Python dependencies are pinned in `backend/uv.lock` (uv) and npm dependencies in `frontend/package-lock.json`. Run `pip-audit` and `npm audit --omit=dev` in CI (warnings only, with documented exceptions).
- The container uses a pinned base image digest and runs as a non-root user.
- `bandit` runs on Keeper itself in CI.
