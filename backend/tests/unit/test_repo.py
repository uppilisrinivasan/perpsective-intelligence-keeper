"""Repository hygiene: secrets, .env.example, the data manifest, hardcoded values."""

from __future__ import annotations

import contextlib
import re
import subprocess

from keeper.config.settings import Settings

PORT_AND_HOSTS = ("8430", "tokenfactory.nebius.com", "api.github.com", "osv.dev")
NOT_IN_EXAMPLE = {"KEEPER_ALLOW_OPEN"}  # deliberately undocumented there (docs/07-configuration/01 §5)


def _tracked(root):  # type: ignore[no-untyped-def]
    try:
        out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=root, capture_output=True, text=True,
                             check=True).stdout.split()
    except Exception:  # noqa: BLE001
        out = []
    return [root / f for f in out]


def test_no_secrets_in_repo(root):
    from keeper.cli.__main__ import secret_scan
    assert secret_scan(root) == []
    pat = re.compile(r"\b(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|tvly-[A-Za-z0-9]{20,})")
    for f in _tracked(root):
        if f.name == ".env" or f.suffix in (".bundle", ".gz", ".png", ".zip") or not f.is_file():
            continue
        with contextlib.suppress(IsADirectoryError):
            assert not pat.search(f.read_text(encoding="utf-8", errors="ignore")), f


def test_env_example_complete(root):
    keys = set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", (root / ".env.example").read_text(), re.M))
    fields = set(Settings.model_fields)
    missing = sorted(fields - keys - NOT_IN_EXAMPLE)
    assert not missing, f"settings missing from .env.example: {missing}"


def test_data_manifest_hashes(root):
    from keeper.datagen.validate import verify_manifest
    assert verify_manifest(root / "data") == []


def test_prompt_versions_locked():
    from keeper.llm.prompts import check_lock
    assert check_lock() == []


def test_hardcode_guard_models_and_ports(root):
    bad = []
    for f in (root / "backend" / "keeper").rglob("*.py"):
        rel = f.relative_to(root)
        text = f.read_text(encoding="utf-8")
        if "nvidia/" in text or re.search(r"\bNemotron-", text):
            bad.append(f"{rel}: model id")
        if rel.as_posix() != "backend/keeper/config/settings.py":
            for p in PORT_AND_HOSTS:
                if re.search(rf"\b{re.escape(p)}\b", text):
                    bad.append(f"{rel}: {p}")
    assert not bad, bad


def test_hardcode_guard_demo_values(root):
    import json
    m = json.loads((root / "data" / "manifest.json").read_text())
    proj = m["project"]
    words = {proj["owner"], proj["repo"], proj["primary_maintainer_login"], proj.get("learner_login"),
             proj.get("security_reviewer_login")} - {None}
    bad = []
    for f in (root / "backend" / "keeper").rglob("*.py"):
        if "datagen" in f.parts:
            continue
        text = f.read_text(encoding="utf-8")
        for w in words:
            if re.search(rf"(?<![\w-]){re.escape(w)}(?![\w-])", text):
                bad.append(f"{f.relative_to(root)}: {w}")
    assert not bad, bad
