# Jobs and streaming

## 1. Job kinds

| Kind | Started by | Steps (emitted as `job.step`) | Typical duration (live) |
|---|---|---|---|
| `load_demo` | Startup | verify manifest → ingest → unbundle → load snapshot | 10–30 s (first run) |
| `import` | Settings → Import | fetch → ingest → clone | minutes (rate limits) |
| `learn` | After an import, or Lens → Rebuild | L2 → L3 → L4 → L5 → L6 → L7 → L8 → L9 (optional) → L10 | 5–20 min |
| `triage` | Queue → Refresh | per PR: A1…A8 | 1–3 min for 12 PRs |
| `analyze` | PR → Analyse again | A1…A8 | 20–60 s |
| `fix` | PR → Fix and test | the fix state machine | 1–4 min |
| `handoff` | PR → Hand to … | A10 | 10 s |
| `lens_update` | Lens → Update (from feedback) | incremental L6 → L7 → diff | 1–3 min |
| `recalibrate` | Lens → Recalibrate, or the schedule | L7 → a new version | 1–5 min |
| `fidelity` | Proof → Run | held-out list → per PR → metrics → bootstrap → falsifiers | 3–8 min (or batch) |
| `practice_score` | Practice → Submit | per item: matching + feedback | 10–30 s |

## 2. Lifecycle

`queued → running → succeeded | failed | cancelled`; on startup, `running → interrupted`. Each job has `params`, `progress` (0–1), `step`, `result`, `error`, `cost_usd`.

- **Concurrency:** `JOB_WORKERS` (2) concurrent jobs. A job of the same kind and key (for example `fix` on the same analysis) is deduplicated: the existing job's ID is returned with `200 existing: true`.
- **Cancellation:** `POST /api/v1/jobs/{id}/cancel` sets a flag. Steps check it between model calls and test runs; sandboxes are torn down; status becomes `cancelled`.
- **Resumption:** idempotent kinds (`learn`, `fidelity`, `triage`, `import`) record per-item completion and skip completed items on resume (`POST /api/v1/jobs/{id}/resume`).

## 3. Runners

| `JOB_RUNNER` | Behaviour |
|---|---|
| `local` (default) | In-process asyncio worker pool |
| `nebius` | For `learn`, `recalibrate` and `fidelity` only: write the inputs to Object Storage (`s3://$S3_BUCKET/jobs/<job_id>/input.json`, including a database export of the needed rows), submit a Nebius Serverless Job running the same image with `python -m keeper.jobs.remote --job <id>`, poll its status, then import the output (`output.json`) into the database. Other kinds always run locally. See [Deployment steps](../09-deployment/02-nebius-deployment-steps.md) §6. |

## 4. Events and SSE

Events are rows in `job_events` with an increasing integer ID. `GET /api/v1/jobs/{id}/events` is an SSE stream:
- sends all events after `Last-Event-ID` (or `?after=`) from the table, then live events from an in-process pub/sub (`asyncio.Queue` per subscriber);
- a heartbeat comment every 15 s;
- the stream closes after the terminal event (`job.completed`, `job.failed`, `job.cancelled`).

Because events are persisted, a browser refresh or reconnect resumes without loss. For `nebius` jobs, the remote job writes events into its output file in batches, and the poller replays them.

## 5. Event throttling

High-frequency events (`fix.test.output`, `job.log`) are coalesced to at most 4 per second per job. Text chunks are concatenated. The full log is stored in `.runtime/logs/jobs/<id>.log`, and is downloadable via `GET /api/v1/jobs/{id}/log`.
