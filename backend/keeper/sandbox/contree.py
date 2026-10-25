"""Token Factory Sandboxes (beta). Access is granted per project from the Token Factory dashboard; the API
names are not verified for this build [verify], so this runner reports itself unavailable unless configured,
and the fallback order applies (docs/04-architecture/05 §3.3)."""

from __future__ import annotations

from keeper.config import get_settings
from keeper.sandbox.base import Availability
from keeper.sandbox.local import LocalRunner


class ContreeRunner(LocalRunner):
    name = "contree"

    def __init__(self) -> None:
        super().__init__()
        self.isolation = "Token Factory Sandboxes: VM isolation."

    async def available(self) -> Availability:
        s = get_settings()
        if not s.CONTREE_API_URL or not s.CONTREE_API_KEY.get_secret_value():
            return Availability(False, "Token Factory Sandboxes not enabled for this project")
        return Availability(False, "Token Factory Sandboxes client not implemented in this build; access unverified")
