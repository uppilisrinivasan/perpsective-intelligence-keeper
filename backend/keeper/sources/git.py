"""The git CLI via subprocess, with fixed argument lists and no shell (docs/04-architecture/02 contracts)."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitError(RuntimeError):
    pass


def _env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "USER")}
    env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1", "LC_ALL": "C"})
    if extra:
        env.update(extra)
    return env


def git(repo: Path | str, *args: str, env: dict[str, str] | None = None, check: bool = True,
        input_text: str | None = None) -> str:
    cmd = ["git", "-C", str(repo), "-c", "core.autocrlf=false", "-c", "core.quotepath=off", *args]
    r = subprocess.run(cmd, capture_output=True, text=True, env=_env(env), input=input_text)
    if check and r.returncode != 0:
        raise GitError(f"git {' '.join(args[:3])}: {r.stderr.strip()[:400]}")
    return r.stdout


def git_ok(repo: Path | str, *args: str, env: dict[str, str] | None = None) -> bool:
    cmd = ["git", "-C", str(repo), *args]
    return subprocess.run(cmd, capture_output=True, text=True, env=_env(env)).returncode == 0


def available() -> bool:
    return shutil.which("git") is not None


def version() -> str:
    return subprocess.run(["git", "version"], capture_output=True, text=True).stdout.strip()


@dataclass
class Identity:
    name: str
    email: str
    date: str  # ISO 8601

    def env(self, prefix: str) -> dict[str, str]:
        return {f"GIT_{prefix}_NAME": self.name, f"GIT_{prefix}_EMAIL": self.email, f"GIT_{prefix}_DATE": self.date}


def commit_env(author: Identity, committer: Identity | None = None) -> dict[str, str]:
    c = committer or author
    return {**author.env("AUTHOR"), **c.env("COMMITTER")}


def init(repo: Path, branch: str = "main") -> None:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", branch, str(repo)], check=True, capture_output=True, env=_env())
    git(repo, "config", "user.name", "keeper-datagen")
    git(repo, "config", "user.email", "datagen@localhost")
    git(repo, "config", "commit.gpgsign", "false")


def head(repo: Path | str, ref: str = "HEAD") -> str:
    return git(repo, "rev-parse", ref).strip()


def clone_bundle(bundle: Path, dest: Path) -> None:
    bundle, dest = Path(bundle).resolve(), Path(dest).resolve()
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["git", "clone", "-q", "--no-checkout", str(bundle), str(dest)], capture_output=True,
                       text=True, env=_env())
    if r.returncode != 0:
        raise GitError(f"git clone bundle: {r.stderr.strip()[:400]}")
    # bring every ref from the bundle (refs/pull/*/head included)
    git(dest, "fetch", "-q", str(bundle), "+refs/*:refs/remotes/bundle/*")
    for line in git(dest, "for-each-ref", "--format=%(refname)", "refs/remotes/bundle/").splitlines():
        local = line.replace("refs/remotes/bundle/", "refs/", 1)
        if local.startswith("refs/heads/") or local.startswith("refs/pull/"):
            git(dest, "update-ref", local, line)
    git(dest, "checkout", "-q", "-f", "main")


def show(repo: Path | str, sha: str, path: str) -> str | None:
    r = subprocess.run(["git", "-C", str(repo), "show", f"{sha}:{path}"], capture_output=True, env=_env())
    if r.returncode != 0:
        return None
    try:
        return r.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return None


def ls_tree(repo: Path | str, sha: str) -> list[str]:
    return [ln for ln in git(repo, "ls-tree", "-r", "--name-only", sha).splitlines() if ln]


def worktree_add(repo: Path | str, dest: Path, sha: str) -> None:
    git(repo, "worktree", "add", "-q", "--detach", "-f", str(dest), sha)


def worktree_remove(repo: Path | str, dest: Path) -> None:
    git(repo, "worktree", "remove", "-f", str(dest), check=False)
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)


def worktree_prune(repo: Path | str) -> None:
    git(repo, "worktree", "prune", check=False)


def diff_files(repo: Path | str, base: str, head_sha: str) -> list[dict[str, object]]:
    """The PR's files as GitHub reports them: status, additions, deletions, previous name, per-file patch."""
    out = git(repo, "diff", "--no-color", "-M", "--numstat", "-z", f"{base}...{head_sha}")
    stat: dict[str, tuple[int | None, int | None, str | None]] = {}
    parts = out.split("\0")
    i = 0
    while i < len(parts) and parts[i]:
        a, d, path = parts[i].split("\t", 2)
        prev = None
        if path == "":
            prev, path = parts[i + 1], parts[i + 2]
            i += 3
        else:
            i += 1
        stat[path] = (None if a == "-" else int(a), None if d == "-" else int(d), prev)
    names = git(repo, "diff", "--no-color", "-M", "--name-status", "-z", f"{base}...{head_sha}").split("\0")
    status: dict[str, str] = {}
    j = 0
    while j < len(names) and names[j]:
        code = names[j]
        if code[0] in "RC":
            status[names[j + 2]] = {"R": "renamed", "C": "copied"}[code[0]]
            j += 3
        else:
            status[names[j + 1]] = {"A": "added", "D": "removed", "M": "modified", "T": "changed"}.get(code[0],
                                                                                                    "modified")
            j += 2
    patches = _split_patches(git(repo, "diff", "--no-color", "-M", "--unified=3", f"{base}...{head_sha}"))
    files = []
    for path, (a, d, prev) in stat.items():
        binary = a is None
        patch = None if binary else patches.get(path)
        files.append({"filename": path, "status": status.get(path, "modified"), "additions": a or 0,
                      "deletions": d or 0, "changes": (a or 0) + (d or 0), "patch": patch, "previous_filename": prev,
                      "binary": binary})
    return files


def _split_patches(raw: str) -> dict[str, str | None]:
    """Split one `git diff` output into per-file patches (from the first @@), keyed by the new path."""
    out: dict[str, str | None] = {}
    for block in raw.split("\ndiff --git ")[0:]:
        block = block[len("diff --git "):] if block.startswith("diff --git ") else block
        if not block.strip():
            continue
        header = block.split("\n", 1)[0]
        path = None
        for ln in block.split("\n")[:8]:
            if ln.startswith("+++ b/"):
                path = ln[6:]
            elif ln.startswith("rename to "):
                path = ln[len("rename to "):]
        if path is None and " b/" in header:
            path = header.rsplit(" b/", 1)[1]
        if path:
            out[path] = _strip_header(block)
    return out


def _strip_header(raw: str) -> str | None:
    lines = raw.split("\n")
    for i, ln in enumerate(lines):
        if ln.startswith("@@"):
            body = "\n".join(lines[i:])
            return body[:-1] if body.endswith("\n") else body
    return None


def blob_sha(repo: Path | str, sha: str, path: str) -> str | None:
    r = subprocess.run(["git", "-C", str(repo), "rev-parse", f"{sha}:{path}"], capture_output=True, text=True,
                       env=_env())
    return r.stdout.strip() if r.returncode == 0 else None


def blame_lines(repo: Path | str, sha: str, path: str) -> list[str]:
    """Commit SHA per line of path at sha (porcelain blame)."""
    out = git(repo, "blame", "--porcelain", sha, "--", path, check=False)
    shas: list[str] = []
    for ln in out.splitlines():
        if ln and len(ln.split(" ")[0]) == 40 and not ln.startswith("\t"):
            parts = ln.split(" ")
            if len(parts) >= 3:
                shas.append(parts[0])
    return shas


def rev_list(repo: Path | str, *args: str) -> list[str]:
    return [s for s in git(repo, "rev-list", *args).split() if s]


def export_tree(repo: Path | str, sha: str, dest: Path) -> None:
    """Write the tree at sha into dest (read-only on the repository, safe to run in parallel)."""
    import io
    import tarfile

    r = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", sha], capture_output=True, env=_env())
    if r.returncode != 0:
        raise GitError(f"git archive: {r.stderr.decode(errors='replace')[:300]}")
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tar:
        tar.extractall(dest, filter="data")


def read_many(repo: Path | str, sha: str, paths: list[str]) -> dict[str, str | None]:
    """Read many files at sha in one `git cat-file --batch` process."""
    if not paths:
        return {}
    req = "".join(f"{sha}:{p}\n" for p in paths)
    r = subprocess.run(["git", "-C", str(repo), "cat-file", "--batch"], input=req.encode(), capture_output=True,
                       env=_env())
    out: dict[str, str | None] = {}
    buf = r.stdout
    pos = 0
    for p in paths:
        nl = buf.index(b"\n", pos)
        header = buf[pos:nl].decode()
        pos = nl + 1
        if header.endswith("missing") or header.endswith("ambiguous"):
            out[p] = None
            continue
        size = int(header.split()[2])
        blob = buf[pos:pos + size]
        pos += size + 1
        try:
            out[p] = blob.decode("utf-8")
        except UnicodeDecodeError:
            out[p] = None
    return out
