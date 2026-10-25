"""G2, G4, G5: build the real repository and execute the plan in time order (docs/03-data/06 §5).

Code renders each PR's change from the plan's toggles (codegen), git commits it with the planned author and dates,
review comments are anchored by code on the real diff (diff_hunk, line, position, outdated), and the wording comes
from the world's phrase banks. Everything is recorded in a ledger that G7/G8 turn into the GitHub mirror.
"""

from __future__ import annotations

import copy
import gzip
import hashlib
import json
import re
import shutil
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from keeper.core.timeutil import iso, parse_ts
from keeper.datagen.codegen import Feature, Rendered, render
from keeper.datagen.plan import CODE_TOGGLES
from keeper.datagen.texts import Texts, choose, human
from keeper.datagen.world import World
from keeper.sources import git as G

IMPORT_NAMES = {"pyyaml": "yaml", "tomli": "tomli", "regex": "regex", "platformdirs": "platformdirs",
                "python-dotenv": "dotenv"}
VOICE = {"maintainer": "maintainer", "security_reviewer": "security_reviewer", "occasional": "occasional"}


class IdGen:
    def __init__(self, seed: int):
        self.counters = {"user": 0, "pr": 1_400_000_000, "review": 1_900_000_000, "comment": 1_700_000_000,
                         "icomment": 2_100_000_000, "issue": 1_300_000_000, "event": 9_000_000_000,
                         "check": 21_000_000_000, "label": 4_000_000_000}
        self.seed = seed

    def next(self, kind: str) -> int:
        step = 1 + (hashlib.sha256(f"{self.seed}{kind}{self.counters[kind]}".encode()).digest()[0] % 37)
        self.counters[kind] += step
        return self.counters[kind]


def node_id(prefix: str, n: int) -> str:
    import base64
    raw = hashlib.sha256(f"{prefix}{n}".encode()).digest()[:9]
    return f"{prefix}_kwDO" + base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _hunks(patch: str | None) -> list[dict[str, Any]]:
    """Parse a per-file patch into hunks with new-side line mapping and GitHub positions."""
    if not patch:
        return []
    hunks: list[dict[str, Any]] = []
    pos = 0
    cur = None
    for ln in patch.split("\n"):
        if ln.startswith("@@"):
            m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", ln)
            if not m:
                continue
            if cur is not None:
                pos += 1  # later hunk headers count as positions
            cur = {"header": ln, "old": int(m.group(1)), "new": int(m.group(3)), "lines": [], "start_pos": pos}
            hunks.append(cur)
            o, nn = cur["old"], cur["new"]
            continue
        if cur is None:
            continue
        pos += 1
        kind = ln[:1] if ln else " "
        if kind == "+":
            cur["lines"].append({"kind": "+", "new": nn, "old": None, "pos": pos, "text": ln})
            nn += 1
        elif kind == "-":
            cur["lines"].append({"kind": "-", "new": None, "old": o, "pos": pos, "text": ln})
            o += 1
        elif kind == "\\":
            cur["lines"].append({"kind": "\\", "new": None, "old": None, "pos": pos, "text": ln})
        else:
            cur["lines"].append({"kind": " ", "new": nn, "old": o, "pos": pos, "text": ln})
            nn += 1
            o += 1
    return hunks


def locate(patch: str | None, line: int) -> tuple[str, int] | None:
    """(diff_hunk, position) for a comment on new-side `line`, per GitHub's conventions; None if not in a hunk."""
    for h in _hunks(patch):
        for i, ln in enumerate(h["lines"]):
            if ln["new"] == line:
                hunk_text = "\n".join([h["header"]] + [x["text"] for x in h["lines"][: i + 1]])
                return hunk_text, ln["pos"]
    return None


def added_lines(patch: str | None) -> list[int]:
    return [ln["new"] for h in _hunks(patch) for ln in h["lines"] if ln["kind"] == "+"]


class Executor:
    def __init__(self, w: World, plan: dict[str, Any], workdir: Path):
        self.w = w
        self.plan = plan
        self.work = workdir
        self.repo = workdir / "repo"
        self.tx = Texts(w.world)
        self.ids = IdGen(w.seed)
        self.pkg = w.pkg
        self.owner = w.project["owner"]
        self.name = w.project["repo"]
        self.people = plan["people"]
        self.prs = {p["key"]: p for p in plan["prs"]}
        self.issues = {i["key"]: i for i in plan["issues"]}
        self.num = {**{p["key"]: p["number"] for p in plan["prs"]}, **{i["key"]: i["number"] for i in plan["issues"]}}
        self.module_state: dict[str, Feature] = {}       # on main
        self.module_meta: dict[str, dict[str, Any]] = {}  # module key → rendered meta
        self.pre_merge_state: dict[str, tuple[str, Feature | None]] = {}  # pr key → (module, state before merge)
        self.branch: dict[str, dict[str, Any]] = {}      # pr key → branch state
        self.ledger: dict[str, Any] = {"prs": {}, "issues": {}, "commits": {}, "comment_truth": [],
                                       "slot_truth": [], "labels": {}}
        self.applied_ci: set[str] = set()
        self._diffs: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self._current: str | None = None

    # ------------------------------------------------------------------ helpers
    def person(self, key: str) -> dict[str, Any]:
        return self.people[key]

    def ident(self, key: str, at: datetime) -> G.Identity:
        p = self.person(key)
        return G.Identity(p["name"], f"{p['gh_id']}+{p['login']}@users.noreply.github.example", iso(at) or "")

    def commit_all(self, message: str, author: str, at: datetime, committer: str | None = None) -> str:
        G.git(self.repo, "add", "-A")
        env = G.commit_env(self.ident(author, at), self.ident(committer or author, at))
        G.git(self.repo, "commit", "-q", "--allow-empty", "-m", message, env=env)
        sha, *parents = G.git(self.repo, "log", "-1", "--format=%H %P").split()
        self.ledger["commits"][sha] = {"sha": sha, "author": author, "committer": committer or author,
                                       "authored_at": iso(at), "committed_at": iso(at), "message": message,
                                       "parents": parents}
        return sha

    def diff(self, base: str, head_sha: str) -> list[dict[str, Any]]:
        k = (base, head_sha)
        if k not in self._diffs:
            self._diffs[k] = G.diff_files(self.repo, base, head_sha)
        return self._diffs[k]

    def write(self, files: dict[str, str | bytes | None]) -> None:
        for path, content in files.items():
            p = self.repo / path
            if content is None:
                if p.exists():
                    p.unlink()
                continue
            p.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                p.write_bytes(content)
            else:
                p.write_text(content, encoding="utf-8")

    def read(self, path: str) -> str:
        p = self.repo / path
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def checkout(self, ref: str) -> None:
        if self._current == ref:
            return
        G.git(self.repo, "checkout", "-q", "-f", ref)
        self._current = ref

    # ------------------------------------------------------------------ G2: initial repository
    def initial_repo(self) -> None:
        if self.work.exists():
            shutil.rmtree(self.work)
        G.init(self.repo)
        src = self.w.dir / "repo"
        for f in sorted(src.rglob("*")):
            if f.is_file():
                rel = f.relative_to(src)
                (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, self.repo / rel)
        sample = (self.repo / "tests" / "data" / "sample.conf").read_bytes()
        (self.repo / "tests" / "data" / "sample.conf.gz").write_bytes(gzip.compress(sample, mtime=0))
        m, s = self.person("maintainer"), self.person("security")
        vals = {"maintainer": m["login"], "security": s["login"], "maintainer_name": m["name"],
                "security_name": s["name"]}
        for t in sorted((self.w.dir / "templates").iterdir()):
            text = t.read_text(encoding="utf-8")
            for k, v in vals.items():
                text = text.replace("{" + k + "}", v)
            dest = self.repo / (".github/CODEOWNERS" if t.name == "CODEOWNERS" else t.name)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
        t0 = parse_ts(self.plan["timeline"]["start"]) - timedelta(days=3)
        self.base_files = sorted(str(p.relative_to(self.repo)) for p in self.repo.rglob("*")
                                 if p.is_file() and ".git" not in p.parts)
        self.main_sha = self.commit_all("Initial import of lamina 0.1.0", "maintainer", t0)
        self._current = "main"
        self.ledger["initial_sha"] = self.main_sha

    # ------------------------------------------------------------------ change rendering
    def feature_for(self, pr: dict[str, Any], toggles: set[str]) -> Feature:
        variant = next((d.get("variant") for d in pr["slots"] if d["slot"] == "E1"), None)
        return Feature(pr["area"], pr["noun"], self.pkg, frozenset(toggles & CODE_TOGGLES), variant)

    def render_files(self, pr: dict[str, Any], feat: Feature) -> tuple[dict[str, str | bytes | None], Rendered]:
        r = render(feat)
        files: dict[str, str | bytes | None] = dict(r.files)
        if pr["kind"] in ("slop",):
            files.update(self.slop_extras(pr, r))
        if pr["kind"] == "deps":
            files.update(self.deps_extras(pr, r))
        return files, r

    def slop_extras(self, pr: dict[str, Any], r: Rendered) -> dict[str, str | bytes | None]:
        out: dict[str, str | bytes | None] = {}
        traits = pr.get("slop_traits", [])
        text = r.files[r.module_path]
        if "unused_helper" in traits or "hallucinated_api" in traits:
            helper = f"\n\ndef _{pr['noun']}_helper2(value):\n"
            if "hallucinated_api" in traits:
                helper += f"    from {self.pkg}.compat import normalize_v2\n\n    return normalize_v2(value)\n"
            else:
                helper += "    result = value\n    return result\n"
            text = text + helper
        out[r.module_path] = text
        if "failing_tests" in traits:
            tp = f"tests/test_{pr['area']}_{pr['noun']}_improved.py"
            mod = r.module_path[:-3].replace("/", ".")
            out[tp] = (f"from {mod} import {r.fn}\n\n\ndef test_{pr['noun']}_improved():\n"
                       f"    assert {r.fn} is not None\n    assert False, \"TODO: update expected value\"\n")
        if "unrelated_changes" in traits:
            readme = self.read("README.md")
            out["README.md"] = readme.rstrip("\n") + "\n\n<!-- formatting -->\n"
        return out

    def deps_extras(self, pr: dict[str, Any], r: Rendered) -> dict[str, str | bytes | None]:
        dep, ver = pr["extra"]["dep"], pr["extra"]["dep_version"]
        mod = IMPORT_NAMES.get(dep, dep.replace("-", "_"))
        text = r.files[r.module_path]
        lines = text.split("\n")
        ins = next(i for i, ln in enumerate(lines) if ln.startswith("from ") or ln.startswith("import "))
        lines[ins:ins] = [f"try:\n    import {mod}  # noqa: F401\nexcept ImportError:  # pragma: no cover\n    {mod} = None\n"]
        out: dict[str, str | bytes | None] = {r.module_path: "\n".join(lines)}
        py = self.read("pyproject.toml")
        if pr["extra"]["runtime"]:
            m = re.search(r"^dependencies = \[(.*?)\]", py, re.M)
            have = m.group(1) if m else ""
            if f'"{dep}' in have:
                new = py
            else:
                new = re.sub(r"^dependencies = \[(.*?)\]", lambda mm: "dependencies = [" + (
                    mm.group(1) + ", " if mm.group(1).strip() else "") + f'"{dep}>={ver}"]', py, count=1, flags=re.M)
        elif re.search(rf"^{re.escape(mod)} = \[", py, re.M):
            new = re.sub(rf"^{re.escape(mod)} = \[.*\]$", f'{mod} = ["{dep}>={ver}"]', py, count=1, flags=re.M)
        else:
            new = py.replace('test = ["pytest==8.*"]', f'test = ["pytest==8.*"]\n{mod} = ["{dep}>={ver}"]', 1)
        out["pyproject.toml"] = new
        return out

    def modify_feature(self, pr: dict[str, Any], base: Feature, *, fixup_addressed: set[str] | None = None) -> Feature:
        slots = {d["slot"] for d in pr["slots"]}
        new_toggles = set(base.toggles)
        if pr["intent"] != "tests":
            new_toggles |= slots & (CODE_TOGGLES - {"S1", "E7", "T3"})
            if "B1" in new_toggles and "B2" in new_toggles:
                new_toggles.discard("B1")
        rev = base.rev + (1 if pr["intent"] in ("refactor", "bugfix") else 0)
        renames = dict(base.renames)
        deprecated = base.deprecated
        if pr.get("renames"):
            renames = dict(pr["renames"])
            deprecated = False
        if pr["intent"] == "tests" and base.on("S1"):
            new_toggles.discard("S1")
        f = replace(base, toggles=frozenset(new_toggles), rev=rev, renames=renames, deprecated=deprecated)
        if fixup_addressed:
            f = self.address(f, fixup_addressed)
        return f

    @staticmethod
    def address(f: Feature, addressed: set[str]) -> Feature:
        toggles = set(f.toggles) - (addressed & CODE_TOGGLES)
        deprecated = f.deprecated or ("E7" in addressed and bool(f.renames))
        return replace(f, toggles=frozenset(toggles), deprecated=deprecated)

    # ------------------------------------------------------------------ build and docs changes
    def build_change(self, pr: dict[str, Any], addressed: set[str] | None = None) -> dict[str, str | bytes | None]:
        ch = pr["extra"].get("build")
        addressed = addressed or set()
        out: dict[str, str | bytes | None] = {}
        ci = self.read(".github/workflows/ci.yml")
        if ch == "ci_python":
            out[".github/workflows/ci.yml"] = ci.replace('- run: pip install -e .[test]',
                                                         '- run: python -m pip install --upgrade pip\n      - run: pip install -e .[test]', 1) \
                if "--upgrade pip" not in ci else ci.replace("runs-on: ubuntu-latest", "runs-on: ubuntu-24.04", 1)
        elif ch == "ci_cache":
            out[".github/workflows/ci.yml"] = ci.replace("python-version: ${{ matrix.python }}",
                                                         "python-version: ${{ matrix.python }}\n          cache: pip", 1) \
                if "cache: pip" not in ci else ci + "# keep\n"
        elif ch == "release_checksums":
            rel = self.read("scripts/release.py")
            out["scripts/release.py"] = rel.replace(
                '    return subprocess.call([sys.executable, "-m", "build", str(ROOT)])',
                '    code = subprocess.call([sys.executable, "-m", "build", str(ROOT)])\n'
                '    for artefact in sorted((ROOT / "dist").glob("*")):\n'
                '        print(artefact.name, hashlib.sha256(artefact.read_bytes()).hexdigest())\n'
                '    return code', 1).replace("import pathlib\n", "import hashlib\nimport pathlib\n", 1) \
                if "hashlib" not in rel else rel.rstrip("\n") + "\n"
        elif ch == "release_fetch":
            rel = self.read("scripts/release.py")
            if "T1" in addressed or "U1" in addressed:
                out["scripts/release.py"] = rel
            else:
                out["scripts/release.py"] = rel.replace("import subprocess\n", "import subprocess\nimport urllib.request\n", 1).replace(
                    '    print(f"building lamina {version}")',
                    '    print(f"building lamina {version}")\n'
                    '    samples = urllib.request.urlopen("https://samples.lamina-configs.example/latest.tar.gz").read()\n'
                    '    (ROOT / "lamina" / "_samples.tar.gz").write_bytes(samples)', 1)
        elif ch in ("binary_fixture", "fixtures_regen", "fixtures_fetch"):
            noun = pr.get("noun") or f"fixture{pr['number']}"
            data = f"# generated sample {noun}\n[sample]\nname = {noun}\nvalue = {pr['number']}\n".encode()
            gz = gzip.compress(data, mtime=0)
            fx = f"tests/data/{noun}.conf.gz"
            out[fx] = gz
            out[f"tests/test_fixture_{noun}.py"] = (
                "import gzip\nimport pathlib\n\nfrom lamina import loads\n\nDATA = pathlib.Path(__file__).parent / \"data\"\n\n\n"
                f"def test_{noun}_fixture_loads():\n    text = gzip.decompress((DATA / \"{noun}.conf.gz\").read_bytes()).decode(\"utf-8\")\n"
                f"    assert loads(text).get(\"sample.name\") == \"{noun}\"\n")
            if "T2" in addressed:
                out[f"tests/data/{noun}.conf"] = data.decode()
            if ch == "fixtures_fetch":
                bf = self.read("scripts/build_fixtures.py")
                out["scripts/build_fixtures.py"] = bf.replace("import pathlib\n", "import pathlib\nimport urllib.request\n", 1).replace(
                    "def main() -> None:\n",
                    "MIRROR = \"https://samples.lamina-configs.example/fixtures/\"\n\n\ndef fetch(name: str) -> bytes:\n"
                    "    return urllib.request.urlopen(MIRROR + name).read()\n\n\ndef main() -> None:\n", 1)
                out[".github/workflows/ci.yml"] = ci.replace("      - run: python -m pytest -q",
                                                             "      - run: python scripts/build_fixtures.py\n      - run: python -m pytest -q", 1)
        return out

    def docs_change(self, pr: dict[str, Any]) -> dict[str, str | bytes | None]:
        path = pr["extra"]["docs_file"]
        cur = self.read(path) or f"# {path.rsplit('/', 1)[-1][:-3].title()}\n"
        topic = self.tx.pt["docs_topics"][pr["extra"]["topic"] % len(self.tx.pt["docs_topics"])]
        para = choose([
            f"\n## Example\n\nA short example of {topic}:\n\n    [app]\n    name = demo\n",
            f"\n## Notes\n\nSee the README for how {topic} interacts with the rest of lamina.\n",
            f"\n## Common questions\n\n**Does {topic} change my file?** No: lamina writes back exactly what it read.\n",
            f"\n## Details\n\n{topic.capitalize()} follows the same rules everywhere in lamina.\n"], pr["key"])
        if pr.get("kind") == "slop_docs":
            para = f"\n## Advanced usage\n\nUse `lamina.compat.normalize_v2()` to normalise {topic} before loading.\n"
        return {path: cur.rstrip("\n") + "\n" + para}

    # ------------------------------------------------------------------ events
    def events(self) -> list[tuple[datetime, int, str, str, int]]:
        ev: list[tuple[datetime, int, str, str, int]] = []
        for p in self.plan["prs"]:
            ev.append((parse_ts(p["created_at"]), 0, "open", p["key"], -1))
            for i, r in enumerate(p.get("rounds", [])):
                ev.append((parse_ts(r["at"]), 1, r["type"], p["key"], i))
            if p.get("end", {}).get("kind") in ("merged", "closed"):
                ev.append((parse_ts(p["end"]["at"]), 2, "end", p["key"], -1))
        for i in self.plan["issues"]:
            ev.append((parse_ts(i["created_at"]), 0, "issue_open", i["key"], -1))
            if i.get("closed_at") and not i.get("closed_by"):
                ev.append((parse_ts(i["closed_at"]), 3, "issue_close", i["key"], -1))
        ev.sort(key=lambda e: (e[0], e[1], self.num.get(e[3], 0)))
        return ev

    def run(self) -> dict[str, Any]:
        self.initial_repo()
        for t, _, kind, key, idx in self.events():
            if kind == "open":
                self.open_pr(self.prs[key], t)
            elif kind == "review":
                self.review(self.prs[key], idx, t)
            elif kind == "fixup":
                self.fixup(self.prs[key], idx, t)
            elif kind == "end":
                self.end_pr(self.prs[key], t)
            elif kind == "issue_open":
                self.open_issue(self.issues[key], t)
            elif kind == "issue_close":
                self.close_issue(self.issues[key], t, None)
        self.checkout("main")
        self.ledger["main_sha"] = self.main_sha
        self.ledger["people"] = self.people
        self.ledger["number"] = self.num
        return self.ledger

    # ------------------------------------------------------------------ PR lifecycle
    def head_ref(self, pr: dict[str, Any]) -> str:
        login = self.person(pr["author"])["login"]
        if pr["kind"] == "revert":
            return f"revert-{self.num[pr['target']]}"
        slug = (pr.get("noun") or pr["kind"]).replace("_", "-")
        prefix = {"bugfix": "fix", "docs": "docs", "build_ci": "ci", "deps": "deps", "refactor": "refactor",
                  "tests": "tests"}.get(pr["intent"], "feature")
        return f"{prefix}/{slug}-{pr['number']}" if not login.endswith("[bot]") else f"bot/{slug}"

    def open_pr(self, pr: dict[str, Any], t: datetime) -> None:
        self.checkout("main")
        base_sha = self.main_sha
        ref = self.head_ref(pr)
        G.git(self.repo, "checkout", "-q", "-B", f"b/{pr['number']}")
        self._current = f"b/{pr['number']}"
        rec: dict[str, Any] = {"key": pr["key"], "number": pr["number"], "author": pr["author"],
                               "association": pr["association"], "created_at": iso(t), "base_sha": base_sha,
                               "base_ref": "main", "head_ref": ref, "commits": [], "heads": [], "reviews": [],
                               "comments": [], "issue_comments": [], "timeline": [], "labels": self.labels_for(pr),
                               "requested_reviewers": [], "state": "open", "kind": pr["kind"], "intent": pr["intent"],
                               "area": pr["area"], "split": pr["split"], "live_key": pr.get("live_key"),
                               "slop_traits": pr.get("slop_traits", []), "skipped": False}
        b: dict[str, Any] = {"feature": None, "rendered": None, "addressed": set()}
        files: dict[str, str | bytes | None] = {}
        fn, test_file = None, None
        commit_at = t - timedelta(minutes=int(7 + pr["number"] % 50))
        if pr["kind"] in ("feature", "slop", "deps"):
            feat = self.feature_for(pr, {d["slot"] for d in pr["slots"]})
            files, r = self.render_files(pr, feat)
            b.update(feature=feat, rendered=r, module=pr["module"])
            fn, test_file = r.fn, r.test_path
        elif pr["kind"] in ("modify", "outcome_fix"):
            base = self.module_state.get(pr["target"])
            if base is None:
                rec["skipped"] = True
                self.ledger["prs"][pr["key"]] = rec
                self.checkout("main")
                return
            if pr["kind"] == "outcome_fix":
                cause = pr["extra"].get("fixes_slot")
                feat = replace(base, rev=base.rev + (1 if pr["extra"].get("mode") == "follow_up" or cause is None else 0))
                if cause:
                    feat = self.address(feat, {cause})
            else:
                feat = self.modify_feature(pr, base)
            files, r = self.render_files(pr, feat)
            for old in (self.module_meta.get(pr["target"], {}).get("files") or []):
                if old not in files and old.startswith("tests/") and pr["intent"] != "tests":
                    pass
            if pr["kind"] == "outcome_fix" or pr["intent"] in ("bugfix",):
                tp = f"tests/test_{pr['area']}_{pr['noun']}_regression_{pr['number']}.py"
                files[tp] = self.regression_test(r, pr)
            if pr["intent"] == "tests" and not base.on("S1"):
                tp = f"tests/test_{pr['area']}_{pr['noun']}_more_{pr['number']}.py"
                files[tp] = self.regression_test(r, pr)
            b.update(feature=feat, rendered=r, module=pr["target"])
            fn, test_file = r.fn, r.test_path
        elif pr["kind"] == "revert":
            target = self.ledger["prs"].get(pr["target"])
            if not target or not target.get("merge_commit_sha"):
                rec["skipped"] = True
                self.ledger["prs"][pr["key"]] = rec
                self.checkout("main")
                return
            ok = G.git_ok(self.repo, "revert", "--no-commit", "-m", "1", target["merge_commit_sha"])
            if not ok:
                G.git(self.repo, "revert", "--abort", check=False)
                G.git(self.repo, "reset", "-q", "--hard", base_sha)
                G.git(self.repo, "checkout", "-q", "-f", "main")
                self._current = "main"
                rec["skipped"] = True
                self.ledger["prs"][pr["key"]] = rec
                self.checkout("main")
                return
            parent = self.ledger["commits"][target["merge_commit_sha"]]["parents"][0]
            msg = (f'Revert "{target["title"]}"\n\nThis reverts commit {target["merge_commit_sha"]}, reversing\n'
                   f"changes made to {parent}.")
            sha = self.commit_all(msg, pr["author"], commit_at)
            rec.update(title=self.tx.revert_title(target["title"]), body=self.tx.revert_body(self.owner, self.name,
                                                                                             target["number"]))
            rec["commits"].append(sha)
            rec["heads"].append(sha)
            rec["reverts"] = pr["target"]
            self.finish_open(pr, rec, t)
            return
        elif pr["kind"] in ("docs", "slop_docs"):
            files = self.docs_change(pr)
        elif pr["kind"] == "build":
            files = self.build_change(pr)
        self.write(files)
        msg = self.tx.commit_message("initial", pr["key"], fn=fn or pr["kind"], noun_h=human(pr.get("noun") or ""),
                                     area_title_cap=self.tx.area_title(pr["area"]).capitalize())
        if pr["kind"] in ("docs", "slop_docs", "build"):
            msg = self.tx.pr_title(pr, fn, pr["key"])
        sha = self.commit_all(msg, pr["author"], commit_at)
        rec["commits"].append(sha)
        rec["heads"].append(sha)
        issue_num = None
        if pr["kind"] == "outcome_fix" and pr["extra"].get("issue"):
            issue_num = self.num[pr["extra"]["issue"]]
        rec["title"] = self.tx.pr_title(pr, fn, pr["key"])
        rec["body"] = self.tx.pr_body(pr, fn, test_file, pr["key"], issue_num, self.owner, self.name)
        rec["fn"] = fn
        if b.get("rendered"):
            rec["module_path"] = b["rendered"].module_path
            rec["fn"] = b["rendered"].fn
        self.branch[pr["key"]] = b
        locs: dict[str, list[Any]] = {}
        for d in pr["slots"]:
            path, line = self.slot_location(pr, b, d["slot"], rec)
            locs[d["slot"]] = [path, line]
        rec["slot_locations"] = locs
        self.branch[pr["key"]] = b
        self.finish_open(pr, rec, t)

    def finish_open(self, pr: dict[str, Any], rec: dict[str, Any], t: datetime) -> None:
        G.git(self.repo, "update-ref", f"refs/pull/{pr['number']}/head", rec["heads"][-1])
        rec["head_sha"] = rec["heads"][-1]
        reviewers = sorted({r["reviewer"] for r in pr.get("rounds", []) if r.get("type") == "review"})
        rec["requested_reviewers"] = reviewers
        rec["timeline"].append({"event": "committed", "sha": rec["head_sha"], "at": iso(t)})
        for r in reviewers:
            rec["timeline"].append({"event": "review_requested", "actor": pr["author"], "requested": r,
                                    "at": iso(t + timedelta(minutes=2))})
        for lb in rec["labels"]:
            rec["timeline"].append({"event": "labeled", "actor": "maintainer", "label": lb,
                                    "at": iso(t + timedelta(minutes=30))})
        if pr["number"] % 7 == 0 and pr["kind"] not in ("revert",):
            rec["issue_comments"].append(self.icomment("bot", "Thanks for the PR! CI runs the tests on Python "
                                                              "3.9–3.13; results appear below.",
                                                       t + timedelta(minutes=1), social=True, pr=pr))
        self.ledger["prs"][pr["key"]] = rec
        self.checkout("main")

    def regression_test(self, r: Rendered, pr: dict[str, Any]) -> str:
        mod = r.module_path[:-3].replace("/", ".")
        return (f"from {mod} import {r.fn}\n\n\ndef test_{r.fn}_regression_{pr['number']}():\n"
                f"    assert callable({r.fn})\n")

    def labels_for(self, pr: dict[str, Any]) -> list[str]:
        return {"docs": ["documentation"], "slop_docs": ["documentation"], "build": ["ci"], "deps": ["dependencies"],
                "outcome_fix": ["bug"], "revert": []}.get(pr["kind"], ["enhancement"] if pr["intent"] == "feature"
                                                          else (["bug"] if pr["intent"] == "bugfix" else []))

    # ------------------------------------------------------------------ comments
    def icomment(self, author: str, body: str, at: datetime, *, social: bool = False, question: bool = False,
                 planted: list[dict[str, Any]] | None = None, pr: dict[str, Any] | None = None,
                 rejection: bool = False) -> dict[str, Any]:
        cid = self.ids.next("icomment")
        c = {"id": cid, "author": author, "body": body, "created_at": iso(at), "association": self.assoc(author, pr)}
        self.ledger["comment_truth"].append({"comment_kind": "issue_comment", "id": cid,
                                             "pr_number": pr["number"] if pr else None, "author": author,
                                             "planted": planted or [], "social": social, "question": question,
                                             "rejection": rejection})
        return c

    def assoc(self, who: str, pr: dict[str, Any] | None) -> str:
        role = self.person(who)["role"]
        if role == "maintainer":
            return "OWNER"
        if role == "security_reviewer" or self.person(who).get("member"):
            return "MEMBER"
        if pr is not None and who == pr["author"]:
            return pr["association"]
        if role == "bot":
            return "NONE"
        return "CONTRIBUTOR"

    def slot_vals(self, pr: dict[str, Any], b: dict[str, Any], slot: str) -> dict[str, Any]:
        r: Rendered | None = b.get("rendered")
        feat: Feature | None = b.get("feature")
        anchors = self.plan.get("anchors", {})
        vals: dict[str, Any] = {"fn": r.fn if r else pr.get("noun"), "file": (r.module_path.rsplit("/", 1)[-1] if r else ""),
                                "path": r.module_path if r else "", "err_class": r.err_class if r else "LaminaError",
                                "exc": "ValueError", "var": "name", "arg": "skip", "dep": pr["extra"].get("dep"),
                                "cache_pr": self.num.get(anchors.get("cache_pr", ""), ""),
                                "revert_pr": self.num.get(anchors.get("revert_pr", ""), ""),
                                "race_issue": self.num.get(anchors.get("race_issue", ""), "")}
        if feat and feat.renames:
            old, new = next(iter(feat.renames.items()))
            vals.update(param=old, new_param=new)
        if r and slot == "S2":
            text = r.files[r.module_path]
            m = re.search(r"\b([a-z]+[A-Z][A-Za-z]+)\b", text)
            if m:
                camel = m.group(1)
                vals.update(camel=camel, snake=re.sub(r"(?<!^)(?=[A-Z])", "_", camel).lower())
            else:
                vals.update(camel="import sys", snake="(remove it)")
        if slot == "S4":
            vals["arg"] = "skip"
        if slot == "E1" and r:
            vals["suggestion"] = None
        return vals

    def slot_location(self, pr: dict[str, Any], b: dict[str, Any], slot: str, rec: dict[str, Any]
                      ) -> tuple[str | None, int | None]:
        r: Rendered | None = b.get("rendered")
        planted = {"T4": "E1"}.get(slot, slot)
        if r and planted in r.locations:
            return r.locations[planted]
        if r and slot in ("X1",):
            return r.locations.get("def", (r.module_path, 1))
        head = rec["heads"][-1]
        files = self.diff(rec["base_sha"], head)
        pats = {"E3": r"dependencies = \[.+\]", "T1": r"urlopen", "U1": r"urlopen", "T2": r"\.gz"}
        rx = pats.get(slot)
        for f in files:
            if not f["patch"]:
                continue
            for h in _hunks(f["patch"]):
                for ln in h["lines"]:
                    if ln["kind"] == "+" and rx and re.search(rx, ln["text"]):
                        return f["filename"], ln["new"]
        return None, None

    def review(self, pr: dict[str, Any], idx: int, t: datetime) -> None:
        rec = self.ledger["prs"].get(pr["key"])
        if rec is None or rec.get("skipped") or rec["state"] != "open":
            return
        rnd = pr["rounds"][idx]
        reviewer = rnd["reviewer"]
        if reviewer == pr["author"]:
            return
        b = self.branch.get(pr["key"], {})
        head = rec["heads"][-1]
        role = self.person(reviewer)["role"]
        voice = VOICE.get(role, "occasional")
        review_id = self.ids.next("review")
        files = {f["filename"]: f for f in self.diff(rec["base_sha"], head)}
        body_parts: list[str] = []
        planted_body: list[dict[str, Any]] = []
        comments = []
        key = f"{pr['key']}:{idx}"
        for fl in rnd["findings"]:
            slot = fl["slot"]
            vals = self.slot_vals(pr, b, slot)
            text = self.tx.finding_comment(voice, slot, key, vals)
            path, line = self.slot_location(pr, b, slot, rec)
            loc = locate(files[path]["patch"], line) if path in files and line else None
            if loc is None and path in files and files[path]["patch"]:
                adds = added_lines(files[path]["patch"])
                if adds:
                    line = min(adds, key=lambda x: abs(x - (line or 0)))
                    loc = locate(files[path]["patch"], line)
            planted = [{"slot": fl["planted"] if slot != "T4" else "T4", "severity": fl["severity"]}]
            if loc is None or slot in ("S1", "T2") and self.person(reviewer)["role"] != "maintainer":
                body_parts.append(text)
                planted_body.extend(planted)
                continue
            if slot == "S1" and choose(["inline", "body"], key, "s1") == "body":
                body_parts.append(text)
                planted_body.extend(planted)
                continue
            hunk, pos = loc
            cid = self.ids.next("comment")
            comments.append({"id": cid, "review_id": review_id, "in_reply_to": None, "author": reviewer, "path": path,
                             "line": line, "start_line": None, "side": "RIGHT", "original_line": line,
                             "original_commit_id": head, "commit_id": head, "position": pos, "original_position": pos,
                             "diff_hunk": hunk, "body": text, "created_at": iso(t), "updated_at": iso(t),
                             "subject_type": "line", "association": self.assoc(reviewer, pr), "slot": fl["planted"],
                             "line_text": self._line_text(head, path, line)})
            self.ledger["comment_truth"].append({"comment_kind": "review_comment", "id": cid,
                                                 "pr_number": pr["number"], "author": reviewer, "planted": planted,
                                                 "social": False, "question": False})
        social = False
        if rnd["state"] == "APPROVED" and not rnd.get("shallow"):
            if rnd.get("social"):
                body_parts.append(self.tx.social(voice, "social_approve", key))
                social = True
        elif rnd["findings"] and rnd.get("body"):
            body_parts.insert(0, self.tx.review_body(voice, rnd["state"], key))
        if rnd.get("question") and voice == "maintainer":
            q = self.tx.social("maintainer", "question", key)
            rec["issue_comments"].append(self.icomment(reviewer, q, t - timedelta(minutes=5), question=True, pr=pr))
        if rnd["state"] == "COMMENTED" and not rnd["findings"] and pr["kind"] in ("slop", "slop_docs"):
            body_parts = [self.tx.social(voice, "question", key)]
        body = "\n\n".join(body_parts)
        rec["reviews"].append({"id": review_id, "reviewer": reviewer, "state": rnd["state"], "body": body,
                               "submitted_at": iso(t), "commit_id": head, "association": self.assoc(reviewer, pr)})
        self.ledger["comment_truth"].append({"comment_kind": "review", "id": review_id, "pr_number": pr["number"],
                                             "author": reviewer, "planted": planted_body,
                                             "social": social or (not planted_body and bool(body)),
                                             "question": False, "state": rnd["state"]})
        rec["comments"].extend(comments)
        rec["timeline"].append({"event": "reviewed", "actor": reviewer, "review_id": review_id, "at": iso(t),
                                "state": rnd["state"]})

    def _line_text(self, sha: str, path: str | None, line: int | None) -> str | None:
        if not path or not line:
            return None
        text = G.show(self.repo, sha, path)
        if text is None:
            return None
        lines = text.split("\n")
        return lines[line - 1] if 0 < line <= len(lines) else None

    def fixup(self, pr: dict[str, Any], idx: int, t: datetime) -> None:
        rec = self.ledger["prs"].get(pr["key"])
        if rec is None or rec.get("skipped") or rec["state"] != "open":
            return
        rnd = pr["rounds"][idx]
        b = self.branch.get(pr["key"], {})
        addressed = set(rnd["addresses"])
        b["addressed"] |= addressed
        self.checkout(f"b/{pr['number']}")
        files: dict[str, str | bytes | None] = {}
        if b.get("feature") is not None:
            feat = self.address(b["feature"], b["addressed"])
            files, r = self.render_files(pr, feat)
            if pr["kind"] == "modify" and "S1" in addressed and r.test_path:
                pass
            b.update(feature=feat, rendered=r)
            if pr["kind"] == "deps" and "E3" in addressed:
                pr2 = {**pr, "extra": {**pr["extra"], "runtime": False}}
                py = G.show(self.repo, rec["base_sha"], "pyproject.toml") or ""
                saved = self.read("pyproject.toml")
                self.write({"pyproject.toml": py})
                files.update(self.deps_extras(pr2, r))
                self.write({"pyproject.toml": saved})
        elif pr["kind"] == "build":
            files = self.build_change(pr, b["addressed"])
        if not files:
            self.checkout("main")
            return
        self.write(files)
        msg = self.tx.commit_message("fixup", f"{pr['key']}:{idx}")
        sha = self.commit_all(msg, pr["author"], t)
        rec["commits"].append(sha)
        rec["heads"].append(sha)
        rec["head_sha"] = sha
        G.git(self.repo, "update-ref", f"refs/pull/{pr['number']}/head", sha)
        rec["timeline"].append({"event": "committed", "sha": sha, "at": iso(t)})
        self.update_outdated(rec, sha)
        # author replies in threads (acks), as context for the root finding
        for c in [c for c in rec["comments"] if c["in_reply_to"] is None and c["created_at"] <= iso(t)]:
            if c.get("replied"):
                continue
            c["replied"] = True
            kind = "ack_history" if c.get("slot") == "E5" and c["slot"] in addressed else "ack"
            if c.get("slot") not in addressed:
                if choose(["y", "n", "n"], c["id"]) != "y":
                    continue
                kind = "disagree"
            elif choose(["y", "y", "n"], c["id"]) != "y":
                continue
            cid = self.ids.next("comment")
            anchors = self.plan.get("anchors", {})
            reply = self.tx.reply(kind, str(c["id"]), cache_pr=self.num.get(anchors.get("cache_pr", ""), ""))
            rec["comments"].append({**{k: v for k, v in c.items() if k not in ("slot", "replied", "line_text")},
                                    "id": cid, "in_reply_to": c["id"], "author": pr["author"], "body": reply,
                                    "created_at": iso(t + timedelta(minutes=3)),
                                    "updated_at": iso(t + timedelta(minutes=3)),
                                    "association": pr["association"], "review_id": self.ids.next("review"),
                                    "reply_review": True})
            rec["reviews"].append({"id": rec["comments"][-1]["review_id"], "reviewer": pr["author"],
                                   "state": "COMMENTED", "body": "", "submitted_at": iso(t + timedelta(minutes=3)),
                                   "commit_id": sha, "association": pr["association"]})
            self.ledger["comment_truth"].append({"comment_kind": "review_comment", "id": cid,
                                                 "pr_number": pr["number"], "author": pr["author"], "planted": [],
                                                 "social": True, "question": False, "ack": kind != "disagree"})
        self.checkout("main")

    def update_outdated(self, rec: dict[str, Any], new_head: str) -> None:
        files = {f["filename"]: f for f in self.diff(rec["base_sha"], new_head)}
        for c in rec["comments"]:
            if c["line"] is None or c["path"] is None:
                continue
            f = files.get(c["path"])
            text = G.show(self.repo, new_head, c["path"]) if f else None
            moved = None
            if text is not None and c.get("line_text") is not None:
                lines = text.split("\n")
                hits = [i + 1 for i, ln in enumerate(lines) if ln == c["line_text"]]
                if len(hits) == 1:
                    loc = locate(f["patch"], hits[0]) if f and f["patch"] else None
                    if loc:
                        moved = (hits[0], loc)
            if moved is None:
                c["line"] = None
                c["position"] = None
            else:
                c["line"] = moved[0]
                c["position"] = moved[1][1]
                c["commit_id"] = new_head

    def end_pr(self, pr: dict[str, Any], t: datetime) -> None:
        rec = self.ledger["prs"].get(pr["key"])
        if rec is None or rec.get("skipped") or rec["state"] != "open":
            return
        end = pr["end"]
        if end["kind"] == "closed":
            if end.get("reason") in ("slop", "dependency"):
                rec["issue_comments"].append(self.icomment("maintainer", self.tx.rejection(end["reason"], pr["key"]),
                                                           t - timedelta(minutes=2), rejection=True, pr=pr,
                                                           planted=[{"slot": "E3", "severity": "blocker"}]
                                                           if end["reason"] == "dependency" else []))
            rec.update(state="closed", closed_at=iso(t))
            rec["timeline"].append({"event": "closed", "actor": end.get("by", "maintainer"), "at": iso(t),
                                    "commit_id": None})
            return
        merger = end.get("by", "maintainer")
        self.checkout("main")
        msg = f"Merge pull request #{pr['number']} from {self.person(pr['author'])['login']}/{rec['head_ref']}\n\n" \
              f"{rec['title']}"
        env = G.commit_env(self.ident(merger, t), self.ident(merger, t))
        ok = G.git_ok(self.repo, "merge", "--no-ff", "-q", "-m", msg, f"b/{pr['number']}", env=env)
        if not ok:
            G.git(self.repo, "merge", "--abort", check=False)
            G.git(self.repo, "reset", "-q", "--hard", self.main_sha)
            rec["issue_comments"].append(self.icomment("maintainer", "This conflicts with main now. Closing; feel "
                                                       "free to reopen after a rebase.", t, social=True, pr=pr))
            rec.update(state="closed", closed_at=iso(t), conflict=True)
            rec["timeline"].append({"event": "closed", "actor": "maintainer", "at": iso(t), "commit_id": None})
            return
        sha, *parents = G.git(self.repo, "log", "-1", "--format=%H %P").split()
        self.main_sha = sha
        self.ledger["commits"][sha] = {"sha": sha, "author": merger, "committer": merger, "authored_at": iso(t),
                                       "committed_at": iso(t), "message": msg, "parents": parents}
        rec.update(state="closed", merged=True, merged_at=iso(t), closed_at=iso(t), merged_by=merger,
                   merge_commit_sha=sha)
        rec["timeline"].append({"event": "merged", "actor": merger, "at": iso(t), "commit_id": sha})
        rec["timeline"].append({"event": "closed", "actor": merger, "at": iso(t), "commit_id": None})
        b = self.branch.get(pr["key"], {})
        mod = b.get("module")
        if pr["kind"] == "revert":
            target = self.prs[pr["target"]]
            tmod, before = self.pre_merge_state.get(target["key"], (None, None))
            if tmod:
                if before is None:
                    self.module_state.pop(tmod, None)
                else:
                    self.module_state[tmod] = before
        elif mod and b.get("feature") is not None:
            self.pre_merge_state[pr["key"]] = (mod, copy.deepcopy(self.module_state.get(mod)))
            self.module_state[mod] = b["feature"]
            self.module_meta[mod] = {"files": sorted(b["rendered"].files), "fn": b["rendered"].fn}
        # issues closed by this PR
        for iss in self.plan["issues"]:
            if iss.get("closed_by") == pr["key"]:
                self.close_issue(iss, t + timedelta(minutes=1), pr)

    # ------------------------------------------------------------------ issues
    def open_issue(self, iss: dict[str, Any], t: datetime) -> None:
        rec = {"key": iss["key"], "number": iss["number"], "author": iss["author"], "created_at": iso(t),
               "labels": iss["labels"], "state": "open", "comments": [], "timeline": [], "kind": iss["kind"]}
        if iss["kind"] == "bug":
            culprit = self.ledger["prs"].get(iss["culprit"]) if iss.get("culprit") else None
            fn = culprit.get("fn") if culprit else "load"
            param = "strict"
            b = self.branch.get(iss.get("culprit") or "", {})
            if b.get("feature") is not None and b["feature"].renames:
                param = next(iter(b["feature"].renames))
            title, body = self.tx.bug_issue(iss.get("slot"), {"fn": fn, "pr": culprit["number"] if culprit else "",
                                                              "param": param})
            rec.update(title=title, body=body)
            if culprit:
                culprit["timeline"].append({"event": "cross-referenced", "actor": iss["author"], "at": iso(t),
                                            "source_issue": iss["number"]})
        else:
            title, body = self.tx.feature_issue(iss.get("title_idx", 0))
            rec.update(title=title, body=body)
        rec["timeline"].append({"event": "labeled", "actor": "maintainer", "label": iss["labels"][0] if iss["labels"]
                                else "bug", "at": iso(t + timedelta(minutes=40))})
        self.ledger["issues"][iss["key"]] = rec

    def close_issue(self, iss: dict[str, Any], t: datetime, by_pr: dict[str, Any] | None) -> None:
        rec = self.ledger["issues"].get(iss["key"])
        if rec is None or rec["state"] != "open":
            return
        rec.update(state="closed", closed_at=iso(t), state_reason="completed")
        actor = "maintainer"
        sha = None
        if by_pr is not None:
            prec = self.ledger["prs"].get(by_pr["key"])
            sha = prec.get("merge_commit_sha") if prec else None
            rec["comments"].append(self.icomment("maintainer", f"Fixed in #{by_pr['number']}.", t, social=True))
            rec["closed_by_pr"] = by_pr["number"]
            if prec:
                rec["timeline"].append({"event": "cross-referenced", "actor": by_pr["author"], "at": prec["created_at"],
                                        "source_issue": by_pr["number"]})
        rec["timeline"].append({"event": "closed", "actor": actor, "at": iso(t), "commit_id": sha})


def execute(w: World, plan: dict[str, Any], workdir: Path) -> dict[str, Any]:
    return Executor(w, plan, workdir).run()


def save_ledger(ledger: dict[str, Any], path: Path) -> None:
    def conv(o: Any) -> Any:
        if isinstance(o, set):
            return sorted(o)
        raise TypeError(type(o))
    path.write_text(json.dumps(ledger, default=conv, indent=1))
