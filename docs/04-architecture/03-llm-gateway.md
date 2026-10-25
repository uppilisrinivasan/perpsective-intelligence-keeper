# LLM gateway

Every model call in Keeper goes through `keeper.llm.gateway.LLMGateway`. No other module imports an LLM SDK. The gateway owns: role → model resolution, the fallback chain, prompt rendering, redaction, context budgets, provider parameters (reasoning, sampling), structured output, retries, rate limits, concurrency, caching, the meter and spend caps, batch submission, and the audit record.

## 1. Providers

| `LLM_PROVIDER` | Implementation | Use |
|---|---|---|
| `nebius` (default) | `OpenAICompatibleProvider(base_url=NEBIUS_BASE_URL, api_key=NEBIUS_API_KEY)` | NVIDIA Nemotron on Token Factory (the competition requirement) |
| `openai_compatible` | the same class, with `LLM_BASE_URL` and `LLM_API_KEY` | For example a self-hosted Nemotron on a Nebius Serverless Endpoint (vLLM) |
| `fake` | `FakeProvider` with fixtures from `backend/tests/fixtures/llm/` keyed by prompt ID and an input hash, with deterministic defaults | Offline tests and CI |

## 2. Roles and models (`config/models.yaml`)

```yaml
roles:
  fast:
    model: ${KEEPER_MODEL_FAST:-nvidia/Nemotron-3_5-Lightning}
    display: "Nemotron 3.5 Lightning"
    context_tokens: 1024000
    max_concurrency: 8
    fallback: [judge]
    reasoning_family: nemotron
  judge:
    model: ${KEEPER_MODEL_JUDGE:-nvidia/nemotron-3-super-120b-a12b}
    display: "Nemotron 3 Super"
    context_tokens: 262144
    max_concurrency: 6
    fallback: [deep]
    reasoning_family: nemotron
  deep:
    model: ${KEEPER_MODEL_DEEP:-nvidia/Nemotron-3-Ultra-550b-a55b}
    display: "Nemotron 3 Ultra"
    context_tokens: 1024000
    max_concurrency: 3
    fallback: [judge]
    reasoning_family: nemotron
  assistant:
    model: ${KEEPER_MODEL_ASSISTANT:-${KEEPER_MODEL_JUDGE}}
    display_from: judge
    tools: true
    fallback: [fast]

reasoning_params:                   # how off|low|on map to request parameters [verify with the probe]
  nemotron:
    off: {extra_body: {chat_template_kwargs: {enable_thinking: false}}}
    low: {extra_body: {chat_template_kwargs: {enable_thinking: true}}, max_reasoning_tokens: 1024}
    on:  {extra_body: {chat_template_kwargs: {enable_thinking: true}}}
  fallback:                         # used if the probe finds chat_template_kwargs rejected
    off: {}
    low: {reasoning_effort: "low"}
    on:  {reasoning_effort: "high"}
```

The `${VAR:-default}` expansion is done by `keeper.config` (not the shell). A prompt's `role` selects the model; a prompt's `allow_fallback: false` disables the chain (the baseline).

## 3. The capability probe

At startup (in the background, non-blocking) and on `./run.sh --check`, the gateway probes each distinct model ID:

| Probe | Request | Result |
|---|---|---|
| `exists` | `GET /v1/models` and look up the ID | `available` or `missing` |
| `chat` | A 5-token prompt | `ok` or the error code |
| `json_schema` | A tiny prompt with `response_format: {type: "json_schema", json_schema: {name, schema, strict: true}}` | `supported`, `rejected` (4xx) or `ignored` (invalid JSON returned) |
| `json_object` | The same with `{type: "json_object"}` | as above |
| `reasoning_off` | The `off` parameters | `accepted` or `rejected` (then try `fallback`) |
| `tools` (assistant role only) | A one-tool call | `supported` or not |

Results are cached in `.runtime/cache/probe.json` for 24 hours and shown in Settings and `GET /api/v1/status`. Token Factory's documentation describes `json_schema`, while parts of its API reference mention only `json_object` and `text`, so the probe settles this per model at runtime instead of assuming either.

## 4. Fallback chain

On `missing`, or on repeated `5xx` or timeouts (≥ 3 within 60 s, a circuit breaker), the role resolves to the first available role in `fallback`. The UI and `llm_calls.fallback_from` record it ("Used Nemotron 3 Super because Nemotron 3 Ultra was unavailable"). The breaker half-opens after 5 minutes. `402` (credits exhausted) never falls back; it raises `SpendCapReached(provider)`.

## 5. One call, step by step

```
call(prompt_id, inputs, *, job, feature) ->
  1. load prompt (front matter + template), render with inputs (StrictUndefined)
  2. redact (keeper.llm.redact): secret-shaped strings, emails, high-entropy tokens → «REDACTED:kind»
  3. budget: count tokens (tiktoken cl100k as an estimator × 1.1 safety); if > role context − max_output → trim per prompt's
     trim policy (declared in front matter: which input lists to shorten first) or raise ValidationFailed
  4. resolve role → model (probe + breaker + fallback)
  5. cache lookup: request_hash = sha256(model_id, prompt_sha, rendered messages, params); hit → return
  6. spend check: estimated cost = in_tokens × price_in + max_output × price_out; refuse if caps would be exceeded
  7. rate limit: token bucket per process (LLM_RATE_LIMIT_RPM) + daily token counter (LLM_TOKENS_PER_DAY); per-role semaphore
  8. request: chat.completions.create(model, messages, temperature, top_p, seed, max_tokens, response_format (best supported), **reasoning params)
  9. retry: 429 (honour Retry-After), 500/502/503/504, timeouts → exponential backoff with full jitter, base LLM_RETRY_BASE_SECONDS, ≤ LLM_MAX_RETRIES
 10. parse: strip reasoning content (reasoning_content field or <think>…</think>) → JSON parse → schema validate
     invalid → one repair call: same messages + assistant output + "Your output failed validation: <errors>. Return corrected JSON only."
 11. meter: write llm_calls row (tokens from usage; cost from config/pricing.yaml), update spend
 12. cache store; return typed result (pydantic model generated from the JSON Schema)
```

Streaming (`stream_chat`) is used only by the assistant. It yields `text`, `tool_call_delta`, `tool_call_done`, `usage` and `finish` items.

## 6. Spend caps and limits

| Variable | Meaning |
|---|---|
| `KEEPER_SPEND_CAP_USD` with `KEEPER_SPEND_CAP_PERIOD` (`day`, `month`, `total`) | A hard cap. Calls that would exceed it raise `SpendCapReached`; the UI shows a banner. |
| `KEEPER_AUTO_APPROVE_USD` | Actions estimated below this run without a confirmation |
| `LLM_TOKENS_PER_DAY` | A daily token ceiling (0 = none) |
| `LLM_RATE_LIMIT_RPM` | Requests per minute |
| `LLM_MAX_CONCURRENCY` | Global concurrent calls (per-role limits also apply) |

Costs come from `config/pricing.yaml` (per model ID, USD per 1M input and output tokens). Unknown models are priced at the most expensive configured price, so they are never free by accident.

## 7. Batch API (`keeper.llm.batch`)

When `BATCH_API_ENABLED=true` and a job submits ≥ `batch.min_requests` (20) requests for batchable prompts (`lens_review`, `lens_recall`, `baseline_review`, `calibration_notes`):
1. Write a JSONL of OpenAI-format batch lines (`{"custom_id", "method": "POST", "url": "/v1/chat/completions", "body": {…}}`).
2. Upload with `files.create(purpose="batch")`, then `batches.create(input_file_id, endpoint="/v1/chat/completions", completion_window="24h")` [verify the parameters against the Token Factory batch docs].
3. Poll `batches.retrieve` every `batch.poll_seconds`; on completion, download the output file and pass each line through steps 10–12. Lines that failed are retried online.
The job shows "Waiting for batch (12/40 done)". Batch pricing is read from `config/pricing.yaml` `batch_discount` if Token Factory publishes one; otherwise the full price.

## 8. Redaction (`keeper.llm.redact`)

Patterns (`config/redaction.yaml`): AWS keys, GitHub tokens (`gh[pousr]_…`), Slack tokens, JWTs, PEM blocks, `password=`/`secret=`/`token=` assignments, e-mail addresses, and any 32+ character high-entropy token. Replacements are stable per value within a call (`«SECRET_1»`), so the model can still refer to them. Redaction runs on all untrusted inputs. Code text is otherwise sent as-is: the code is public, or synthetic in the demo.

## 9. Audit

Each call's `llm_calls` row stores metadata only (no prompt text) unless `LLM_LOG_PROMPTS=true` (dev only), which writes prompts and responses to `.runtime/logs/llm/` (git-ignored).
