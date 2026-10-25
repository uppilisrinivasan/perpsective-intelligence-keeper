# API conventions

## 1. Basics

- Base path: `/api/v1`. JSON (UTF-8) in and out; `snake_case` field names.
- The OpenAPI document is at `/api/v1/openapi.json` and the docs UI at `/api/docs` (enabled locally; disabled in cloud mode unless `API_DOCS=true`).
- Times are ISO 8601 UTC with `Z`. Money is a number in USD with 4 decimals (`cost_usd`). Durations end in `_ms` or `_seconds`.
- IDs are opaque strings with a type prefix (`keeper.ids`): `prj_`, `per_`, `ana_`, `fnd_`, `rf_`, `lns_`, `lv_`, `li_`, `job_`, `fix_`, `fid_`, `prs_` (practice session), `thr_`, `msg_`. PRs are addressed by `number` within a project.
- The project is in the path (`/projects/{project_id}/…`). The frontend gets the default project from `GET /api/v1/status` (`default_project_id`).

## 2. Common query parameters

| Parameter | Meaning |
|---|---|
| `limit` (default 50, max 200), `cursor` | Cursor pagination. Responses carry `next_cursor` (null at the end). |
| `as_of` | Read data as of a timestamp (default: `demo_now` in demo mode, otherwise now). Only on read endpoints that support it. |
| `origin` | `live`, `snapshot` or `any` (default `any`, preferring live) |
| `role` | The viewer role (`maintainer`, `contributor`). Also settable via the `X-Keeper-Role` header from the role picker. |

## 3. Envelopes

Single objects and lists are returned directly (no wrapping `data` key). Lists are `{ "items": [...], "next_cursor": null, "total": 12 }`.

Every response carrying derived results includes provenance:

```json
"provenance": {
  "origin": "snapshot",
  "computed_at": "2026-10-19T07:41:12Z",
  "ruler_id": "rul_3f9c…",
  "lens_version": 2,
  "models": ["nvidia/nemotron-3-super-120b-a12b"]
}
```

The UI uses `origin` for the "Saved run" badge.

## 4. Errors

```json
{
  "error": {
    "code": "confirmation_required",
    "message": "This will cost about $0.03. Confirm to continue.",
    "details": { "estimate_usd": 0.031, "confirm_token": "cfm_…" },
    "request_id": "req_…"
  }
}
```

| HTTP | `code` | When |
|---|---|---|
| 400 | `validation_failed` | Invalid input (details list the fields) |
| 401 | `auth_required` | Cloud mode, no session |
| 403 | `forbidden` / `consent_required` | Role not allowed / lens needs consent |
| 404 | `not_found` | — |
| 409 | `conflict` / `ruler_mismatch` / `job_in_progress` | State conflicts (details include an existing `job_id`) |
| 402 | `confirmation_required` | The action's estimate exceeds auto-approve; resend with `confirm_token` |
| 402 | `spend_cap_reached` | The cap is reached (details: cap, period, resets_at) |
| 422 | `model_output_invalid` | The model output failed validation after repair |
| 429 | `rate_limited` | With `Retry-After` |
| 503 | `model_unavailable` / `sandbox_unavailable` / `no_api_key` | Dependencies missing (details explain how to fix) |

`402` for confirmations is deliberate: the client treats it as "needs the user's go-ahead", distinct from 4xx validation errors.

## 5. Actions and jobs

Any request that calls a model, runs code or takes more than about 1 s returns **`202 Accepted`** with a job:

```json
{ "job": { "id": "job_…", "kind": "fix", "status": "queued", "events_url": "/api/v1/jobs/job_…/events" } }
```

Confirmation flow: the first request returns `402 confirmation_required` with `confirm_token` (valid 10 minutes, bound to the parameters). The client shows the estimate and resends the same body with `"confirm_token": "cfm_…"`. Actions estimated at or below `KEEPER_AUTO_APPROVE_USD` skip this.

Idempotency: action endpoints accept `Idempotency-Key`; repeats within 10 minutes return the same job.

## 6. Headers

| Header | Direction | Use |
|---|---|---|
| `X-Request-ID` | both | Correlation; generated if absent; included in logs |
| `X-Keeper-Role` | request | The viewer role |
| `X-Keeper-CSRF` | request | Cloud mode only, for state-changing methods |
| `Retry-After` | response | With 429 and 503 |
| `Last-Event-ID` | request | SSE resume |

## 7. Versioning

Breaking changes go to `/api/v2`. Additive fields are allowed in v1. The frontend is built against the generated types, so a contract test (`backend/tests/api/test_openapi_snapshot.py`) catches accidental changes.
