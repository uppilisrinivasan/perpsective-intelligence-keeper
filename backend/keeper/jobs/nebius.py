"""JOB_RUNNER=nebius: heavy jobs (learn, recalibrate, fidelity) on Nebius Serverless Jobs.

Not exercised in this build (no Nebius project); the documented flow is in docs/09-deployment/02 §6. When
selected without the CLI and credentials, Keeper falls back to the local runner and says so.
"""

from __future__ import annotations

import shutil

from keeper.config import get_settings


def available() -> tuple[bool, str | None]:
    s = get_settings()
    if not shutil.which("nebius"):
        return False, "the Nebius CLI is not installed"
    if not s.NEBIUS_SA_CREDENTIALS.get_secret_value() or not s.S3_BUCKET:
        return False, "Serverless Jobs credentials or the bucket are not configured"
    return False, "remote job submission is not implemented in this build"
