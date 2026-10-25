"""Every screen's read endpoints answer from the snapshot (FR-DATA-4, test_no_key_mode_serves_all_screens)."""

from __future__ import annotations

import json


def test_no_key_mode_serves_all_screens(client, monkeypatch):
    A = "/api/v1"
    st = client.get(A + "/status").json()
    pid = st["default_project_id"]
    assert st["data"]["snapshot"] is True
    q = client.get(f"{A}/projects/{pid}/queue")
    assert q.status_code == 200 and q.json()["items"]
    assert all(r["status"] != "waiting" for r in q.json()["items"]), "every open PR has a saved analysis"
    n = q.json()["items"][0]["number"]
    for path in (f"/projects/{pid}/pulls/{n}", f"/projects/{pid}/pulls/{n}/analysis", f"/projects/{pid}/pulls/{n}/diff",
                 f"/projects/{pid}/pulls/{n}/review-draft", f"/projects/{pid}/lenses", f"/projects/{pid}/fidelity-runs",
                 f"/projects/{pid}/practice/overview", "/chat/examples", "/tour", "/glossary", "/settings", "/usage"):
        r = client.get(A + path)
        assert r.status_code == 200, (path, r.text[:300])
    lens = client.get(f"{A}/projects/{pid}/lenses").json()["items"][0]
    for sub in ("", "/edge-map", "/growth", "/bias", "/audit"):
        assert client.get(f"{A}/lenses/{lens['id']}{sub}").status_code == 200, sub
    run = client.get(f"{A}/projects/{pid}/fidelity-runs").json()["items"][0]
    assert client.get(f"{A}/fidelity-runs/{run['id']}").status_code == 200
    assert client.get(f"{A}/fidelity-runs/{run['id']}/cases").status_code == 200
    ex = client.get(A + "/chat/examples").json()
    assert ex["items"] and all(e["answer_md"] for e in ex["items"])
    # without a key, actions say so instead of spending
    from keeper.config import get_settings
    monkeypatch.setattr(type(get_settings()), "live", property(lambda self: False))
    r = client.post(f"{A}/projects/{pid}/pulls/{n}/analysis", json={})
    assert r.status_code in (402, 403, 409, 412, 424, 503) and json.loads(r.text)["error"]["code"] == "no_api_key"


def test_citations_verified(client):
    """Markers that don't refer to an object a tool returned in this turn are dropped (no card)."""
    from keeper.assistant import loop
    assert loop.card_id({"type": "pull", "data": {"number": 5}}) == "5"
    A = "/api/v1"
    th = client.post(A + "/chat/threads", json={"context": None}).json()
    r = client.post(f"{A}/chat/threads/{th['id']}/messages", json={"text": "What needs me today?"})
    assert r.status_code == 200
    cards = [json.loads(line[5:])["card"] for line in r.text.splitlines()
             if line.startswith("data:") and '"card"' in line]
    text = "".join(json.loads(line[5:]).get("text", "") for line in r.text.splitlines()
                   if line.startswith("data:") and '"text"' in line)
    import re
    markers = set(re.findall(r"\[\[([a-z_]+):([^\]\s]+?)\]\]", text))
    ids = {(c["type"], loop.card_id(c)) for c in cards}
    assert ids <= markers | {(c["type"], loop.card_id(c)) for c in cards if c["type"] == "action"}
    assert cards, "the queue answer cites PRs"
