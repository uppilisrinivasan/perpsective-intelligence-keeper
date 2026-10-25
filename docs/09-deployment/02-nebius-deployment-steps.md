# Nebius deployment steps

These commands follow the Nebius documentation (Serverless AI, Container Registry, Object Storage, SecretStash, Managed PostgreSQL, CLI). Flags change, so run `nebius <command> --help` before each step and prefer the docs where they differ [verify]. Values in `<angle brackets>` are yours; record the non-secret ones in `.env` (`NEBIUS_*`, `S3_*`).

The steps are wrapped in `infra/nebius/deploy.sh`, which is idempotent, prints each command before running it, and supports `--dry-run`. Nothing here runs from `./run.sh`.

## 0. Prerequisites

- A Nebius AI Cloud account and project (use `eu-north1`, which has every service used here).
- A Token Factory API key for the deployment, **separate from your development key** so it can be revoked after judging. Enable Zero Data Retention for the organisation in Token Factory.
- Docker (with buildx), `jq`, and the Nebius CLI:

```bash
curl -sSL https://artifacts.nebius.cloud/cli/install.sh | bash
nebius profile create --profile keeper --endpoint api.nebius.cloud \
  --federation-endpoint auth.nebius.com --parent-id <project_id>     # opens a browser to sign in
```

- Your subnet ID (console → VPC → Subnets); record it as `NEBIUS_SUBNET_ID`.

## 1. Image

```bash
nebius registry create --name keeper
# Registry path = the registry ID without the "registry-" prefix
nebius registry configure-helper
docker buildx build --platform linux/amd64 -f infra/docker/Dockerfile \
  -t cr.eu-north1.nebius.cloud/<registry_path>/keeper-app:<git_sha> --push .
```

The Dockerfile:
1. `node:22-slim` stage: `npm ci && npm run build` in `frontend/`.
2. `python:3.12-slim` stage (pinned by digest): install `git`; create user `keeper`; `uv sync --frozen` (or `pip install -r requirements.lock`); copy `backend/`, `config/`, `data/`, and `frontend/dist` from stage 1; build the sandbox wheelhouse; `ENV APP_HOST=0.0.0.0 APP_PORT=8430 OPEN_BROWSER=false`; `USER keeper`; `EXPOSE 8430`; `HEALTHCHECK` on `/api/v1/health`; `ENTRYPOINT ["infra/docker/entrypoint.sh"]`.
3. `entrypoint.sh`: run migrations; if `NEBIUS_SA_CREDENTIALS` is set, create the CLI profile for the job runner (§6); `exec python -m keeper.app`.
4. `.dockerignore` excludes `.env*`, `.runtime/`, `node_modules/`, `.venv/`, `.git/`, `frontend/dist` (rebuilt), and test reports. **The image contains no secrets** (checked in CI with `docker run … gitleaks detect --no-git -s /app`).

## 2. Object Storage (for remote jobs)

```bash
nebius iam service-account create --name keeper-storage-sa
nebius iam v2 access-key create --account-service-account-id <sa_id> --description 'keeper jobs'
nebius iam v2 access-key get --id <access_key_id> --format json   # .status.aws_access_key_id and .status.secret
# Add the service account to the project's editors group (Object Storage quickstart)
nebius storage bucket create --name <bucket_name>
```

Record `S3_ENDPOINT_URL=https://storage.eu-north1.nebius.cloud`, `S3_REGION=eu-north1`, `S3_BUCKET`, and the two keys (secrets).

## 3. Secrets (SecretStash, CLI `mysterybox`)

```bash
nebius mysterybox secret create --name keeper-secrets --secret-version-payload '[
  {"key": "NEBIUS_API_KEY",         "string_value": "<token_factory_key_for_deployment>"},
  {"key": "KEEPER_ACCESS_CODES",    "string_value": "<code_for_judges>,<code_for_team>"},
  {"key": "KEEPER_SESSION_SECRET",  "string_value": "<long_random_string>"},
  {"key": "S3_ACCESS_KEY_ID",       "string_value": "<…>"},
  {"key": "S3_SECRET_ACCESS_KEY",   "string_value": "<…>"},
  {"key": "TAVILY_API_KEY",         "string_value": "<optional>"}
]'
```

Generate random strings with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`. Each `--env-secret KEY=<secret_selector>` must use a payload key, and a variable cannot be in both `--env` and `--env-secret`.

## 4. Optional: Managed PostgreSQL (recommended for judging)

```bash
nebius msp postgresql v1alpha1 cluster create --name keeper-db \
  --config-version 16 \
  --config-template-resources-platform cpu-e2 --config-template-resources-preset 2vcpu-8gb \
  --config-template-hosts-count 1 \
  --bootstrap-user-password '<password>'
nebius msp postgresql v1alpha1 cluster get-by-name --name keeper-db \
  --format jsonpath='{.status.connection_endpoints.private_read_write}'
```

Add `DATABASE_URL=postgresql+psycopg://<user>:<password>@<endpoint>:5432/<db>?sslmode=verify-full` to SecretStash. On first start, the app migrates and loads the demo data and the snapshot into PostgreSQL.

## 5. The app endpoint

```bash
nebius ai endpoint create --name keeper-app \
  --image cr.eu-north1.nebius.cloud/<registry_path>/keeper-app:<git_sha> \
  --platform cpu-d3 --preset 4vcpu-16gb \
  --public --container-port 8430 \
  --env "KEEPER_MODE=demo,KEEPER_AUTH_MODE=access_code,APP_HOST=0.0.0.0,APP_PORT=8430,OPEN_BROWSER=false,API_DOCS=false,IMPORT_ALLOWED=false,JOB_RUNNER=local,KEEPER_SPEND_CAP_USD=10,KEEPER_SPEND_CAP_PERIOD=day,KEEPER_AUTO_APPROVE_USD=0.20,API_RATE_LIMIT_PER_MINUTE=60,SANDBOX_PROVIDER=local,BATCH_API_ENABLED=true,S3_ENDPOINT_URL=https://storage.eu-north1.nebius.cloud,S3_REGION=eu-north1,S3_BUCKET=<bucket_name>" \
  --env-secret NEBIUS_API_KEY=<secret_selector> \
  --env-secret KEEPER_ACCESS_CODES=<secret_selector> \
  --env-secret KEEPER_SESSION_SECRET=<secret_selector> \
  --env-secret S3_ACCESS_KEY_ID=<secret_selector> \
  --env-secret S3_SECRET_ACCESS_KEY=<secret_selector> \
  --subnet-id <subnet_id>

nebius ai endpoint get <endpoint_id> --format json | jq -r '.status.public_endpoints[] | select(startswith("https://"))' | head -1
nebius ai endpoint logs <endpoint_id>
```

- Set the disk to ≥ 20 GiB (the flag is shown by `--help`).
- Use `JOB_RUNNER=nebius` after §6 is set up. Use `SANDBOX_PROVIDER=contree` if Sandboxes access is granted (add `CONTREE_API_KEY` as a secret).
- Add `--env-secret DATABASE_URL=…` when using §4, and `TAVILY_API_KEY` if used.
- Access control: keep Keeper's access-code sign-in on. Check `--auth` options with `--help`; choose the one that allows browser access.
- A stopped endpoint is not billed; stop it after judging ends.

## 6. Serverless Jobs for heavy work (`JOB_RUNNER=nebius`)

For each `learn`, `recalibrate` or `fidelity` job, the app's `nebius` runner uploads the input to `s3://<bucket>/jobs/<job_id>/input.json` and runs:

```bash
nebius ai job create --name keeper-<kind>-<job_id> \
  --image cr.eu-north1.nebius.cloud/<registry_path>/keeper-app:<git_sha> \
  --container-command python --args "-m keeper.jobs.remote --job <job_id>" \
  --platform cpu-d3 --preset 4vcpu-16gb --timeout 1h \
  --env "JOB_INPUT_URI=s3://<bucket>/jobs/<job_id>/input.json,JOB_OUTPUT_URI=s3://<bucket>/jobs/<job_id>/output.json,S3_ENDPOINT_URL=https://storage.eu-north1.nebius.cloud,S3_REGION=eu-north1,LLM_PROVIDER=nebius" \
  --env-secret NEBIUS_API_KEY=<secret_selector> \
  --env-secret S3_ACCESS_KEY_ID=<secret_selector> \
  --env-secret S3_SECRET_ACCESS_KEY=<secret_selector> \
  --subnet-id <subnet_id>

nebius ai job get <nebius_job_id>          # polled by the runner
nebius ai job logs <nebius_job_id> --follow
nebius ai job cancel <nebius_job_id>
```

The runner calls the CLI through `subprocess` with fixed argument lists (the `keeper.jobs.nebius` module), so the container needs the CLI and a profile for a service account allowed to create jobs:

```bash
nebius iam service-account create --name keeper-jobs-sa          # grant it permission to create jobs in the project
nebius iam auth-public-key generate --service-account-id <sa_id> --output credentials.json
# Store the file content in SecretStash as NEBIUS_SA_CREDENTIALS; never commit credentials.json (it is git-ignored)
```

The entrypoint writes it to a temp file and runs `nebius profile create --endpoint api.nebius.cloud --service-account-file <tmp> --parent-id <project_id> --profile keeper`. Without this, keep `JOB_RUNNER=local`; jobs then run inside the endpoint, which is enough for the demo.

## 7. Optional: self-hosted Nemotron on a GPU endpoint

For a model not on Token Factory (for example a fine-tuned Nemotron), serve it with vLLM and point `LLM_PROVIDER=openai_compatible` at it:

```bash
nebius ai endpoint create --name keeper-llm \
  --image vllm/vllm-openai:<version> \
  --container-command "python3 -m vllm.entrypoints.openai.api_server" \
  --args "--model <hf_model_id> --host 0.0.0.0 --port 8000" \
  --platform gpu-l40s-a --preset 1gpu-8vcpu-32gb \
  --public --container-port 8000 --auth token --token "<llm_token>" \
  --shm-size 16Gi --subnet-id <subnet_id>
```

Then `LLM_BASE_URL=<url>/v1` and `LLM_API_KEY=<llm_token>` (as secrets). This is not needed for v1.

## 8. Smoke test after each deployment

`infra/nebius/smoke.sh <url> <access_code>` checks:
1. `GET /api/v1/health` returns `ok`; `GET /api/v1/status` (after sign-in) shows `live: true`, all roles `available`, and the expected sandbox provider.
2. Sign in through the UI in a fresh incognito window; the tour starts; the Queue answer header shows counts.
3. Open the tour's aha PR; Compare shows the pair.
4. Run **Analyse again** on one PR: completes in < 90 s; Settings → Usage shows the calls with Nemotron model IDs.
5. Run **Fix and test** on the fix-demo finding: completes with passing tests.
6. Ask "What needs me today?" and get an answer with PR chips.
7. (If `JOB_RUNNER=nebius`) Proof → Run with batch off: the remote job appears in `nebius ai job list` and finishes.

## 9. Updating and teardown

- **Update:** build a new tag → `nebius ai endpoint update <id> --image …:<new_sha>` [verify] (or delete and create) → smoke test. Keep the submitted tag's image as a fallback.
- **Teardown after 15 Dec:** stop and delete the endpoint; delete finished jobs; empty and delete the bucket; delete the PostgreSQL cluster, the registry images and the secret; **revoke the deployment Token Factory key**.
