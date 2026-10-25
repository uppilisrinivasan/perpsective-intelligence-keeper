"""Pure domain types shared by every layer (the interface between pipelines; docs/02-methodology/01)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Source = Literal["human", "baseline", "lens", "learner"]
Scope = Literal["line", "file", "pr"]
Side = Literal["RIGHT", "LEFT"]
Severity = Literal["blocker", "major", "minor", "nit"]
Lane = Literal["shared", "edge", "blind_spot", "unknown"]
RouteLane = Literal["shared", "edge", "blind_spot", "baseline_only"]
Decision = Literal["match", "partial", "none"]
Confidence = Literal["high", "medium", "low"]
ItemType = Literal["edge", "blind_spot", "shared_ground"]
ItemStatus = Literal["validated", "candidate", "bias_suspected", "retired", "disabled_by_owner"]
ResidualClass = Literal["shared", "r_plus", "r_minus"]
OutcomeKind = Literal["merged", "closed_unmerged", "reverted", "post_merge_bug", "follow_up_fix", "ci_failed"]
HealthState = Literal["healthy", "absorbed", "self_caricature", "deskilling", "replaced", "insufficient_data"]

LANE_ORDER: tuple[str, ...] = ("unknown", "edge", "blind_spot", "shared")
BAD_OUTCOMES = ("reverted", "post_merge_bug", "follow_up_fix")


class Anchor(BaseModel):
    scope: Scope = "pr"
    path: str | None = None
    side: Side = "RIGHT"
    start_line: int | None = None
    end_line: int | None = None

    def span(self, pad: int = 0) -> tuple[int, int] | None:
        if self.scope != "line" or self.start_line is None:
            return None
        end = self.end_line if self.end_line is not None else self.start_line
        return (self.start_line - pad, end + pad)


class Finding(BaseModel):
    """One noticed thing. All four sources produce this shape, so they can be matched."""

    id: str
    project_id: str = ""
    pr_number: int
    head_sha: str = ""
    source: Source
    person_id: str | None = None
    anchor: Anchor = Field(default_factory=Anchor)
    category: str
    severity: Severity = "minor"
    kind: str = "comment"
    statement: str
    rationale: str | None = None
    suggestion: str | None = None
    substantive: bool = True
    confidence: Confidence | None = None
    refs: dict[str, Any] = Field(default_factory=dict)
    llm_call_id: str | None = None
    created_at: datetime | None = None


class MatchPair(BaseModel):
    a_id: str
    b_id: str
    decision: Decision
    weight: float
    rationale: str = ""


class Matching(BaseModel):
    """A one-to-one matching of finding set A against set B, partitioned (methodology 04 §2)."""

    pairs: list[MatchPair] = Field(default_factory=list)
    shared_a: list[str] = Field(default_factory=list)
    shared_b: list[str] = Field(default_factory=list)
    r_plus: list[str] = Field(default_factory=list)   # A not assigned
    r_minus: list[str] = Field(default_factory=list)  # B not assigned
    judged: list[MatchPair] = Field(default_factory=list)  # every judged candidate pair (for audit and κ)

    def matched_weight(self) -> float:
        return sum(p.weight for p in self.pairs)

    def partner_of_a(self, a_id: str) -> MatchPair | None:
        return next((p for p in self.pairs if p.a_id == a_id), None)

    def partner_of_b(self, b_id: str) -> MatchPair | None:
        return next((p for p in self.pairs if p.b_id == b_id), None)


class Triggers(BaseModel):
    paths: list[str] = Field(default_factory=list)
    code_patterns: list[str] = Field(default_factory=list)
    pr_features: dict[str, Any] = Field(default_factory=dict)


class LensItem(BaseModel):
    id: str
    lens_version_id: str = ""
    stable_key: str = ""
    type: ItemType = "edge"
    title: str
    statement: str
    rationale: str = ""
    category: str
    severity_typical: Severity = "minor"
    triggers: Triggers = Field(default_factory=Triggers)
    stats: dict[str, Any] = Field(default_factory=dict)
    status: ItemStatus = "candidate"
    owner_override: str | None = None
    member_ids: list[str] = Field(default_factory=list)
    exemplar_ids: list[str] = Field(default_factory=list)
    counter_example_prs: list[int] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class RiskSignal(BaseModel):
    key: str
    label: str
    severity: Literal["high", "medium", "low"]
    paths: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    covered: bool = False
    covered_by: list[str] = Field(default_factory=list)  # lens item ids


class RoutedFinding(BaseModel):
    finding_id: str
    paired_finding_id: str | None = None
    lane: RouteLane
    action: str
    fixable: bool = False
    blind_spot_item_id: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class FileChange(BaseModel):
    path: str
    status: str = "modified"
    previous_path: str | None = None
    patch: str | None = None
    additions: int = 0
    deletions: int = 0
    binary: bool = False


class PRContext(BaseModel):
    """What both the baseline and the lens review see (methodology 01 §1). No author login, no reviews."""

    repo: str
    number: int
    title: str
    labels: list[str] = Field(default_factory=list)
    base_ref: str = "main"
    author_association: str | None = None
    draft: bool = False
    description: str = ""
    files: list[FileChange] = Field(default_factory=list)
    diff_text: str = ""
    ci: list[dict[str, Any]] = Field(default_factory=list)
    repo_notes: str = ""
    created_at: datetime | None = None
    head_sha: str = ""
    changed_lines: int = 0
    added_lines: dict[str, list[tuple[int, str]]] = Field(default_factory=dict)  # path -> [(new_line, text)]
    removed_lines: dict[str, list[tuple[int, str]]] = Field(default_factory=dict)  # path -> [(old_line, text)]
    hunks: dict[str, list[tuple[int, int]]] = Field(default_factory=dict)  # path -> [(new_start, new_end)]
