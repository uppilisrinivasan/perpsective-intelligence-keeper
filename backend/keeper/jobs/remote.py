"""Entry point inside a Nebius Serverless Job (python -m keeper.jobs.remote --job ID). Not used in this build."""

import sys

if __name__ == "__main__":
    print("keeper.jobs.remote: remote jobs are not enabled in this build; use JOB_RUNNER=local", file=sys.stderr)
    sys.exit(2)
