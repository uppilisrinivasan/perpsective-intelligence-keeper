"""The LLM gateway: every model call in Keeper goes through `LLMGateway` (docs/04-architecture/03-llm-gateway.md).

It owns role → model resolution, the fallback chain and circuit breaker, prompt rendering and redaction, context
budgets, reasoning parameters, structured output with one repair re-ask, retries with backoff, rate limits and
concurrency, the cache, spend caps and the audit record.
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from keeper.config import get_config, get_settings
from keeper.core.errors import ModelOutputInvalid, ModelUnavailable, NoApiKey, RateLimited, SpendCapReached
from keeper.ids import new_id
from keeper.llm import cache, meter, probe
from keeper.llm.prompts import Prompt, Renderer, load_prompt
from keeper.llm.providers import FakeProvider, OpenAICompatibleProvider, ProviderError, ProviderResponse
from keeper.llm.schemas import load_schema, parse_json, validation_errors
from keeper.logging import get_logger

log = get_logger("keeper.llm")


@dataclass
class CallResult:
    data: Any
    text: str
    call_id: str
    prompt_id: str
    role: str
    model_id: str
    model_display: str
    latency_ms: int
    cost_usd: float
    cache_hit: bool
    fallback_from: str | None
    input_tokens: int = 0
    output_tokens: int = 0
    repaired: bool = False

    def meta(self) -> dict[str, Any]:
        return {"call_id": self.call_id, "model": self.model_id, "model_display": self.model_display,
                "latency_ms": self.latency_ms, "cost_usd": self.cost_usd, "cache_hit": self.cache_hit,
                "fallback_from": self.fallback_from, "role": self.role, "prompt_id": self.prompt_id}


@dataclass
class _Breaker:
    failures: deque[float] = field(default_factory=deque)
    open_until: float = 0.0


def estimate_tokens(text: str) -> int:
    te = get_config().models.get("token_estimate", {})
    cpt, safety = float(te.get("chars_per_token", 3.6)), float(te.get("safety", 1.1))
    return int(len(text) / cpt * safety) + 1


def make_provider() -> Any:
    s = get_settings()
    if s.LLM_PROVIDER == "fake":
        return FakeProvider(fixtures_dir=s.path("backend/tests/fixtures/llm"),
                            model_id=get_config().models.get("fake_model_id", "offline-simulator"))
    name = "nebius" if s.LLM_PROVIDER == "nebius" else "openai_compatible"
    return OpenAICompatibleProvider(base_url=s.base_url, api_key=s.api_key or "missing", timeout=s.LLM_TIMEOUT_SECONDS,
                                    name=name)


class LLMGateway:
    def __init__(self, provider: Any | None = None):
        self.settings = get_settings()
        self.cfg = get_config()
        self.provider = provider or make_provider()
        self.fake = isinstance(self.provider, FakeProvider)
        self._global = asyncio.Semaphore(max(1, self.settings.LLM_MAX_CONCURRENCY))
        self._roles: dict[str, asyncio.Semaphore] = {}
        self._breakers: dict[str, _Breaker] = {}
        self._calls: deque[float] = deque()
        self._rl_lock = asyncio.Lock()
        self.probe: dict[str, Any] = probe.load_cached()
        self.missing: set[str] = set()

    # ------------------------------------------------------------------ resolution
    @property
    def roles(self) -> dict[str, Any]:
        return self.cfg.models["roles"]

    def model_for(self, role: str) -> str:
        if self.fake:
            return str(self.cfg.models.get("fake_model_id", "offline-simulator"))
        return str(self.roles[role]["model"])

    def _usable(self, model_id: str) -> bool:
        if model_id in self.missing:
            return False
        st = self.probe.get("models", {}).get(model_id)
        if st and st.get("exists") == "missing":
            return False
        b = self._breakers.get(model_id)
        return not (b and b.open_until > time.time())

    def resolve(self, role: str, allow_fallback: bool = True) -> tuple[str, str, str | None]:
        """Return (role_used, model_id, fallback_from_model)."""
        primary = self.model_for(role)
        if self.fake or self._usable(primary):
            return role, primary, None
        if not allow_fallback:
            raise ModelUnavailable(f"{self.cfg.model_display(primary)} is unavailable and this step never falls "
                                   "back (the generic review is the pinned ruler).", {"role": role, "model": primary})
        for fb in self.roles[role].get("fallback", []) or []:
            mid = self.model_for(fb)
            if self._usable(mid):
                return fb, mid, primary
        raise ModelUnavailable(f"{self.cfg.model_display(primary)} isn't available right now, nor its fallbacks.",
                               {"role": role, "model": primary})

    def fallback_active(self) -> dict[str, str]:
        out = {}
        for role in self.roles:
            try:
                _, mid, fb = self.resolve(role)
                if fb:
                    out[role] = mid
            except ModelUnavailable:
                out[role] = ""
        return out

    def _sem(self, role: str) -> asyncio.Semaphore:
        if role not in self._roles:
            self._roles[role] = asyncio.Semaphore(int(self.roles.get(role, {}).get("max_concurrency", 4)))
        return self._roles[role]

    def _trip(self, model_id: str) -> None:
        br = self.cfg.models.get("probe", {}).get("breaker", {})
        b = self._breakers.setdefault(model_id, _Breaker())
        now = time.time()
        b.failures.append(now)
        while b.failures and now - b.failures[0] > float(br.get("window_seconds", 60)):
            b.failures.popleft()
        if len(b.failures) >= int(br.get("failures", 3)):
            b.open_until = now + float(br.get("half_open_seconds", 300))
            log.warning("circuit open for %s", model_id)

    # ------------------------------------------------------------------ parameters
    def _reasoning(self, model_id: str, level: str) -> dict[str, Any]:
        rp = self.cfg.models["reasoning_params"]
        st = self.probe.get("models", {}).get(model_id, {})
        family = "fallback" if st.get("reasoning") == "rejected" else "nemotron"
        params = dict(rp.get(family, {}).get(level, {}) or {})
        params.pop("max_reasoning_tokens", None)
        return params

    def _response_format(self, model_id: str, schema_name: str | None) -> dict[str, Any] | None:
        if not schema_name:
            return None
        st = self.probe.get("models", {}).get(model_id, {})
        if st.get("json_schema") == "supported":
            return {"type": "json_schema", "json_schema": {"name": schema_name, "schema": load_schema(schema_name),
                                                           "strict": False}}
        if st.get("json_object") == "rejected":
            return None
        return {"type": "json_object"}

    async def _rate_limit(self) -> None:
        rpm = self.settings.LLM_RATE_LIMIT_RPM
        if rpm <= 0 or self.fake:
            return
        async with self._rl_lock:
            now = time.time()
            while self._calls and now - self._calls[0] > 60:
                self._calls.popleft()
            if len(self._calls) >= rpm:
                await asyncio.sleep(60 - (now - self._calls[0]) + 0.05)
            self._calls.append(time.time())

    def _check_budget(self, model_id: str, in_tokens: int, max_out: int) -> None:
        if self.fake:
            return
        est = meter.cost(model_id, in_tokens, max_out)
        meter.check_spend(est)
        limit = self.settings.LLM_TOKENS_PER_DAY
        if limit > 0 and meter.tokens_today() + in_tokens + max_out > limit:
            raise SpendCapReached("Keeper reached its daily token limit.", {"tokens_per_day": limit, "kind": "tokens"})

    # ------------------------------------------------------------------ provider call with retries
    async def _send(self, *, role: str, model_id: str, messages: list[dict[str, Any]], params: dict[str, Any],
                    response_format: dict[str, Any] | None, prompt: Prompt, inputs: dict[str, Any],
                    request_hash: str) -> tuple[ProviderResponse, dict[str, Any] | None]:
        attempt = 0
        rf = response_format
        while True:
            await self._rate_limit()
            try:
                async with self._global, self._sem(role):
                    if self.fake:
                        resp = await self.provider.complete(model=model_id, messages=messages, params=params,
                                                            response_format=rf, prompt_id=prompt.id, inputs=inputs,
                                                            request_hash=request_hash)
                    else:
                        resp = await self.provider.complete(model=model_id, messages=messages, params=params,
                                                            response_format=rf, prompt_id=prompt.id, inputs=inputs)
                return resp, rf
            except ProviderError as e:
                if e.kind == "credits":
                    raise SpendCapReached("Spending limit reached at the provider (credits exhausted).",
                                          {"provider": True}) from e
                if e.kind == "missing_model":
                    self.missing.add(model_id)
                    raise
                if e.kind == "unsupported" and rf is not None:
                    rf = {"type": "json_object"} if rf.get("type") == "json_schema" else None
                    continue
                if e.kind in ("rate_limited", "server", "timeout") and attempt < self.settings.LLM_MAX_RETRIES:
                    attempt += 1
                    base = self.settings.LLM_RETRY_BASE_SECONDS * (2 ** (attempt - 1))
                    wait = e.retry_after if e.retry_after else random.uniform(0, base)
                    await asyncio.sleep(min(wait, 60))
                    continue
                if e.kind in ("server", "timeout"):
                    self._trip(model_id)
                if e.kind == "rate_limited":
                    raise RateLimited("The model provider is rate limiting requests.",
                                      {"retry_after": e.retry_after}) from e
                raise

    # ------------------------------------------------------------------ public API
    async def call(self, prompt_id: str, inputs: dict[str, Any], *, job_id: str | None = None,
                   feature: str = "other", temperature: float | None = None,
                   max_output_tokens: int | None = None) -> CallResult:
        if not self.settings.live:
            raise NoApiKey("This needs a Nemotron API key.", {"how": "Add NEBIUS_API_KEY to .env and restart."})
        prompt = load_prompt(prompt_id)
        renderer = Renderer()
        messages = renderer.render(prompt, inputs)
        max_out = max_output_tokens or prompt.max_output_tokens
        in_tokens = estimate_tokens("".join(m["content"] for m in messages))
        role_used, model_id, fallback_from = self._resolve_with_budget(prompt, in_tokens, max_out)
        params: dict[str, Any] = {"temperature": prompt.temperature if temperature is None else temperature,
                                  "top_p": prompt.top_p, "max_tokens": max_out}
        if prompt.seed is not None:
            params["seed"] = prompt.seed
        if not self.fake:
            params.update(self._reasoning(model_id, prompt.reasoning))
        rf = self._response_format(model_id, prompt.output_schema)
        h = cache.request_hash(model_id, prompt.sha256, messages, params)
        call_id = new_id("llm")
        use_cache = prompt.cache and self.settings.LLM_CACHE
        if use_cache and (hit := cache.get(h)) is not None:
            meter.record(dict(id=call_id, job_id=job_id, role=role_used, model_id=model_id, provider=self.provider.name,
                              prompt_id=prompt.id, prompt_version=prompt.version, prompt_sha=prompt.sha256,
                              request_hash=h, input_tokens=0, output_tokens=0, cost_usd=0.0, latency_ms=0,
                              cache_hit=True, fallback_from=fallback_from, feature=feature))
            return CallResult(data=hit.get("data"), text=hit.get("text", ""), call_id=call_id, prompt_id=prompt.id,
                              role=role_used, model_id=model_id, model_display=self.cfg.model_display(model_id),
                              latency_ms=0, cost_usd=0.0, cache_hit=True, fallback_from=fallback_from)
        self._check_budget(model_id, in_tokens, max_out)
        t0 = time.perf_counter()
        status, err = "ok", None
        resp: ProviderResponse | None = None
        data: Any = None
        repaired = False
        tokens_in = tokens_out = reasoning = 0
        try:
            try:
                resp, _ = await self._send(role=role_used, model_id=model_id, messages=messages, params=params,
                                           response_format=rf, prompt=prompt, inputs=inputs, request_hash=h)
            except ProviderError as e:
                if e.kind == "missing_model" and prompt.allow_fallback:
                    role_used, model_id, fallback_from = self.resolve(prompt.role, True)
                    resp, _ = await self._send(role=role_used, model_id=model_id, messages=messages, params=params,
                                               response_format=rf, prompt=prompt, inputs=inputs, request_hash=h)
                elif e.kind == "missing_model":
                    raise ModelUnavailable(f"{self.cfg.model_display(model_id)} isn't available right now.",
                                           {"model": model_id}) from e
                else:
                    raise ModelUnavailable(f"The model call failed: {e}", {"model": model_id, "kind": e.kind}) from e
            tokens_in, tokens_out, reasoning = resp.input_tokens, resp.output_tokens, resp.reasoning_tokens
            if prompt.output_schema:
                data, errors = self._parse(prompt.output_schema, resp.text)
                if errors:
                    repaired = True
                    fix_msgs = messages + [{"role": "assistant", "content": resp.text[:12000]},
                                           {"role": "user", "content": "Your output failed validation: "
                                            + "; ".join(errors) + ". Return corrected JSON only."}]
                    resp2, _ = await self._send(role=role_used, model_id=model_id, messages=fix_msgs, params=params,
                                                response_format=rf, prompt=prompt, inputs=inputs,
                                                request_hash=h + ":repair")
                    tokens_in += resp2.input_tokens
                    tokens_out += resp2.output_tokens
                    data, errors = self._parse(prompt.output_schema, resp2.text)
                    if errors:
                        raise ModelOutputInvalid("The model's answer didn't pass Keeper's checks.",
                                                 {"prompt": prompt.id, "errors": errors[:5]})
                    resp = resp2
            return_text = resp.text
        except Exception as e:
            status, err = "error", f"{type(e).__name__}: {str(e)[:300]}"
            raise
        finally:
            latency = int((time.perf_counter() - t0) * 1000)
            c = meter.cost(model_id, tokens_in, tokens_out, reasoning) if not self.fake else 0.0
            meter.record(dict(id=call_id, job_id=job_id, role=role_used, model_id=model_id, provider=self.provider.name,
                              prompt_id=prompt.id, prompt_version=prompt.version, prompt_sha=prompt.sha256,
                              request_hash=h, input_tokens=tokens_in, output_tokens=tokens_out,
                              reasoning_tokens=reasoning, cost_usd=c, latency_ms=latency, cache_hit=False,
                              fallback_from=fallback_from, repaired=repaired, status=status, error=err,
                              feature=feature))
            if self.settings.LLM_LOG_PROMPTS:
                self._log_prompt(call_id, messages, resp.text if resp else err)
        if use_cache:
            cache.put(h, model_id, {"data": data, "text": return_text})
        return CallResult(data=data, text=return_text, call_id=call_id, prompt_id=prompt.id, role=role_used,
                          model_id=model_id, model_display=self.cfg.model_display(model_id), latency_ms=latency,
                          cost_usd=c, cache_hit=False, fallback_from=fallback_from, input_tokens=tokens_in,
                          output_tokens=tokens_out, repaired=repaired)

    def _resolve_with_budget(self, prompt: Prompt, in_tokens: int, max_out: int) -> tuple[str, str, str | None]:
        role_used, model_id, fallback_from = self.resolve(prompt.role, prompt.allow_fallback)
        ctx = int(self.roles.get(role_used, {}).get("context_tokens", 128000))
        if in_tokens + max_out > ctx:
            from keeper.core.errors import ValidationFailed
            raise ValidationFailed(f"The input for {prompt.id} is too large for {self.cfg.model_display(model_id)}.",
                                   {"tokens": in_tokens, "context": ctx})
        return role_used, model_id, fallback_from

    @staticmethod
    def _parse(schema_name: str, text: str) -> tuple[Any, list[str]]:
        try:
            data = parse_json(text)
        except (json.JSONDecodeError, ValueError) as e:
            return None, [f"not valid JSON ({e})"]
        return data, validation_errors(schema_name, data)

    def _log_prompt(self, call_id: str, messages: list[dict[str, Any]], response: Any) -> None:
        d = self.settings.runtime_dir / "logs" / "llm"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{call_id}.json").write_text(json.dumps({"messages": messages, "response": response}, indent=1))

    async def stream_chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], *,
                          job_id: str | None = None, feature: str = "ask", inputs: dict[str, Any] | None = None,
                          prompt_id: str = "assistant_system") -> AsyncIterator[dict[str, Any]]:
        """Streaming chat with tools (the assistant only). Yields text, tool_call_done, usage and finish items."""
        if not self.settings.live:
            raise NoApiKey("Ask needs a Nemotron API key.")
        prompt = load_prompt(prompt_id)
        role_used, model_id, fallback_from = self.resolve("assistant", True)
        in_tokens = estimate_tokens("".join(str(m.get("content") or "") for m in messages))
        self._check_budget(model_id, in_tokens, prompt.max_output_tokens)
        params: dict[str, Any] = {"temperature": prompt.temperature, "top_p": prompt.top_p,
                                  "max_tokens": prompt.max_output_tokens}
        if not self.fake:
            params.update(self._reasoning(model_id, prompt.reasoning))
        st = self.probe.get("models", {}).get(model_id, {})
        use_tools = tools if st.get("tools") not in ("rejected", "ignored") else []
        await self._rate_limit()
        t0 = time.perf_counter()
        usage = {"input_tokens": in_tokens, "output_tokens": 0}
        text_len = 0
        status, err = "ok", None
        try:
            async with self._global, self._sem(role_used):
                async for item in self.provider.stream(model=model_id, messages=messages, params=params,
                                                       tools=use_tools, inputs=inputs):
                    if item["type"] == "usage":
                        usage = {"input_tokens": item["input_tokens"], "output_tokens": item["output_tokens"]}
                        continue
                    if item["type"] == "text":
                        text_len += len(item["text"])
                    yield item
        except ProviderError as e:
            status, err = "error", str(e)[:300]
            if e.kind == "credits":
                raise SpendCapReached("Spending limit reached at the provider (credits exhausted).") from e
            raise ModelUnavailable(f"The assistant model call failed: {e}", {"model": model_id}) from e
        finally:
            if not usage["output_tokens"]:
                usage["output_tokens"] = text_len // 4
            c = meter.cost(model_id, usage["input_tokens"], usage["output_tokens"]) if not self.fake else 0.0
            meter.record(dict(id=new_id("llm"), job_id=job_id, role=role_used, model_id=model_id,
                              provider=self.provider.name, prompt_id=prompt.id, prompt_version=prompt.version,
                              prompt_sha=prompt.sha256, request_hash="stream", input_tokens=usage["input_tokens"],
                              output_tokens=usage["output_tokens"], cost_usd=c,
                              latency_ms=int((time.perf_counter() - t0) * 1000), cache_hit=False,
                              fallback_from=fallback_from, status=status, error=err, feature=feature))
            yield {"type": "usage", "model": model_id, "model_display": self.cfg.model_display(model_id),
                   "cost_usd": c, **usage}

    async def run_probe(self) -> dict[str, Any]:
        if self.fake:
            mid = self.model_for("fast")
            res = {"models": {mid: {"exists": "available", "chat": "ok", "json_schema": "supported",
                                    "json_object": "supported", "reasoning": "accepted", "tools": "supported"}}}
        elif not self.settings.live:
            return {"models": {}}
        else:
            res = await probe.run_probe(self.provider)
        self.probe = res
        self.missing = {m for m, st in res.get("models", {}).items() if st.get("exists") == "missing"}
        return res


_gateway: LLMGateway | None = None


def get_gateway() -> LLMGateway:
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway


def set_gateway(gw: LLMGateway | None) -> None:
    global _gateway
    _gateway = gw
