"""Extract the GitHub REST component schemas Keeper reads into config/schemas/github/ (docs/03-data/02 §1).

Downloads a pinned commit of github/rest-api-description and writes one JSON Schema per component, with every
transitively referenced component inlined under `$defs`. Usage:
    backend/.venv/bin/python scripts/extract_github_schemas.py [--source path/to/api.github.com.json]
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

PINNED_COMMIT = "bb754941722779d8a5b3a2f25a5fbb7ce794e1ea"
URL = ("https://raw.githubusercontent.com/github/rest-api-description/{sha}/descriptions/api.github.com/"
       "api.github.com.json")
COMPONENTS = ["full-repository", "pull-request-simple", "pull-request", "diff-entry", "pull-request-review",
              "pull-request-review-comment", "commit", "issue", "issue-comment", "timeline-issue-events", "check-run",
              "label", "simple-user"]
ROOT = Path(__file__).resolve().parents[1]
# Known gaps between the OpenAPI description and what the API returns (documented in docs/build-log.md):
# outdated review comments come back with "line": null and "position": null.
NULLABLE_OVERRIDES = {"pull-request-review-comment": ["line", "position", "original_line", "original_position"]}
PREFIX = "#/components/schemas/"


def refs(node, found):
    if isinstance(node, dict):
        r = node.get("$ref")
        if isinstance(r, str) and r.startswith(PREFIX):
            found.add(r[len(PREFIX):])
        for v in node.values():
            refs(v, found)
    elif isinstance(node, list):
        for v in node:
            refs(v, found)


def rewrite(node):
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k == "$ref" and isinstance(v, str) and v.startswith(PREFIX):
                out[k] = "#/$defs/" + v[len(PREFIX):]
            elif k in ("example", "examples", "description", "externalDocs"):
                continue
            elif k == "nullable" and v is True:
                continue
            else:
                out[k] = rewrite(v)
        if node.get("nullable") is True:
            return {"anyOf": [out, {"type": "null"}]}
        return out
    if isinstance(node, list):
        return [rewrite(v) for v in node]
    return node


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source")
    a = ap.parse_args()
    if a.source:
        spec = json.loads(Path(a.source).read_text())
    else:
        spec = json.loads(urllib.request.urlopen(URL.format(sha=PINNED_COMMIT), timeout=180).read())
    comps = spec["components"]["schemas"]
    out = ROOT / "config" / "schemas" / "github"
    out.mkdir(parents=True, exist_ok=True)
    for name in COMPONENTS:
        need, todo = set(), [name]
        while todo:
            n = todo.pop()
            if n in need:
                continue
            need.add(n)
            f: set[str] = set()
            refs(comps[n], f)
            todo.extend(f - need)
        comp = json.loads(json.dumps(comps[name]))
        for prop in NULLABLE_OVERRIDES.get(name, []):
            if prop in comp.get("properties", {}):
                comp["properties"][prop]["nullable"] = True
        comps = {**comps, name: comp}
        schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": name,
                  "$comment": f"Extracted from github/rest-api-description@{PINNED_COMMIT}", **rewrite(comps[name]),
                  "$defs": {n: rewrite(comps[n]) for n in sorted(need) if n != name}}
        (out / f"{name}.json").write_text(json.dumps(schema, indent=1, sort_keys=True) + "\n")
    (out / "_source.json").write_text(json.dumps({"repo": "github/rest-api-description", "commit": PINNED_COMMIT,
                                                  "components": COMPONENTS}, indent=2) + "\n")
    print(f"wrote {len(COMPONENTS)} schemas to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
