# Frontend integration

## 1. Types from OpenAPI

- The backend exports OpenAPI with `python -m keeper.app.export_openapi > frontend/src/api/openapi.json` (run by `./run.sh` and in CI).
- `openapi-typescript` generates `frontend/src/api/schema.d.ts`. `openapi-fetch` provides a typed client (`frontend/src/api/client.ts`).
- CI fails if the generated files are stale (`npm run api:check`).
- SSE event payloads are declared as pydantic models in `keeper.app.events` and exported into OpenAPI `components.schemas` (as `JobEvent*` and `ChatEvent*`), so they are typed too.

## 2. Client setup

`frontend/src/api/client.ts`:
- base URL `/api/v1` (same origin; Vite proxies in dev);
- adds `X-Keeper-Role` from the role store, `X-Request-ID`, and `X-Keeper-CSRF` in cloud mode (read from the cookie);
- maps error envelopes to `ApiError {code, message, details, status}`;
- `402 confirmation_required` is surfaced to `useConfirmableAction` (below), never as a red error.

## 3. Hooks

| Hook | Wraps | Notes |
|---|---|---|
| `useStatus()` | `GET /status` | Polled every 60 s; drives the live/saved badge, banners and disabled states |
| `useQueue(filters)` | `GET /projects/{pid}/queue` | `staleTime` 30 s |
| `usePull(n)`, `useAnalysis(n)`, `useCompare(n)`, `useReviewDraft(n)` | PR endpoints | Prefetched on queue-row hover and focus |
| `useLens(lid)`, `useLensVersion(lid, v)`, `useLensItems(...)`, `useLensDiff(...)`, `useEdgeMap(...)`, `useGrowth(lid)` | Lens endpoints | |
| `useFidelityRuns()`, `useFidelityRun(id)` | Proof endpoints | |
| `usePracticeSession(id)` | Practice endpoints | |
| `useJob(id)` | `GET /jobs/{id}` + the event stream | Returns `{job, events, step, progress, cost, done, error}`; one EventSource per job, shared by reference counting |
| `useConfirmableAction(mutationFn)` | Any action endpoint | Runs the mutation; on `402 confirmation_required`, opens `ConfirmCostDialog` with the estimate; on confirm, re-runs with `confirm_token`; returns the job and starts `useJob` |
| `useChat(threadId)` | Chat endpoints + the POST stream | Exposes `send(text, context)`, `stop()`, and the streaming message state (text, steps, cards) |
| `useSettings()`, `useUsage(period)` | Settings endpoints | |

## 4. Cache invalidation on job completion

| Job kind | Invalidate |
|---|---|
| `triage` and `analyze` | `queue`, `pull/{n}/*` for the affected numbers |
| `fix` | `pull/{n}/fixes`, `queue` |
| `handoff` | `pull/{n}/handoff`, `queue` |
| `learn`, `lens_update`, `recalibrate` | `lens/*`, `queue` (attention may change), `tour` |
| `fidelity` | `fidelity/*`, `tour` |
| `practice_score` | `practice/*` |
| `import` | `projects`, `status` |

Feedback mutations (`PATCH findings`) use optimistic updates and roll back on error.

## 5. Routes and deep links

| Route | Screen |
|---|---|
| `/` | Redirects to `/queue` |
| `/queue?lane=&q=` | Queue |
| `/pr/:number?view=diff|compare&finding=:id&file=` | Pull request |
| `/pr/:number/fix/:fixId` | PR with the fix panel open |
| `/ask` and `/ask/:threadId` | Ask |
| `/lens?person=&v=&tab=card|items|map|versions|growth|controls&item=` | Lens |
| `/proof?run=&case=` | Proof |
| `/practice` and `/practice/:sessionId/:index` | Practice |
| `/settings?tab=` | Settings |
| `/signin` | Cloud mode only |

The project is implicit (the default project in the status). If more than one project exists, a project switcher sets `?project=` across routes.

## 6. Development proxy

`frontend/vite.config.ts` proxies `/api` to `http://127.0.0.1:${APP_PORT}` (read from the root `.env` via `loadEnv`, no hardcoded port). SSE needs no special proxy options beyond disabling buffering (`proxy[...].configure` sets `x-accel-buffering: no`).
