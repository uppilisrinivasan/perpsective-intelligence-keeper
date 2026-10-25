"""Write config/schemas/config/<name>.schema.json from the committed YAML files.

The schemas pin the *shape* of each file: top-level keys are required, and every known key keeps its type.
Re-run after adding a key on purpose: backend/.venv/bin/python scripts/gen_config_schemas.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from keeper.config.loader import CONFIG_FILES, load_config  # noqa: E402


def infer(v, depth):
    if isinstance(v, bool):
        return {"type": "boolean"}
    if isinstance(v, (int, float)):
        return {"type": "number"}
    if isinstance(v, str):
        return {"type": "string"}
    if v is None:
        return {}
    if isinstance(v, list):
        kinds = {type(x).__name__ for x in v}
        if v and len(kinds) == 1 and not isinstance(v[0], (dict, list)):
            return {"type": "array", "items": infer(v[0], depth + 1)}
        return {"type": "array"}
    if isinstance(v, dict):
        s = {"type": "object", "properties": {k: infer(x, depth + 1) for k, x in v.items()}}
        if depth == 0:
            s["required"] = sorted(v)
        return s
    return {}


cfg = load_config(validate=False)
out = ROOT / "config" / "schemas" / "config"
out.mkdir(parents=True, exist_ok=True)
for name in CONFIG_FILES:
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": f"config/{name}.yaml",
              **infer(cfg[name], 0)}
    (out / f"{name}.schema.json").write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
print(f"wrote {len(CONFIG_FILES)} schemas to {out.relative_to(ROOT)}")
