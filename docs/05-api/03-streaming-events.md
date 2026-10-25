# Streaming events (SSE)

Two kinds of streams exist:
1. **Job streams:** `GET /api/v1/jobs/{id}/events`. These are persisted and resumable.
2. **Chat answers:** the response body of `POST /api/v1/chat/threads/{tid}/messages`. These are live; the finished message is persisted.

## 1. Wire format

```
id: 1042
event: fix.test.result
data: {"job_id":"job_…","at":"2026-10-25T10:12:03Z","branch":"A","passed":118,"failed":1,"duration_ms":8412}

: heartbeat
```

- `event` is the type; `data` is one line of JSON, always with `job_id` (job streams) and `at`.
- The client uses `EventSource` for job streams (GET, auto-reconnect with `Last-Event-ID`) and `fetch` plus a ReadableStream parser for chat (POST). The parser is shared (`frontend/src/api/sse.ts`).

## 2. Common job events

| Event | Data |
|---|---|
| `job.queued` | `{kind, params}` |
| `job.started` | `{kind, runner}` |
| `job.step` | `{step, label, index, total}`, where `label` is user-facing ("Reading the maintainer's past reviews") |
| `job.progress` | `{progress, done, total}` |
| `job.log` | `{level, message}` (coalesced) |
| `job.cost` | `{cost_usd, calls}` (cumulative, at most every 2 s) |
| `job.warning` | `{code, message}`, for example `fallback_model`, `sandbox_fallback`, `batch_partial` |
| `job.completed` | `{result}` (terminal) |
| `job.failed` | `{error: {code, message, details}}` (terminal) |
| `job.cancelled` | `{}` (terminal) |

## 3. Kind-specific events

| Kind | Events |
|---|---|
| `analyze` and `triage` | `analysis.step {pr_number, stage: "context"|"baseline"|"lens_recall"|"lens_review"|"match"|"route"|"triage"|"draft"}`, `analysis.updated {pr_number, analysis_id, lane, attention_minutes}` |
| `fix` | `fix.started {finding_ids, branches}`, `fix.sandbox.ready {provider}`, `fix.tests.baseline {passed, failed}`, `fix.plan {branch, plan, model, latency_ms}`, `fix.apply {branch, ok, errors[]}`, `fix.test.output {branch, chunk}`, `fix.test.result {branch, passed, failed, duration_ms}`, `fix.repair {branch, iteration, model}`, `fix.verify {branch, addresses_finding}`, `fix.completed {status, winning_branch, diff_stats}` |
| `learn`, `lens_update` and `recalibrate` | `lens.stage {stage: "findings"|"baseline"|"residual"|"cluster"|"items"|"calibrate"|"bias"|"card"|"edge_map", done, total}`, `lens.version.ready {lens_id, version}` |
| `fidelity` | `fidelity.case {pr_number, done, total}`, `fidelity.batch {submitted, completed, failed}`, `fidelity.metrics {metrics}`, `fidelity.falsifier {name, pass}` |
| `import` | `import.fetch {resource, pages, rate_remaining}`, `import.wait {seconds, reason: "rate_limit"}` |
| `handoff` | `handoff.osv {packages, vulns}`, `handoff.ready {target}` |
| `practice_score` | `practice.scored {item, score}` |

## 4. Chat events

| Event | Data |
|---|---|
| `chat.message.created` | `{user_message_id, assistant_message_id}` |
| `chat.tool_step` | `{call_id, name, label, status: "running"|"done"|"error", duration_ms?}`, where `label` is user-facing ("Looking at PR #412") |
| `chat.delta` | `{text}` |
| `chat.card` | `{card}` (see [Assistant](../04-architecture/06-assistant.md) §3) |
| `chat.done` | `{usage: {input_tokens, output_tokens}, cost_usd, model}` |
| `chat.error` | `{code, message}` |

Markers `[[pull:412]]` in deltas are passed through. The client renders them as placeholders until the matching `chat.card` arrives; unresolved markers are removed on `chat.done`.

## 5. Client behaviour

- **Job streams:** on `job.completed`, invalidate the related TanStack Query keys (a table in [Frontend integration](04-frontend-integration.md) §4).
- Reconnect with backoff on network errors (EventSource does this; for fetch streams, show "Connection lost. Retry"). Chat answers are not resumed; the persisted message is fetched instead.
- No stream ever carries secrets or full prompts.
