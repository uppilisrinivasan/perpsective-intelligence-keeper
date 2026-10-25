"""Import a public GitHub repository (FR-ING): GET-only reads into a local mirror, then the normal ingest.
Not available in this build; the job fails with a clear message (see docs/build-log.md)."""

from __future__ import annotations

from typing import Any

from keeper.core.errors import KeeperError


async def run_import(job: Any) -> dict[str, Any]:
    raise KeeperError("Importing a GitHub repository isn't available in this build yet. The demo project works fully.",
                      code="not_implemented", http_status=501)
