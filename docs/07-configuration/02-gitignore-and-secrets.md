# `.gitignore` and secrets

**Goal:** no secret ever reaches git, while the generated data (`data/`) **is** committed so that anyone who clones the repository gets the full demo.

## 1. `.gitignore` (complete, repository root)

```gitignore
# ---- Secrets (never commit) --------------------------------------------------
.env
.env.*
!.env.example
*.pem
*.key
*-credentials.json
credentials.json
service-account*.json
.nebius/
.secrets/
infra/nebius/.state/

# ---- Runtime state (database, caches, unpacked repos, sandboxes, logs) -------
.runtime/
data/private/

# ---- Python -----------------------------------------------------------------
__pycache__/
*.py[cod]
.venv/
backend/.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.hypothesis/
.coverage
.coverage.*
htmlcov/
*.egg-info/
backend/build/
backend/dist/

# ---- Node / frontend --------------------------------------------------------
node_modules/
frontend/dist/
frontend/.vite/
frontend/coverage/
frontend/playwright-report/
frontend/test-results/
frontend/blob-report/

# ---- Logs and temp ----------------------------------------------------------
*.log
*.tmp

# ---- OS and editors ---------------------------------------------------------
.DS_Store
Thumbs.db
.idea/
.vscode/*
!.vscode/extensions.json
*.swp

# ---- Local agent settings of the people building this repo -----------------
.claude/settings.local.json
CLAUDE.local.md
```

What is **committed** on purpose: `.env.example`, `config/` (no secrets), `data/` (all of it except `data/private/`, a scratch folder that should normally not exist), `frontend/src/api/openapi.json` and `schema.d.ts` (generated, checked in CI), lockfiles, and `infra/` scripts (with placeholders only).

## 2. Where each kind of file lives

| Kind | Path | In git? |
|---|---|---|
| Secrets | `.env` | **no** |
| Template | `.env.example` | yes |
| Database, caches, cloned repositories, sandboxes, wheels, logs | `.runtime/` | no |
| Generated dataset (mirror, bundle, scenario, ground truth, snapshot, manifest) | `data/` | **yes** ([data folder and git](../03-data/08-data-folder-and-git.md)) |
| Datagen ledger, intermediate files and cached LLM responses | `.runtime/datagen/` | no |
| Data about real imported people | `.runtime/projects/<id>/` | no (never committed) |

## 3. Guarding against mistakes

1. **Pre-commit hooks** (`.pre-commit-config.yaml`, installed by `./run.sh --dev`): `gitleaks protect --staged`, `detect-private-key`, `check-added-large-files --maxkb=5000` (with `data/` bundle files allowed via the hook's exclude), plus `ruff` and `prettier`.
2. **CI** (`.github/workflows/ci.yml`): `gitleaks detect` over the full history; fail on any finding.
3. **Data scans:** the data generator's validation step V8 scans `data/` for secret-shaped strings and real e-mail domains before writing the manifest. `./run.sh --check` re-runs it.
4. **Runtime:** log redaction and `SecretStr` (see [Security and privacy](../04-architecture/07-security-and-privacy.md) §2).
5. **Tests:** `test_no_secrets_in_repo` runs the redaction patterns over all tracked files (from `git ls-files`), except `.env.example`, which must have empty values for every secret variable.

## 4. If a secret was committed

1. Revoke the key immediately (Token Factory → API keys; GitHub → tokens).
2. Remove it from history (`git filter-repo --replace-text`), force-push, and tell collaborators to re-clone.
3. Create a new key and put it in `.env` only.
