# Sandbox runners

Tests, static tools and fix attempts run untrusted code (PR code, model-written code). They run only through `keeper.sandbox`.

## 1. Interface

```python
class SandboxRunner(Protocol):
    name: str                                     # "local" | "docker" | "contree"
    async def available(self) -> Availability     # ok | unavailable(reason)
    async def prepare(self, project: Project, sha: str, recipe: Recipe) -> Workspace   # checkout + environment; returns a handle
    async def checkpoint(self, ws: Workspace) -> Checkpoint
    async def branch(self, cp: Checkpoint) -> Workspace          # a new workspace from a checkpoint
    async def write_files(self, ws: Workspace, changes: list[FileChange]) -> None
    async def read_file(self, ws: Workspace, path: str) -> str
    async def run(self, ws: Workspace, cmd: RecipeCommand, *, timeout: int, on_output: Callable[[str], None]) -> RunResult  # exit code, stdout/err tails, artefacts (junit.xml)
    async def dispose(self, ws: Workspace) -> None
```

`RecipeCommand` comes only from `config/sandbox.yaml`; models cannot supply commands.

## 2. Recipes (`config/sandbox.yaml`)

```yaml
default_provider: ${SANDBOX_PROVIDER:-local}
fallback_order: [contree, docker, local]       # used when the configured provider is unavailable
network: off
test_timeout_seconds: 120
recipes:
  python-pytest:
    detect: ["pyproject.toml", "setup.cfg", "setup.py"]
    image: "python:3.12-slim"                   # docker and contree base image
    setup:
      - ["python", "-m", "venv", ".venv"]
      - [".venv/bin/pip", "install", "--no-index", "--find-links", "/wheels", "-e", ".[test]"]
    test: [".venv/bin/python", "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", "--junitxml=.keeper/junit.xml"]
    test_targeted: [".venv/bin/python", "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", "--junitxml=.keeper/junit-targeted.xml", "{tests}"]
    lint: [".venv/bin/ruff", "check", "--output-format", "json", "{files}"]
    wheelhouse: ".runtime/wheels/python-pytest"  # prepared by ./run.sh (pip download) so the sandbox needs no network
```

The wheelhouse is built once by `./run.sh` from `backend/sandbox-requirements.txt` (pytest, ruff, and the demo repository's test extras). For imported repositories, their test extras are added to the wheelhouse during the import job (that step uses the network; the sandbox does not).

## 3. Providers

### 3.1 `local` (always available)
- Workspace: `git worktree add --detach .runtime/sandboxes/<id> <sha>` from the project's repository, plus the recipe setup. The virtual environment is cached per (project, recipe, lockfile hash) and copied in, using copy-on-write where the filesystem supports it.
- Checkpoint: `git stash create` plus a copy of untracked files, or a directory snapshot (`cp -a`, or `cp -c` clones on APFS).
- Isolation, best effort: a subprocess with `env` built from an allow-list, `cwd` in the workspace, `HOME` set to a temp directory, `resource.setrlimit` (CPU seconds, address space 2 GB, max open files) on Linux and macOS, process-group kill on timeout. Network: on Linux, `unshare -n` if available; on macOS, `sandbox-exec` with a deny-network profile (`config/sandbox/macos-deny-network.sb`); otherwise there is no network isolation, which the Settings screen states.
- The UI labels it: "Local sandbox: tests run on this machine with limited isolation."

### 3.2 `docker` (when `docker info` succeeds)
- `docker run --rm --network none --cpus 2 --memory 2g --pids-limit 256 --read-only --tmpfs /tmp -v <workspace>:/work -v <wheelhouse>:/wheels:ro -w /work <image> <cmd>`.
- Workspaces and checkpoints are as in `local`, on the host. The container does only execution.

### 3.3 `contree` (Token Factory Sandboxes, beta)
- Requires Sandboxes access granted for the Token Factory project, plus `CONTREE_*` settings [verify names and SDK in the Token Factory Sandboxes docs; access is requested per project from the dashboard].
- Mapping of operations: `prepare` = build or reuse an **image** from the recipe's base image plus the repository at the SHA and the wheelhouse (a Dockerfile-style build with layer caching); `run` = an **operation** on that image (fresh compute, returns stdout, stderr and exit code); `checkpoint` = a non-disposable run that saves a new image; `branch` = start runs from the same image in parallel, which is the documented "try two fixes and keep the passing branch" pattern.
- Files are written by an operation that applies a tar of the changes. Artefacts (JUnit XML) are read by an operation that prints them base64-encoded.
- Credentials are never placed in the sandbox environment (the docs warn that `env` is visible inside).
- If access is missing (HTTP 403 or "not ready"), `available()` returns `unavailable("Token Factory Sandboxes access not granted for this project")`, and the fallback order applies. Settings and the README state this.

## 4. Selection

`keeper.sandbox.select(settings) -> SandboxRunner`: try `SANDBOX_PROVIDER`; if it is unavailable, walk `fallback_order`. The result and the reason are in `GET /api/v1/status` and on every fix run (`provider` field). A fix run never switches provider midway.

## 5. Cleanup

Workspaces are disposed at the end of each fix run (kept for 1 hour if `KEEPER_KEEP_SANDBOXES=true`, for debugging). A janitor on startup removes `.runtime/sandboxes/*` older than 24 hours and prunes git worktrees.
