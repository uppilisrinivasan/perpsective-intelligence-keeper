"""SQLAlchemy 2.0 models (docs/03-data/09-internal-data-model.md).

SQLite locally (WAL, foreign keys on), PostgreSQL in the cloud. IDs are prefixed ULIDs; GitHub IDs are `gh_id`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class UTCDateTime(TypeDecorator):
    """Timezone-aware UTC datetimes on every backend (SQLite drops tzinfo otherwise)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        return value if value.tzinfo else value.replace(tzinfo=UTC)


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON, datetime: UTCDateTime}


# ----------------------------------------------------------------------------------------------- source tables
class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner: Mapped[str] = mapped_column(String)
    repo: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String, default="demo")  # demo | imported
    fictional: Mapped[bool] = mapped_column(Boolean, default=False)
    default_branch: Mapped[str] = mapped_column(String, default="main")
    primary_maintainer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    demo_now: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    repo_path: Mapped[str | None] = mapped_column(String, nullable=True)
    mirror_path: Mapped[str | None] = mapped_column(String, nullable=True)
    html_base: Mapped[str | None] = mapped_column(String, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class Person(Base):
    __tablename__ = "people"
    __table_args__ = (UniqueConstraint("project_id", "gh_id"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    gh_id: Mapped[int] = mapped_column(BigInteger)
    login: Mapped[str] = mapped_column(String)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    type: Mapped[str] = mapped_column(String, default="User")
    role: Mapped[str] = mapped_column(String, default="contributor")
    first_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class Pull(Base):
    __tablename__ = "pulls"
    __table_args__ = (UniqueConstraint("project_id", "number"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    gh_id: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String)
    draft: Mapped[bool] = mapped_column(Boolean, default=False)
    author_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    author_association: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    merged_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    merged_by_id: Mapped[str | None] = mapped_column(String, nullable=True)
    merge_commit_sha: Mapped[str | None] = mapped_column(String, nullable=True)
    head_sha: Mapped[str] = mapped_column(String)
    head_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    base_sha: Mapped[str | None] = mapped_column(String, nullable=True)
    base_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    labels: Mapped[list[Any]] = mapped_column(JSON, default=list)
    additions: Mapped[int] = mapped_column(Integer, default=0)
    deletions: Mapped[int] = mapped_column(Integer, default=0)
    changed_files: Mapped[int] = mapped_column(Integer, default=0)
    split: Mapped[str | None] = mapped_column(String, nullable=True)  # train | holdout | live
    html_url: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_path: Mapped[str | None] = mapped_column(String, nullable=True)


class PullFile(Base):
    __tablename__ = "pull_files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pull_id: Mapped[str] = mapped_column(ForeignKey("pulls.id", ondelete="CASCADE"), index=True)
    head_sha: Mapped[str] = mapped_column(String)
    filename: Mapped[str] = mapped_column(String)
    previous_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String)
    additions: Mapped[int] = mapped_column(Integer, default=0)
    deletions: Mapped[int] = mapped_column(Integer, default=0)
    patch: Mapped[str | None] = mapped_column(Text, nullable=True)
    binary: Mapped[bool] = mapped_column(Boolean, default=False)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    pull_id: Mapped[str] = mapped_column(ForeignKey("pulls.id", ondelete="CASCADE"), index=True)
    gh_id: Mapped[int] = mapped_column(BigInteger, index=True)
    reviewer_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    state: Mapped[str] = mapped_column(String)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    commit_id: Mapped[str | None] = mapped_column(String, nullable=True)
    author_association: Mapped[str | None] = mapped_column(String, nullable=True)
    html_url: Mapped[str | None] = mapped_column(String, nullable=True)


class ReviewComment(Base):
    __tablename__ = "review_comments"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    pull_id: Mapped[str] = mapped_column(ForeignKey("pulls.id", ondelete="CASCADE"), index=True)
    gh_id: Mapped[int] = mapped_column(BigInteger, index=True)
    review_gh_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    in_reply_to_gh_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    author_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    path: Mapped[str | None] = mapped_column(String, nullable=True)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    side: Mapped[str | None] = mapped_column(String, nullable=True)
    start_side: Mapped[str | None] = mapped_column(String, nullable=True)
    original_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subject_type: Mapped[str | None] = mapped_column(String, nullable=True)
    diff_hunk: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text, default="")
    commit_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    html_url: Mapped[str | None] = mapped_column(String, nullable=True)


class IssueComment(Base):
    __tablename__ = "issue_comments"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    issue_number: Mapped[int] = mapped_column(Integer, index=True)
    gh_id: Mapped[int] = mapped_column(BigInteger, index=True)
    author_id: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    html_url: Mapped[str | None] = mapped_column(String, nullable=True)


class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (UniqueConstraint("project_id", "number"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    gh_id: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String)
    state_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    author_id: Mapped[str | None] = mapped_column(String, nullable=True)
    labels: Mapped[list[Any]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    is_pull: Mapped[bool] = mapped_column(Boolean, default=False)
    html_url: Mapped[str | None] = mapped_column(String, nullable=True)


class TimelineEvent(Base):
    __tablename__ = "timeline_events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    issue_number: Mapped[int] = mapped_column(Integer, index=True)
    event: Mapped[str] = mapped_column(String)
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    commit_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_issue_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Commit(Base):
    __tablename__ = "commits"
    sha: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    author_login: Mapped[str | None] = mapped_column(String, nullable=True)
    committer_login: Mapped[str | None] = mapped_column(String, nullable=True)
    authored_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    committed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")
    parents: Mapped[list[Any]] = mapped_column(JSON, default=list)
    pull_numbers: Mapped[list[Any]] = mapped_column(JSON, default=list)


class CheckRun(Base):
    __tablename__ = "check_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    head_sha: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    conclusion: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


# --------------------------------------------------------------------------------------------- analysis tables
class Ruler(Base):
    __tablename__ = "rulers"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    spec: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class FindingRow(Base):
    __tablename__ = "findings"
    __table_args__ = (Index("ix_findings_pr_source", "project_id", "pr_number", "source"),
                      Index("ix_findings_person_created", "person_id", "created_at"))
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    pr_number: Mapped[int] = mapped_column(Integer)
    head_sha: Mapped[str] = mapped_column(String, default="")
    source: Mapped[str] = mapped_column(String)
    person_id: Mapped[str | None] = mapped_column(String, nullable=True)
    ruler_id: Mapped[str | None] = mapped_column(String, nullable=True)
    lens_version_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    practice_answer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    scope: Mapped[str] = mapped_column(String, default="pr")
    path: Mapped[str | None] = mapped_column(String, nullable=True)
    side: Mapped[str] = mapped_column(String, default="RIGHT")
    start_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String, default="minor")
    kind: Mapped[str] = mapped_column(String, default="comment")
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    statement: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    substantive: Mapped[bool] = mapped_column(Boolean, default=True)
    confidence: Mapped[str | None] = mapped_column(String, nullable=True)
    refs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    llm_call_id: Mapped[str | None] = mapped_column(String, nullable=True)
    context: Mapped[str] = mapped_column(String, default="history")  # history | analysis | fidelity | practice
    origin: Mapped[str] = mapped_column(String, default="live")
    created_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class FindingMatch(Base):
    __tablename__ = "finding_matches"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    pr_number: Mapped[int] = mapped_column(Integer, index=True)
    set_a: Mapped[str] = mapped_column(String)
    set_b: Mapped[str] = mapped_column(String)
    a_id: Mapped[str] = mapped_column(String)
    b_id: Mapped[str] = mapped_column(String)
    decision: Mapped[str] = mapped_column(String)
    weight: Mapped[float] = mapped_column(Float, default=0)
    assigned: Mapped[bool] = mapped_column(Boolean, default=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_call_id: Mapped[str | None] = mapped_column(String, nullable=True)
    origin: Mapped[str] = mapped_column(String, default="live")


class ResidualSample(Base):
    __tablename__ = "residual_samples"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    finding_id: Mapped[str] = mapped_column(String, index=True)
    person_id: Mapped[str] = mapped_column(String, index=True)
    ruler_id: Mapped[str] = mapped_column(String, index=True)
    pr_number: Mapped[int] = mapped_column(Integer)
    klass: Mapped[str] = mapped_column("class", String)
    matched_finding_id: Mapped[str | None] = mapped_column(String, nullable=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    evidence: Mapped[str] = mapped_column(String, default="review")
    at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    origin: Mapped[str] = mapped_column(String, default="live")


class Outcome(Base):
    __tablename__ = "outcomes"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    pr_number: Mapped[int] = mapped_column(Integer, index=True)
    kind: Mapped[str] = mapped_column(String)
    at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    origin: Mapped[str] = mapped_column(String, default="live")


class OutcomeLink(Base):
    __tablename__ = "outcome_links"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    outcome_id: Mapped[str] = mapped_column(ForeignKey("outcomes.id", ondelete="CASCADE"), index=True)
    finding_id: Mapped[str] = mapped_column(String, index=True)
    overlap: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (UniqueConstraint("project_id", "pr_number", "head_sha", "ruler_id", "lens_version_id", "origin",
                                       "purpose"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    pr_number: Mapped[int] = mapped_column(Integer, index=True)
    head_sha: Mapped[str] = mapped_column(String)
    ruler_id: Mapped[str | None] = mapped_column(String, nullable=True)
    lens_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    purpose: Mapped[str] = mapped_column(String, default="queue")  # queue | fidelity | history
    status: Mapped[str] = mapped_column(String, default="ready")
    pr_lane: Mapped[str] = mapped_column(String)
    attention_minutes: Mapped[int] = mapped_column(Integer, default=1)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    slop_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    signals: Mapped[list[Any]] = mapped_column(JSON, default=list)
    reasons: Mapped[list[Any]] = mapped_column(JSON, default=list)
    recall_mode: Mapped[str | None] = mapped_column(String, nullable=True)
    stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    models: Mapped[list[Any]] = mapped_column(JSON, default=list)
    job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    origin: Mapped[str] = mapped_column(String, default="live")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class RoutedFindingRow(Base):
    __tablename__ = "routed_findings"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    finding_id: Mapped[str] = mapped_column(String)
    paired_finding_id: Mapped[str | None] = mapped_column(String, nullable=True)
    lane: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    fixable: Mapped[bool] = mapped_column(Boolean, default=False)
    blind_spot_item_id: Mapped[str | None] = mapped_column(String, nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    user_state: Mapped[str] = mapped_column(String, default="open")
    user_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_severity: Mapped[str | None] = mapped_column(String, nullable=True)


class Handoff(Base):
    __tablename__ = "handoffs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    candidates: Mapped[list[Any]] = mapped_column(JSON, default=list)
    target_person_id: Mapped[str | None] = mapped_column(String, nullable=True)
    note_md: Mapped[str] = mapped_column(Text, default="")
    checklist: Mapped[list[Any]] = mapped_column(JSON, default=list)
    osv: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    tavily: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    models: Mapped[list[Any]] = mapped_column(JSON, default=list)
    origin: Mapped[str] = mapped_column(String, default="live")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class ReviewDraft(Base):
    __tablename__ = "review_drafts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    body_md: Mapped[str] = mapped_column(Text, default="")
    comments: Mapped[list[Any]] = mapped_column(JSON, default=list)
    event: Mapped[str] = mapped_column(String, default="COMMENT")
    edited_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    models: Mapped[list[Any]] = mapped_column(JSON, default=list)
    origin: Mapped[str] = mapped_column(String, default="live")
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    pr_number: Mapped[int] = mapped_column(Integer)
    routed_finding_id: Mapped[str | None] = mapped_column(String, nullable=True)
    kind: Mapped[str] = mapped_column(String)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    lens_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    ruler_id: Mapped[str | None] = mapped_column(String, nullable=True)
    consumed_by_lens_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class FixRun(Base):
    __tablename__ = "fix_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    pr_number: Mapped[int] = mapped_column(Integer, index=True)
    analysis_id: Mapped[str | None] = mapped_column(String, nullable=True)
    finding_ids: Mapped[list[Any]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String, default="preparing")
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    winning_branch: Mapped[str | None] = mapped_column(String, nullable=True)
    diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    diff_stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    junit_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    baseline_failures: Mapped[list[Any]] = mapped_column(JSON, default=list)
    iterations: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0)
    models: Mapped[list[Any]] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    origin: Mapped[str] = mapped_column(String, default="live")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class FixAttempt(Base):
    __tablename__ = "fix_attempts"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    fix_run_id: Mapped[str] = mapped_column(ForeignKey("fix_runs.id", ondelete="CASCADE"), index=True)
    branch: Mapped[str] = mapped_column(String)
    iteration: Mapped[int] = mapped_column(Integer)
    step: Mapped[str] = mapped_column(String)  # plan | repair | verify
    llm_call_id: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    plan_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    edits: Mapped[list[Any]] = mapped_column(JSON, default=list)
    apply_errors: Mapped[list[Any]] = mapped_column(JSON, default=list)
    test_result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    log_path: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


# ------------------------------------------------------------------------------------------------- lens tables
class Consent(Base):
    __tablename__ = "consents"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    person_id: Mapped[str] = mapped_column(String, index=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    scope: Mapped[str] = mapped_column(String)  # build_lens | evaluation_only | share_in_project
    granted_by: Mapped[str] = mapped_column(String)
    granted_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    text_version: Mapped[str] = mapped_column(String, default="1")
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class Lens(Base):
    __tablename__ = "lenses"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    person_id: Mapped[str] = mapped_column(String, index=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="active")  # active | paused | revoked
    consent_id: Mapped[str] = mapped_column(ForeignKey("consents.id"))
    shared_in_project: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class LensVersion(Base):
    __tablename__ = "lens_versions"
    __table_args__ = (UniqueConstraint("lens_id", "version"),)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    lens_id: Mapped[str] = mapped_column(ForeignKey("lenses.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    cutoff_at: Mapped[datetime] = mapped_column(UTCDateTime)
    ruler_id: Mapped[str] = mapped_column(String)
    change_reason: Mapped[str] = mapped_column(String, default="initial_build")
    parent_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="building")
    card_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    card: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    digest: Mapped[str | None] = mapped_column(Text, nullable=True)
    digest_sha: Mapped[str | None] = mapped_column(String, nullable=True)
    style_hints: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    build_stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    models: Mapped[list[Any]] = mapped_column(JSON, default=list)
    job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    origin: Mapped[str] = mapped_column(String, default="live")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class LensItemRow(Base):
    __tablename__ = "lens_items"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    lens_version_id: Mapped[str] = mapped_column(ForeignKey("lens_versions.id", ondelete="CASCADE"), index=True)
    stable_key: Mapped[str] = mapped_column(String, index=True)
    type: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(Text)
    statement: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String)
    severity_typical: Mapped[str] = mapped_column(String, default="minor")
    triggers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String)
    owner_override: Mapped[str | None] = mapped_column(String, nullable=True)
    owner_edits: Mapped[list[Any]] = mapped_column(JSON, default=list)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class LensItemEvidence(Base):
    __tablename__ = "lens_item_evidence"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lens_item_id: Mapped[str] = mapped_column(ForeignKey("lens_items.id", ondelete="CASCADE"), index=True)
    finding_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    role: Mapped[str] = mapped_column(String)  # member | exemplar | counter_example


class BiasCheck(Base):
    __tablename__ = "bias_checks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lens_item_id: Mapped[str] = mapped_column(ForeignKey("lens_items.id", ondelete="CASCADE"), index=True)
    odds_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    ci_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    ci_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    n_by_group: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    outcome_check: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    verdict: Mapped[str] = mapped_column(String)


class EdgeMapCell(Base):
    __tablename__ = "edge_map_cells"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lens_version_id: Mapped[str] = mapped_column(ForeignKey("lens_versions.id", ondelete="CASCADE"), index=True)
    area: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    volume: Mapped[float] = mapped_column(Float, default=0)
    residual_rate: Mapped[float] = mapped_column(Float, default=0)
    shared_rate: Mapped[float] = mapped_column(Float, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0)
    speed_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    tests_present: Mapped[bool] = mapped_column(Boolean, default=False)
    value: Mapped[float] = mapped_column(Float, default=0)
    kind: Mapped[str] = mapped_column(String, default="cell")  # top | enough | gap | cell
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class GrowthSnapshot(Base):
    __tablename__ = "growth_snapshots"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    lens_id: Mapped[str] = mapped_column(String, index=True)
    period_start: Mapped[datetime] = mapped_column(UTCDateTime)
    period_end: Mapped[datetime] = mapped_column(UTCDateTime)
    measures: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    health_state: Mapped[str | None] = mapped_column(String, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin: Mapped[str] = mapped_column(String, default="live")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)
    actor_role: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    object_type: Mapped[str] = mapped_column(String)
    object_id: Mapped[str] = mapped_column(String, index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


# ------------------------------------------------------------------------------------- evaluation and growth
class FidelityRun(Base):
    __tablename__ = "fidelity_runs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    person_id: Mapped[str] = mapped_column(String)
    lens_version_id: Mapped[str] = mapped_column(String)
    ruler_id: Mapped[str] = mapped_column(String)
    holdout_spec: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String, default="running")
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    ci: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    passes: Mapped[dict[str, Any]] = mapped_column("pass", JSON, default=dict)
    falsifiers: Mapped[list[Any]] = mapped_column(JSON, default=list)
    sensitivity: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    measurement: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    batch_id: Mapped[str | None] = mapped_column(String, nullable=True)
    cost_usd: Mapped[float] = mapped_column(Float, default=0)
    models: Mapped[list[Any]] = mapped_column(JSON, default=list)
    job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    origin: Mapped[str] = mapped_column(String, default="live")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class FidelityCase(Base):
    __tablename__ = "fidelity_cases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("fidelity_runs.id", ondelete="CASCADE"), index=True)
    pr_number: Mapped[int] = mapped_column(Integer)
    per_system: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class PracticeSession(Base):
    __tablename__ = "practice_sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    learner_key: Mapped[str] = mapped_column(String, index=True)
    target_person_id: Mapped[str] = mapped_column(String)
    lens_version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    kind: Mapped[str] = mapped_column(String)  # before | learn | after | taste
    item_pr_numbers: Mapped[list[Any]] = mapped_column(JSON, default=list)
    current_index: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="open")
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    origin: Mapped[str] = mapped_column(String, default="live")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class PracticeAnswer(Base):
    __tablename__ = "practice_answers"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("practice_sessions.id", ondelete="CASCADE"), index=True)
    pr_number: Mapped[int] = mapped_column(Integer)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    notes: Mapped[list[Any]] = mapped_column(JSON, default=list)
    submitted_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)
    hints: Mapped[list[Any]] = mapped_column(JSON, default=list)
    feedback: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String, default="submitted")  # submitted | scored


# ------------------------------------------------------------------------------------------------- platform
class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, index=True)
    key: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String, default="queued")
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    progress: Mapped[float] = mapped_column(Float, default=0)
    step: Mapped[str | None] = mapped_column(String, nullable=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    runner: Mapped[str] = mapped_column(String, default="local")
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    cost_usd: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class JobEvent(Base):
    __tablename__ = "job_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class LLMCall(Base):
    __tablename__ = "llm_calls"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    role: Mapped[str] = mapped_column(String)
    model_id: Mapped[str] = mapped_column(String)
    provider: Mapped[str] = mapped_column(String, default="nebius")
    prompt_id: Mapped[str] = mapped_column(String)
    prompt_version: Mapped[int] = mapped_column(Integer)
    prompt_sha: Mapped[str] = mapped_column(String)
    request_hash: Mapped[str] = mapped_column(String)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    fallback_from: Mapped[str | None] = mapped_column(String, nullable=True)
    repaired: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String, default="ok")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    feature: Mapped[str] = mapped_column(String, default="other")
    origin: Mapped[str] = mapped_column(String, default="live")
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now, index=True)


class LLMCacheRow(Base):
    __tablename__ = "llm_cache"
    request_hash: Mapped[str] = mapped_column(String, primary_key=True)
    response: Mapped[dict[str, Any]] = mapped_column(JSON)
    model_id: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class ChatThread(Base):
    __tablename__ = "chat_threads"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, default="New chat")
    role: Mapped[str] = mapped_column(String, default="maintainer")
    project_id: Mapped[str | None] = mapped_column(String, nullable=True)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    origin: Mapped[str] = mapped_column(String, default="live")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("chat_threads.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String)  # user | assistant | tool
    content: Mapped[str] = mapped_column(Text, default="")
    tool_calls: Mapped[list[Any]] = mapped_column(JSON, default=list)
    tool_call_id: Mapped[str | None] = mapped_column(String, nullable=True)
    cards: Mapped[list[Any]] = mapped_column(JSON, default=list)
    tool_trace: Mapped[list[Any]] = mapped_column(JSON, default=list)
    llm_call_ids: Mapped[list[Any]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class SettingsOverride(Base):
    __tablename__ = "settings_overrides"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class SessionRow(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)
    ip_hash: Mapped[str | None] = mapped_column(String, nullable=True)


class AppState(Base):
    """Small key-value state: data manifest loaded, snapshot info, probe results."""

    __tablename__ = "app_state"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)
