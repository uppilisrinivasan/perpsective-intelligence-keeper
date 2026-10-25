# Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `./run.sh: Permission denied` | The execute bit was lost | `chmod +x run.sh` (the repo stores it as executable; check `git config core.fileMode`) |
| "Python 3.11+ not found" | Old system Python | macOS: `brew install python@3.12`; Ubuntu: `sudo apt install python3.12 python3.12-venv` |
| "Node 20.19+ not found" | Old Node | Install via `nvm install 22` or Homebrew |
| "Port 8430 is in use" | Another process | `./run.sh --port 8431`, or stop the process shown |
| The UI says "Saved results" although a key is set | The key is in the wrong file, has a typo, or the server wasn't restarted | The key belongs in `.env` at the root; restart; `./run.sh --check` shows the probe result |
| "Model … not found" in Settings | Token Factory changed or removed a model ID | Update `KEEPER_MODEL_*` in `.env` to a current ID from `GET /v1/models` (or Token Factory's model list); the fallback chain keeps Keeper working meanwhile |
| "json_schema rejected" in the probe | The model or endpoint does not support structured output | No action needed: the gateway uses `json_object` plus validation and repair |
| `402` errors from the provider | Credits exhausted | Add credits in Token Factory; Keeper shows "Spending limit reached at the provider" |
| "Keeper reached its spending limit" | `KEEPER_SPEND_CAP_USD` reached | Raise it in `.env` or wait for the period reset |
| Fix runs fail with "wheelhouse missing" | Step 9 of `run.sh` could not download (offline) | Run `./run.sh` once online |
| Fix runs say "Local sandbox: no network isolation" | No `unshare` or `sandbox-exec` | Install Docker and set `SANDBOX_PROVIDER=docker` |
| "Token Factory Sandboxes access not granted" | Sandboxes are in beta and need access per project | Request access in the Token Factory dashboard, or use `docker` or `local` |
| "Data manifest hash mismatch" | `data/` was modified, or Git LFS or line-ending conversion changed files | `git status data/`; `git checkout -- data/`; make sure `.gitattributes` (binary for bundles) is respected |
| The browser shows a blank page | The frontend wasn't built | `./run.sh` rebuilds; or `rm frontend/dist/.build-stamp && ./run.sh` |
| SSE progress never updates behind a proxy | The proxy buffers responses | Disable buffering for `/api/v1/jobs/*/events` (`X-Accel-Buffering: no` is sent) |
| Windows | Not supported natively | Use WSL2 (Ubuntu): install Python, Node and git inside WSL, clone inside the WSL filesystem, run `./run.sh`, open the printed URL in Windows |
| Import is slow | GitHub rate limits (60 per hour without a token) | Add `GITHUB_TOKEN` (5,000 per hour); the import job shows the wait |
| Everything is broken after experiments | Bad local state | `./run.sh --reset` (keeps `data/` and `.env`) |

For anything else: `./run.sh --check` and `.runtime/logs/keeper.log` (request IDs in the UI's error details match log lines).
