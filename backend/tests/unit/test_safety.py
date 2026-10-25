"""Guardrails that must hold whatever a model returns."""

from __future__ import annotations

import inspect

import pytest

from keeper.config import get_config


def test_github_client_get_only(monkeypatch):
    from keeper.sources.github import client as C
    public = [n for n, _ in inspect.getmembers(C.GitHubClient, inspect.isfunction) if not n.startswith("_")]
    assert all(n.startswith("get") or n == "close" for n in public), public
    src = inspect.getsource(C)
    for verb in ('"POST"', '"PUT"', '"PATCH"', '"DELETE"', ".post(", ".put(", ".patch(", ".delete("):
        assert verb not in src


def test_sandbox_commands_from_recipes_only():
    from keeper.core.errors import KeeperError
    from keeper.sandbox.recipes import command, recipes
    r = recipes()["python-pytest"]
    cmd = command(r, "test_targeted", python="/py", tests=["tests/test_a.py"])
    assert cmd[0] == "/py" and cmd[-1] == "tests/test_a.py"
    for bad in (["--rootdir=/"], ["../../etc/passwd"], ["/etc/passwd"], ["-p", "evil"]):
        with pytest.raises(KeeperError):
            command(r, "test_targeted", python="/py", tests=bad)


def test_fix_never_deletes_tests():
    from keeper.fix.edits import apply
    files = {"tests/test_x.py": "def test_a():\n    assert 1\n\n\ndef test_b():\n    assert 2\n"}
    plan = {"edits": [{"path": "tests/test_x.py", "search": "def test_b():\n    assert 2\n", "replace": ""}]}
    changed, errors = apply(files, plan, get_config().routing, "tests/**")
    assert not changed and any("removes or skips tests" in e for e in errors)
    plan = {"edits": [{"path": "tests/test_x.py", "search": "def test_b():",
                       "replace": "@pytest.mark.skip\ndef test_b():"}]}
    changed, errors = apply(files, plan, get_config().routing, "tests/**")
    assert not changed and errors


def test_fix_refuses_build_files():
    from keeper.fix.edits import apply
    files = {"pyproject.toml": "[project]\nname = 'x'\n"}
    plan = {"edits": [{"path": "pyproject.toml", "search": "name = 'x'", "replace": "name = 'y'"}]}
    changed, errors = apply(files, plan, get_config().routing, "tests/**")
    assert not changed and errors


def test_exported_review_has_keeper_label():
    import json

    from keeper.review.export import github_json, markdown
    label = get_config().review["label_line"].format(maintainer="M")
    d = {"body_md": "Thanks!", "comments": [{"path": "a.py", "line": 3, "body_md": "Check this."}], "event": "COMMENT"}
    assert markdown(d, label, "h").rstrip().endswith(label)
    payload = json.loads(github_json(d, label))
    assert payload["body"].endswith(label) and all(c["body"].endswith(label) for c in payload["comments"])


def test_baseline_never_falls_back(monkeypatch):
    from keeper.core.errors import ModelUnavailable
    from keeper.llm.gateway import LLMGateway
    gw = LLMGateway()
    monkeypatch.setattr(gw, "fake", False)
    monkeypatch.setattr(gw, "_usable", lambda mid: False)
    role = get_config().baseline["llm"]["role"]
    with pytest.raises(ModelUnavailable):
        gw.resolve(role, allow_fallback=False)


def test_spend_cap_blocks_calls(monkeypatch):
    from keeper.core.errors import SpendCapReached
    from keeper.llm import meter
    monkeypatch.setattr(meter, "spent", lambda period=None: 1e9)
    with pytest.raises(SpendCapReached):
        meter.check_spend(0.01)


def test_slop_ignores_author_association():
    """The slop rules see the PR without its author (FR-TRI bias guard)."""
    import inspect as I

    from keeper.analysis import pipeline
    src = I.getsource(pipeline.analyze_pr)
    assert "no_author=True" in src
    from keeper.route import triage
    assert "association" not in I.getsource(triage.slop_rules)
