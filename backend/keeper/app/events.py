"""SSE event payload models, exported into OpenAPI components so the frontend's event types are generated too
(docs/05-api/03-streaming-events.md)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class JobEventBase(BaseModel):
    job_id: str
    at: str


class JobEventStep(JobEventBase):
    step: str
    label: str
    index: int
    total: int


class JobEventProgress(JobEventBase):
    progress: float
    done: int
    total: int


class JobEventLog(JobEventBase):
    level: str
    message: str


class JobEventCost(JobEventBase):
    cost_usd: float
    calls: int


class JobEventWarning(JobEventBase):
    code: str
    message: str


class JobEventCompleted(JobEventBase):
    result: dict[str, Any] = Field(default_factory=dict)


class JobEventFailed(JobEventBase):
    error: dict[str, Any]


class JobEventAnalysisStep(JobEventBase):
    pr_number: int
    stage: Literal["context", "baseline", "lens_recall", "lens_review", "match", "route", "triage", "draft"]


class JobEventAnalysisUpdated(JobEventBase):
    pr_number: int
    analysis_id: str
    lane: str
    attention_minutes: int


class JobEventFix(JobEventBase):
    branch: str | None = None
    plan: str | None = None
    model: str | None = None
    model_display: str | None = None
    latency_ms: int | None = None
    ok: bool | None = None
    errors: list[str] | None = None
    chunk: str | None = None
    passed: int | None = None
    failed: int | None = None
    duration_ms: int | None = None
    iteration: int | None = None
    addresses_finding: bool | None = None
    provider: str | None = None
    status: str | None = None
    winning_branch: str | None = None
    diff_stats: dict[str, int] | None = None
    finding_ids: list[str] | None = None
    branches: int | None = None
    explanation: str | None = None


class JobEventLensStage(JobEventBase):
    stage: str
    done: int
    total: int


class JobEventFidelityCase(JobEventBase):
    pr_number: int
    done: int
    total: int


class ChatEventToolStep(BaseModel):
    call_id: str
    name: str
    label: str
    status: Literal["running", "done", "error"]
    duration_ms: int | None = None


class ChatEventDelta(BaseModel):
    text: str


class ChatEventCard(BaseModel):
    card: dict[str, Any]


class ChatEventDone(BaseModel):
    usage: dict[str, int]
    cost_usd: float
    model: str | None = None
    model_display: str | None = None
    message_id: str | None = None
    suggestions: list[str] = Field(default_factory=list)
    dropped_markers: int = 0


class ChatEventError(BaseModel):
    code: str
    message: str


_MODELS = [JobEventStep, JobEventProgress, JobEventLog, JobEventCost, JobEventWarning, JobEventCompleted,
           JobEventFailed, JobEventAnalysisStep, JobEventAnalysisUpdated, JobEventFix, JobEventLensStage,
           JobEventFidelityCase, ChatEventToolStep, ChatEventDelta, ChatEventCard, ChatEventDone, ChatEventError]


def event_schemas() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for m in _MODELS:
        s = m.model_json_schema(ref_template="#/components/schemas/{model}")
        out.update(s.pop("$defs", {}))
        out[m.__name__] = s
    return out
