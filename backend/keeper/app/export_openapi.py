"""Print the OpenAPI document (run.sh step 7: > frontend/src/api/openapi.json)."""

from __future__ import annotations

import json
import sys


def main() -> None:
    from keeper.app import create_app

    app = create_app(run_startup=False)
    doc = app.openapi()
    from keeper.app import events as ev
    doc.setdefault("components", {}).setdefault("schemas", {}).update(ev.event_schemas())
    sys.stdout.write(json.dumps(doc, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
