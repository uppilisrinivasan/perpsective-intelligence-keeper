"""Model providers. Only this module imports the `openai` SDK (import contract).

- `OpenAICompatibleProvider`: NVIDIA Nemotron on Nebius Token Factory (or any OpenAI-compatible endpoint).
- `FakeProvider`: offline. Recorded fixtures win; otherwise a deterministic simulator per prompt
  (keeper.llm.simulate) produces a meaningful, schema-valid answer from the same inputs the prompt shows.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ProviderResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str | None = None


class ProviderError(Exception):
    def __init__(self, message: str, *, status: int | None = None, retry_after: float | None = None,
                 kind: str = "error"):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after
        self.kind = kind  # error | rate_limited | credits | missing_model | unsupported | timeout | server


class OpenAICompatibleProvider:
    name = "nebius"

    def __init__(self, base_url: str, api_key: str, timeout: float, name: str = "nebius"):
        from openai import AsyncOpenAI

        self.name = name
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=0)

    @staticmethod
    def _map(e: Exception) -> ProviderError:
        import openai

        status = getattr(e, "status_code", None)
        retry_after = None
        resp = getattr(e, "response", None)
        if resp is not None:
            try:
                ra = resp.headers.get("retry-after")
                retry_after = float(ra) if ra else None
            except Exception:
                retry_after = None
        msg = str(e)[:500]
        if isinstance(e, openai.APITimeoutError):
            return ProviderError(msg, kind="timeout")
        if isinstance(e, openai.APIConnectionError):
            return ProviderError(msg, kind="server")
        if status == 402:
            return ProviderError(msg, status=402, kind="credits")
        if status == 429:
            return ProviderError(msg, status=429, retry_after=retry_after, kind="rate_limited")
        if status == 404 or (status == 400 and "model" in msg.lower() and "not" in msg.lower()):
            return ProviderError(msg, status=status, kind="missing_model")
        if status is not None and status >= 500:
            return ProviderError(msg, status=status, kind="server")
        if status in (400, 422):
            return ProviderError(msg, status=status, kind="unsupported")
        return ProviderError(msg, status=status)

    async def complete(self, *, model: str, messages: list[dict[str, Any]], params: dict[str, Any],
                       response_format: dict[str, Any] | None, tools: list[dict[str, Any]] | None = None,
                       prompt_id: str = "", inputs: dict[str, Any] | None = None) -> ProviderResponse:
        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        for k in ("temperature", "top_p", "seed", "max_tokens"):
            if params.get(k) is not None:
                kwargs[k] = params[k]
        if params.get("extra_body"):
            kwargs["extra_body"] = params["extra_body"]
        if params.get("reasoning_effort"):
            kwargs["reasoning_effort"] = params["reasoning_effort"]
        if response_format:
            kwargs["response_format"] = response_format
        if tools:
            kwargs["tools"] = tools
        try:
            r = await self.client.chat.completions.create(**kwargs)
        except Exception as e:  # noqa: BLE001
            raise self._map(e) from e
        choice = r.choices[0]
        msg = choice.message
        text = msg.content or ""
        calls = []
        for tc in msg.tool_calls or []:
            calls.append({"id": tc.id, "name": tc.function.name, "arguments": tc.function.arguments})
        usage = r.usage
        reasoning = 0
        if usage is not None and getattr(usage, "completion_tokens_details", None):
            reasoning = getattr(usage.completion_tokens_details, "reasoning_tokens", 0) or 0
        return ProviderResponse(text=text, input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                                output_tokens=getattr(usage, "completion_tokens", 0) or 0, reasoning_tokens=reasoning,
                                tool_calls=calls, finish_reason=choice.finish_reason)

    async def stream(self, *, model: str, messages: list[dict[str, Any]], params: dict[str, Any],
                     tools: list[dict[str, Any]] | None = None, inputs: dict[str, Any] | None = None
                     ) -> AsyncIterator[dict[str, Any]]:
        kwargs: dict[str, Any] = {"model": model, "messages": messages, "stream": True,
                                  "stream_options": {"include_usage": True}}
        for k in ("temperature", "top_p", "max_tokens"):
            if params.get(k) is not None:
                kwargs[k] = params[k]
        if params.get("extra_body"):
            kwargs["extra_body"] = params["extra_body"]
        if tools:
            kwargs["tools"] = tools
        try:
            stream = await self.client.chat.completions.create(**kwargs)
            calls: dict[int, dict[str, Any]] = {}
            in_think = False
            async for chunk in stream:
                if chunk.usage:
                    yield {"type": "usage", "input_tokens": chunk.usage.prompt_tokens,
                           "output_tokens": chunk.usage.completion_tokens}
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    text = delta.content
                    if "<think>" in text:
                        in_think = True
                    if in_think:
                        if "</think>" in text:
                            in_think = False
                            text = text.split("</think>", 1)[1]
                        else:
                            continue
                    if text:
                        yield {"type": "text", "text": text}
                for tc in delta.tool_calls or []:
                    c = calls.setdefault(tc.index, {"id": tc.id, "name": "", "arguments": ""})
                    if tc.id:
                        c["id"] = tc.id
                    if tc.function and tc.function.name:
                        c["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        c["arguments"] += tc.function.arguments
                if chunk.choices[0].finish_reason:
                    for c in calls.values():
                        yield {"type": "tool_call_done", **c}
                    yield {"type": "finish", "reason": chunk.choices[0].finish_reason}
        except Exception as e:  # noqa: BLE001
            raise self._map(e) from e

    async def list_models(self) -> list[str]:
        try:
            page = await self.client.models.list()
            return [m.id for m in page.data]
        except Exception as e:  # noqa: BLE001
            raise self._map(e) from e

    # ---- Batch API (OpenAI-compatible) [verify parameters against the Token Factory batch docs]
    async def batch_submit(self, jsonl: bytes) -> str:
        try:
            f = await self.client.files.create(file=("batch.jsonl", jsonl), purpose="batch")
            b = await self.client.batches.create(input_file_id=f.id, endpoint="/v1/chat/completions",
                                                 completion_window="24h")
            return b.id
        except Exception as e:  # noqa: BLE001
            raise self._map(e) from e

    async def batch_status(self, batch_id: str) -> dict[str, Any]:
        b = await self.client.batches.retrieve(batch_id)
        counts = getattr(b, "request_counts", None)
        return {"status": b.status, "output_file_id": b.output_file_id,
                "completed": getattr(counts, "completed", 0) if counts else 0,
                "failed": getattr(counts, "failed", 0) if counts else 0,
                "total": getattr(counts, "total", 0) if counts else 0}

    async def batch_output(self, file_id: str) -> str:
        content = await self.client.files.content(file_id)
        return content.text


class FakeProvider:
    """Offline provider for tests, CI and no-key development (`LLM_PROVIDER=fake`)."""

    name = "fake"

    def __init__(self, fixtures_dir: Path, model_id: str):
        self.fixtures_dir = fixtures_dir
        self.model_id = model_id

    def _fixture(self, prompt_id: str, request_hash: str | None) -> dict[str, Any] | None:
        if not request_hash:
            return None
        f = self.fixtures_dir / prompt_id / f"{request_hash[:16]}.json"
        if f.exists():
            return json.loads(f.read_text())
        return None

    async def complete(self, *, model: str, messages: list[dict[str, Any]], params: dict[str, Any],
                       response_format: dict[str, Any] | None, tools: list[dict[str, Any]] | None = None,
                       prompt_id: str = "", inputs: dict[str, Any] | None = None,
                       request_hash: str | None = None) -> ProviderResponse:
        from keeper.llm import simulate

        fx = self._fixture(prompt_id, request_hash)
        if fx is not None:
            text = fx["response"] if isinstance(fx["response"], str) else json.dumps(fx["response"])
        else:
            out = simulate.run(prompt_id, inputs or {}, messages=messages, params=params, tools=tools)
            if isinstance(out, ProviderResponse):
                return out
            text = out if isinstance(out, str) else json.dumps(out)
        n_in = sum(len(m.get("content") or "") for m in messages) // 4
        return ProviderResponse(text=text, input_tokens=n_in, output_tokens=len(text) // 4, finish_reason="stop")

    async def stream(self, *, model: str, messages: list[dict[str, Any]], params: dict[str, Any],
                     tools: list[dict[str, Any]] | None = None, inputs: dict[str, Any] | None = None
                     ) -> AsyncIterator[dict[str, Any]]:
        from keeper.llm import simulate

        r = simulate.assistant(messages, tools or [], inputs or {})
        if r.tool_calls:
            for c in r.tool_calls:
                yield {"type": "tool_call_done", **c}
            yield {"type": "finish", "reason": "tool_calls"}
            return
        words = r.text.split(" ")
        for i, w in enumerate(words):
            yield {"type": "text", "text": w + (" " if i < len(words) - 1 else "")}
        yield {"type": "usage", "input_tokens": sum(len(m.get("content") or "") for m in messages) // 4,
               "output_tokens": len(r.text) // 4}
        yield {"type": "finish", "reason": "stop"}

    async def list_models(self) -> list[str]:
        return [self.model_id]
