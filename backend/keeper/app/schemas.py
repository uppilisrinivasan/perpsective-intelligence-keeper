"""API request and response models (docs/05-api/02-endpoints.md). The OpenAPI document — and through it the
frontend's TypeScript types — is generated from these, so they are the contract between backend and frontend."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Lane = Literal["shared", "edge", "blind_spot", "unknown"]
RouteLane = Literal["shared", "edge", "blind_spot", "baseline_only"]
Origin = Literal["live", "snapshot"]


class Provenance(BaseModel):
    origin: Origin = "live"
    computed_at: datetime | None = None
    ruler_id: str | None = None
    lens_version: int | None = None
    models: list[str] = Field(default_factory=list)
    model_displays: list[str] = Field(default_factory=list)
    simulated: bool = False


class Page(BaseModel):
    next_cursor: str | None = None
    total: int = 0


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class JobRef(BaseModel):
    id: str
    kind: str
    status: str
    events_url: str
    existing: bool = False


class JobAccepted(BaseModel):
    job: JobRef


class ActionRequest(BaseModel):
    confirm_token: str | None = None


# ---------------------------------------------------------------------------------------------------- system
class Health(BaseModel):
    status: Literal["ok"] = "ok"
    version: str


class ProbeResult(BaseModel):
    exists: str = "unknown"
    chat: str = "unknown"
    json_schema: str = "unknown"
    json_object: str = "unknown"
    reasoning: str = "unknown"
    tools: str = "n/a"


class ModelStatus(BaseModel):
    role: str
    model_id: str
    display: str
    purpose: str
    probe: ProbeResult
    fallback_active: bool = False
    fallback_model: str | None = None


class SandboxStatus(BaseModel):
    provider: str
    requested: str
    reason: str | None = None
    isolation: str


class SpendStatus(BaseModel):
    used_usd: float
    cap_usd: float
    period: str
    resets_at: str | None = None
    reached: bool = False


class DataStatus(BaseModel):
    manifest_sha: str | None = None
    loaded_at: datetime | None = None
    snapshot: bool = False
    snapshot_created_at: datetime | None = None
    snapshot_simulated: bool = False
    snapshot_models: list[str] = Field(default_factory=list)
    loading: bool = False
    load_job_id: str | None = None
    error: str | None = None


class Status(BaseModel):
    mode: Literal["demo", "workspace"]
    provider: str
    live: bool
    simulated: bool = False
    reason_if_not_live: str | None = None
    auth_mode: str = "none"
    default_project_id: str | None = None
    demo_now: datetime | None = None
    models: list[ModelStatus]
    sandbox: SandboxStatus
    spend: SpendStatus
    data: DataStatus
    estimates: dict[str, float] = Field(default_factory=dict)
    auto_approve_usd: float = 0.05
    batch_enabled: bool = False
    import_allowed: bool = True
    version: str


class TourTarget(BaseModel):
    kind: str
    id: str | None = None


class TourStep(BaseModel):
    id: str
    title: str
    body_md: str
    route: str
    target: TourTarget
    reason: str


class Tour(BaseModel):
    steps: list[TourStep]


class GlossaryTerm(BaseModel):
    key: str
    label: str
    short: str
    long_md: str


class Glossary(BaseModel):
    terms: list[GlossaryTerm]


# ------------------------------------------------------------------------------------------ projects, people
class PersonRef(BaseModel):
    id: str
    login: str
    display_name: str | None = None
    role: str = "contributor"


class ProjectCounts(BaseModel):
    pulls: int = 0
    open: int = 0
    reviewers: int = 0


class ProjectSummary(BaseModel):
    id: str
    owner: str
    repo: str
    kind: str
    fictional: bool
    counts: ProjectCounts
    primary_maintainer: PersonRef | None = None


class ProjectList(BaseModel):
    items: list[ProjectSummary]


class ProjectDetail(ProjectSummary):
    demo_now: datetime | None = None
    policy_files: list[str] = Field(default_factory=list)
    ruler_id: str | None = None
    learner: PersonRef | None = None
    html_base: str | None = None


class ImportRequest(BaseModel):
    repo_url: str
    maintainer_login: str | None = None
    since: str | None = None
    max_pulls: int | None = None
    consent_ack: bool = False
    confirm_token: str | None = None


class PersonStats(BaseModel):
    reviews: int = 0
    comments: int = 0
    prs: int = 0


class PersonSummary(BaseModel):
    id: str
    login: str
    display_name: str | None = None
    role: str
    has_lens: bool = False
    lens_id: str | None = None
    lens_status: str | None = None
    fictional: bool = False
    stats: PersonStats = Field(default_factory=PersonStats)


class PeopleList(BaseModel):
    items: list[PersonSummary]


class ConsentInfo(BaseModel):
    id: str
    scope: str
    granted_by: str
    granted_at: datetime
    revoked_at: datetime | None = None
    text_version: str
    synthetic: bool


class PersonDetail(PersonSummary):
    consents: list[ConsentInfo] = Field(default_factory=list)


class ConsentRequest(BaseModel):
    scope: Literal["build_lens", "evaluation_only", "share_in_project"]
    attest: bool = False
    typed_login: str | None = None


# ----------------------------------------------------------------------------------------------------- queue
class AuthorRef(BaseModel):
    id: str | None = None
    login: str
    display_name: str | None = None
    association: str | None = None
    first_time: bool = False


class Reason(BaseModel):
    kind: str
    label: str
    detail: str | None = None


class SignalRef(BaseModel):
    key: str
    label: str
    severity: str = "medium"
    covered: bool = False
    paths: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class LaneCounts(BaseModel):
    edge: int = 0
    blind_spot: int = 0
    shared: int = 0
    baseline_only: int = 0


class SlopInfo(BaseModel):
    score: float
    label: str | None = None
    evidence: list[str] = Field(default_factory=list)


class FixRef(BaseModel):
    status: str
    run_id: str


class HandoffRef(BaseModel):
    person_id: str | None = None
    login: str | None = None
    display_name: str | None = None


class QueueRow(BaseModel):
    number: int
    title: str
    author: AuthorRef
    lane: Lane
    summary: str | None = None
    reasons: list[Reason]
    signals: list[SignalRef]
    attention_minutes: int
    counts: LaneCounts
    slop: SlopInfo | None = None
    fix: FixRef | None = None
    handoff: HandoffRef | None = None
    status: str = "analysed"
    areas: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None
    created_at: datetime | None = None
    head_sha: str
    analysis_id: str | None = None
    provenance: Provenance


class ByLane(BaseModel):
    shared: int = 0
    edge: int = 0
    blind_spot: int = 0
    unknown: int = 0


class AttentionByLane(BaseModel):
    shared: int = 0
    edge: int = 0
    blind_spot: int = 0
    unknown: int = 0


class QueueSummary(BaseModel):
    by_lane: ByLane
    attention_by_lane: AttentionByLane
    attention_minutes_total: int
    budget_minutes: int
    over_budget: bool
    need_count: int
    total: int
    naive_minutes: int
    handoff_suggestion: int | None = None


class QueueResponse(BaseModel):
    items: list[QueueRow]
    summary: QueueSummary
    provenance: Provenance
    maintainer: PersonRef | None = None


class QueueRefreshRequest(BaseModel):
    numbers: list[int] | None = None
    confirm_token: str | None = None


class Card(BaseModel):
    type: Literal["pull", "finding", "comment", "lens_item", "metric", "action"]
    data: dict[str, Any]


class QueueDigest(BaseModel):
    markdown: str
    cards: list[Card]


# ---------------------------------------------------------------------------------------------- pull request
class PullFileInfo(BaseModel):
    filename: str
    status: str
    additions: int
    deletions: int
    binary: bool = False


class CheckInfo(BaseModel):
    name: str
    conclusion: str | None = None
    summary: str | None = None


class PullDetail(BaseModel):
    number: int
    title: str
    body_md: str
    author: AuthorRef
    state: str
    merged: bool = False
    labels: list[str]
    base: str
    head: str
    head_sha: str
    created_at: datetime
    closed_at: datetime | None = None
    merged_at: datetime | None = None
    files: list[PullFileInfo]
    checks: list[CheckInfo]
    additions: int
    deletions: int
    commits: int
    html_url: str | None = None
    split: str | None = None
    has_human_review: bool = False


class DiffFile(BaseModel):
    filename: str
    status: str
    patch: str | None = None
    binary: bool = False
    too_large: bool = False


class DiffResponse(BaseModel):
    files: list[DiffFile]


class AnchorOut(BaseModel):
    scope: str
    path: str | None = None
    side: str = "RIGHT"
    start_line: int | None = None
    end_line: int | None = None


class LensItemRef(BaseModel):
    id: str
    title: str
    status: str | None = None
    support: int | None = None


class PastComment(BaseModel):
    id: str
    pr_number: int
    excerpt: str
    path: str | None = None
    at: datetime | None = None
    author: str | None = None
    html_url: str | None = None


class BaselinePair(BaseModel):
    finding_id: str
    statement: str
    decision: str | None = None


class BlindSpotEvidence(BaseModel):
    id: str
    title: str
    bad_outcomes: int = 0
    ignored: int = 0
    outcome_prs: list[int] = Field(default_factory=list)


class FindingEvidence(BaseModel):
    lens_items: list[LensItemRef] = Field(default_factory=list)
    past_comments: list[PastComment] = Field(default_factory=list)
    baseline_pair: BaselinePair | None = None
    blind_spot_item: BlindSpotEvidence | None = None
    signals: list[str] = Field(default_factory=list)
    why_similar: str | None = None
    tool: str | None = None


class ModelTag(BaseModel):
    model_id: str | None = None
    display: str | None = None
    latency_ms: int | None = None


class RoutedFindingOut(BaseModel):
    id: str
    finding_id: str
    lane: RouteLane
    action: str
    source: Literal["lens", "baseline", "both"]
    title: str
    statement_md: str
    rationale_md: str | None = None
    suggestion_md: str | None = None
    category: str
    category_label: str
    severity: str
    kind: str
    anchor: AnchorOut
    confidence: Literal["high", "medium", "low"] | None = None
    fixable: bool
    evidence: FindingEvidence
    model: ModelTag | None = None
    user_state: str
    user_text: str | None = None
    user_severity: str | None = None


class AnalysisResponse(BaseModel):
    analysis_id: str
    pr_number: int
    lane: Lane
    summary_md: str | None = None
    attention_minutes: int
    signals: list[SignalRef]
    reasons: list[Reason]
    slop: SlopInfo | None = None
    recall_mode: str | None = None
    findings: list[RoutedFindingOut]
    baseline_only_count: int
    stats: dict[str, Any] = Field(default_factory=dict)
    lens_version: int | None = None
    lens_paused: bool = False
    baseline_unavailable: bool = False
    provenance: Provenance


class AnalyzeRequest(BaseModel):
    confirm_token: str | None = None


class FindingOut(BaseModel):
    id: str
    source: str
    person: str | None = None
    title: str
    statement: str
    category: str
    category_label: str
    severity: str
    kind: str
    anchor: AnchorOut
    confidence: str | None = None
    substantive: bool = True
    lens_item_ids: list[str] = Field(default_factory=list)
    exemplar_ids: list[str] = Field(default_factory=list)
    html_url: str | None = None
    created_at: datetime | None = None


class ComparePair(BaseModel):
    baseline_id: str
    lens_id: str
    decision: str
    rationale: str | None = None


class HumanPair(BaseModel):
    human_id: str
    other_id: str
    system: Literal["baseline", "lens"]
    decision: str


class CompareResidual(BaseModel):
    r_plus: list[str] = Field(default_factory=list)
    r_minus: list[str] = Field(default_factory=list)


class CompareResponse(BaseModel):
    pr_number: int
    baseline: list[FindingOut]
    lens: list[FindingOut]
    pairs: list[ComparePair]
    residual: CompareResidual
    human: list[FindingOut] | None = None
    human_pairs: list[HumanPair] = Field(default_factory=list)
    maintainer: PersonRef | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    provenance: Provenance


class HistoryItem(BaseModel):
    comment_id: str
    pr_number: int
    path: str | None = None
    excerpt: str
    at: datetime | None = None
    html_url: str | None = None
    category: str | None = None


class HistoryResponse(BaseModel):
    items: list[HistoryItem]


class HumanReviewComment(BaseModel):
    id: str
    kind: str
    path: str | None = None
    line: int | None = None
    body_md: str
    author: str
    at: datetime | None = None
    html_url: str | None = None


class HumanReviewResponse(BaseModel):
    pr_number: int
    person: PersonRef | None = None
    comments: list[HumanReviewComment]
    findings: list[FindingOut]


class FeedbackRequest(BaseModel):
    state: Literal["accepted", "edited", "dismissed", "good_catch", "open"]
    text: str | None = None
    severity: str | None = None
    reason: str | None = None


class NoteRequest(BaseModel):
    path: str | None = None
    line: int | None = None
    text: str
    category: str | None = None


class LaneOverrideRequest(BaseModel):
    lane: Lane
    reason: str | None = None


class LaneOverrideResponse(BaseModel):
    lane: Lane
    blocked: bool = False
    message: str | None = None


class DraftComment(BaseModel):
    path: str
    line: int
    side: str = "RIGHT"
    body_md: str
    finding_id: str | None = None


class ReviewDraftOut(BaseModel):
    body_md: str
    comments: list[DraftComment]
    event: Literal["COMMENT", "REQUEST_CHANGES", "APPROVE"]
    edited_by_user: bool
    label: str
    header: str
    updated_at: datetime | None = None
    provenance: Provenance


class ReviewDraftUpdate(BaseModel):
    body_md: str
    comments: list[DraftComment] = Field(default_factory=list)


class ReviewDraftExport(BaseModel):
    format: Literal["md", "github_json"]
    content: str
    filename: str
    gh_command: str | None = None


class HandoffCandidate(BaseModel):
    person: PersonRef
    score: float
    competence: float
    distance: float | None = None
    why: list[str]


class OsvVuln(BaseModel):
    id: str
    summary: str | None = None
    aliases: list[str] = Field(default_factory=list)
    url: str | None = None


class OsvPackage(BaseModel):
    name: str
    version: str | None = None
    vulns: list[OsvVuln] = Field(default_factory=list)
    error: str | None = None


class TavilyResult(BaseModel):
    title: str
    url: str
    snippet: str | None = None


class HandoffOut(BaseModel):
    candidates: list[HandoffCandidate]
    target: PersonRef | None = None
    note_md: str
    checklist: list[str]
    signals: list[SignalRef]
    osv: list[OsvPackage] = Field(default_factory=list)
    osv_status: str = "not_needed"
    tavily: list[TavilyResult] = Field(default_factory=list)
    tavily_status: str = "not_configured"
    no_candidate_message: str | None = None
    model: ModelTag | None = None
    provenance: Provenance


class OutcomeOut(BaseModel):
    kind: str
    at: datetime | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class OutcomesResponse(BaseModel):
    items: list[OutcomeOut]


# ----------------------------------------------------------------------------------------------------- fixes
class FixRequest(BaseModel):
    finding_ids: list[str]
    branches: int | None = None
    user_hint: str | None = None
    both_ways: bool = False
    confirm_token: str | None = None


class TestFailure(BaseModel):
    test: str
    message: str


class TestResult(BaseModel):
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_ms: int = 0
    failures: list[TestFailure] = Field(default_factory=list)
    lint_errors: int = 0
    ok: bool = False


class FixAttemptOut(BaseModel):
    iteration: int
    step: str
    plan_md: str | None = None
    edits: list[dict[str, Any]] = Field(default_factory=list)
    apply_errors: list[str] = Field(default_factory=list)
    test: TestResult | None = None
    verify: dict[str, Any] | None = None
    model: ModelTag | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class FixBranchOut(BaseModel):
    name: str
    status: str
    approach: str | None = None
    attempts: list[FixAttemptOut]
    diff: str | None = None
    diff_stats: dict[str, int] = Field(default_factory=dict)


class FixRunSummary(BaseModel):
    id: str
    status: str
    finding_ids: list[str]
    provider: str | None = None
    winning_branch: str | None = None
    iterations: int
    diff_stats: dict[str, int] = Field(default_factory=dict)
    junit_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    finished_at: datetime | None = None
    job_id: str | None = None
    provenance: Provenance


class FixRunList(BaseModel):
    items: list[FixRunSummary]


class FixRunDetail(FixRunSummary):
    pr_number: int
    provider_reason: str | None = None
    isolation: str | None = None
    baseline_tests: TestResult | None = None
    baseline_failures: list[str] = Field(default_factory=list)
    branches: list[FixBranchOut]
    diff: str | None = None
    cost_usd: float = 0
    error: str | None = None
    suggestion_md: str | None = None
    findings: list[RoutedFindingOut] = Field(default_factory=list)


# ------------------------------------------------------------------------------------------------------ lens
class LensVersionRef(BaseModel):
    id: str
    version: int
    created_at: datetime
    change_reason: str
    origin: Origin
    cutoff_at: datetime
    status: str
    counts: dict[str, int] = Field(default_factory=dict)


class LensSummary(BaseModel):
    id: str
    person: PersonRef
    status: str
    latest_version: int | None = None
    health_state: str | None = None
    shared_in_project: bool = True


class LensList(BaseModel):
    items: list[LensSummary]


class LensOverview(BaseModel):
    id: str
    person: PersonRef
    status: str
    consent: ConsentInfo | None = None
    versions: list[LensVersionRef]
    current_version: int | None = None
    unconsumed_feedback: int = 0
    update_min_events: int = 5
    health_state: str | None = None
    ruler_changed: bool = False
    owner_login: str | None = None
    fictional: bool = False


class LensVersionOut(BaseModel):
    id: str
    version: int
    card_md: str
    card: dict[str, Any] = Field(default_factory=dict)
    cutoff_at: datetime
    ruler_id: str
    ruler_display: str | None = None
    build_stats: dict[str, Any]
    items_count: dict[str, int]
    key_facts: dict[str, Any] = Field(default_factory=dict)
    change_reason: str
    provenance: Provenance


class Interval(BaseModel):
    low: float
    high: float


class LensItemStats(BaseModel):
    support: int = 0
    trigger_precision: float | None = None
    baseline_overlap: float | None = None
    posterior_mean: float | None = None
    ci90: Interval | None = None
    n_ignored: int = 0
    k_bad: int = 0
    base_rate: float | None = None
    lift: float | None = None
    first_seen: str | None = None
    last_seen: str | None = None
    enough_evidence: bool = True


class TriggersOut(BaseModel):
    paths: list[str] = Field(default_factory=list)
    code_patterns: list[str] = Field(default_factory=list)
    counter_patterns: list[str] = Field(default_factory=list)


class LensItemOut(BaseModel):
    id: str
    stable_key: str
    type: str
    title: str
    statement_md: str
    rationale_md: str | None = None
    category: str
    category_label: str
    severity_typical: str
    triggers: TriggersOut
    stats: LensItemStats
    status: str
    owner_override: str | None = None
    explanation: str | None = None
    bias: dict[str, Any] | None = None
    owner_only: bool = False
    provenance: dict[str, Any] = Field(default_factory=dict)


class LensItemList(BaseModel):
    items: list[LensItemOut]


class Exemplar(BaseModel):
    finding_id: str
    pr_number: int
    statement: str
    path: str | None = None
    line: int | None = None
    hunk: str | None = None
    comment_excerpt: str | None = None
    author: str | None = None
    at: datetime | None = None
    html_url: str | None = None


class LensItemDetail(LensItemOut):
    exemplars: list[Exemplar] = Field(default_factory=list)
    counter_examples: list[int] = Field(default_factory=list)
    history: list[dict[str, Any]] = Field(default_factory=list)
    outcomes: list[dict[str, Any]] = Field(default_factory=list)


class LensItemPatch(BaseModel):
    status: Literal["active", "muted"] | None = None
    edits: dict[str, str] | None = None
    not_me: bool = False
    reason: str | None = None


class LensDiffEntry(BaseModel):
    change: str
    item_id: str
    stable_key: str
    title: str
    category: str
    detail: str | None = None
    fields: dict[str, dict[str, Any]] = Field(default_factory=dict)


class LensDiff(BaseModel):
    from_version: int
    to_version: int
    added: list[LensDiffEntry]
    removed: list[LensDiffEntry]
    changed: list[LensDiffEntry]
    summary_md: str
    summary_simulated: bool = False


class LensActionRequest(BaseModel):
    reason: str | None = None
    confirm_token: str | None = None


class RevokeRequest(BaseModel):
    confirm: str
    typed_login: str | None = None


class EdgeCell(BaseModel):
    area: str
    category: str
    category_label: str
    volume: float
    residual_rate: float
    shared_rate: float
    cost: float
    value: float
    kind: str
    multiplier: float | None = None
    bad_outcomes: list[dict[str, Any]] = Field(default_factory=list)
    items: list[LensItemRef] = Field(default_factory=list)
    open_prs: list[int] = Field(default_factory=list)
    findings: int = 0


class EdgeMapOut(BaseModel):
    cells: list[EdgeCell]
    top: list[EdgeCell]
    enough: list[EdgeCell]
    gaps: list[EdgeCell]
    areas: list[str]
    categories: list[str]
    summary_md: str


class BiasOut(BaseModel):
    item_id: str
    title: str
    odds_ratio: float | None = None
    ci: Interval | None = None
    verdict: str
    n_by_group: dict[str, Any] = Field(default_factory=dict)
    outcome_check: dict[str, Any] = Field(default_factory=dict)
    explanation_md: str | None = None


class BiasList(BaseModel):
    items: list[BiasOut]


class GrowthPeriod(BaseModel):
    period: str
    period_start: datetime
    period_end: datetime
    measures: dict[str, Any]
    state: str | None = None


class GrowthOut(BaseModel):
    health_state: str
    explanation_md: str
    snapshots: list[GrowthPeriod]
    g_examples: list[FindingOut] = Field(default_factory=list)
    accepted_share: float | None = None


class AuditOut(BaseModel):
    at: datetime
    actor_role: str
    action: str
    object_type: str
    object_id: str
    details: dict[str, Any] = Field(default_factory=dict)


class AuditList(BaseModel):
    items: list[AuditOut]


# ----------------------------------------------------------------------------------------------------- proof
class FidelityRunRef(BaseModel):
    id: str
    lens_version: int
    created_at: datetime
    pass_overall: bool
    origin: Origin
    prs: int
    simulated: bool = False


class FidelityRunList(BaseModel):
    items: list[FidelityRunRef]


class Metric(BaseModel):
    value: float | None = None
    low: float | None = None
    high: float | None = None
    n: int | None = None


class SystemMetrics(BaseModel):
    substantive_recall: Metric
    residual_recall: Metric | None = None
    noise_per_pr: Metric
    precision: Metric
    caricature_ratio: Metric | None = None
    jsd: Metric | None = None
    per_category: dict[str, float] = Field(default_factory=dict)


class Criterion(BaseModel):
    key: str
    label: str
    passed: bool | None
    detail: str


class Falsifier(BaseModel):
    key: str
    name: str
    description_md: str
    result: str
    passed: bool | None


class FidelityRunOut(BaseModel):
    id: str
    lens_version: int
    person: PersonRef
    holdout: dict[str, Any]
    metrics: dict[str, SystemMetrics]
    paired_difference: Metric
    p_value: float | None = None
    routing: dict[str, Any] = Field(default_factory=dict)
    criteria: list[Criterion]
    pass_overall: bool
    falsifiers: list[Falsifier]
    sensitivity: dict[str, Any] = Field(default_factory=dict)
    measurement: dict[str, Any] = Field(default_factory=dict)
    cases_count: int
    cost_usd: float
    created_at: datetime
    provenance: Provenance


class CaseRow(BaseModel):
    pr_number: int
    title: str
    maintainer_findings: int
    baseline_matched: float
    lens_matched: float
    keeper_matched: float
    lens_extra: int = 0
    outcome: str


class CaseList(BaseModel):
    items: list[CaseRow]


class CaseDetail(BaseModel):
    pr_number: int
    title: str
    human: list[FindingOut]
    baseline: list[FindingOut]
    lens: list[FindingOut]
    matches: list[HumanPair]
    lens_baseline_pairs: list[ComparePair] = Field(default_factory=list)


class FidelityRunRequest(BaseModel):
    lens_version: int | None = None
    use_batch: bool = False
    confirm_token: str | None = None


# -------------------------------------------------------------------------------------------------- practice
class PracticeSessionRef(BaseModel):
    id: str
    kind: str
    status: str
    created_at: datetime
    items: int
    recall: float | None = None
    origin: Origin = "live"


class PracticeOverview(BaseModel):
    learner_key: str
    learner: PersonRef | None = None
    target: PersonRef | None = None
    sessions: list[PracticeSessionRef]
    growth: dict[str, Any] | None = None
    next_kind: str | None = None
    bank_size: int = 0
    lens_shared: bool = True
    scoring_available: bool = True


class PracticeStart(BaseModel):
    kind: Literal["taste", "before", "learn", "after"]
    target_person_id: str | None = None
    length: int | None = None
    learner: str | None = None


class PracticeItemRef(BaseModel):
    pr_number: int
    status: str


class PracticeSessionOut(BaseModel):
    id: str
    kind: str
    items: list[PracticeItemRef]
    current_index: int
    status: str
    target: PersonRef | None = None
    origin: Origin = "live"
    result: dict[str, Any] | None = None


class PracticeItemOut(BaseModel):
    pr_number: int
    title: str
    body_md: str
    files: list[PullFileInfo]
    diff: list[DiffFile]
    hint_available: bool
    attempt: int
    index: int
    total: int
    saved_notes: list[dict[str, Any]] = Field(default_factory=list)


class PracticeNote(BaseModel):
    scope: Literal["line", "pr"] = "line"
    path: str | None = None
    line: int | None = None
    text: str


class PracticeAnswerRequest(BaseModel):
    notes: list[PracticeNote]


class PracticeFeedback(BaseModel):
    attempt: int
    status: str
    hints: list[dict[str, Any]] = Field(default_factory=list)
    reveal: dict[str, Any] | None = None
    measures: dict[str, Any] = Field(default_factory=dict)
    scoring_simulated: bool = False


class PracticeResult(BaseModel):
    result: dict[str, Any]


# ------------------------------------------------------------------------------------------------- assistant
class ChatThreadOut(BaseModel):
    id: str
    title: str
    context: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime
    origin: Origin = "live"


class ChatThreadList(BaseModel):
    items: list[ChatThreadOut]


class ChatThreadCreate(BaseModel):
    context: dict[str, Any] | None = None


class ChatMessageOut(BaseModel):
    id: str
    role: str
    content_md: str
    cards: list[Card] = Field(default_factory=list)
    tool_trace: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    model: str | None = None
    cost_usd: float | None = None


class ChatThreadDetail(ChatThreadOut):
    messages: list[ChatMessageOut]


class ChatThreadPatch(BaseModel):
    title: str


class ChatSend(BaseModel):
    text: str
    context: dict[str, Any] | None = None


class Suggestion(BaseModel):
    text: str
    context: dict[str, Any] | None = None


class SuggestionList(BaseModel):
    items: list[Suggestion]


class ChatExample(BaseModel):
    id: str
    question: str
    answer_md: str
    cards: list[Card] = Field(default_factory=list)
    tool_trace: list[dict[str, Any]] = Field(default_factory=list)


class ChatExampleList(BaseModel):
    items: list[ChatExample]
    simulated: bool = False


# ------------------------------------------------------------------------------------------------------ jobs
class JobOut(BaseModel):
    id: str
    kind: str
    status: str
    params: dict[str, Any]
    progress: float
    step: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None
    cost_usd: float
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    events_url: str


class JobList(BaseModel):
    items: list[JobOut]


# -------------------------------------------------------------------------------------------------- settings
class EditableSetting(BaseModel):
    key: str
    label: str
    type: str
    value: Any
    default: Any
    min: float | None = None
    max: float | None = None
    options: list[str] | None = None


class SecretState(BaseModel):
    configured: bool


class SettingsOut(BaseModel):
    editable: list[EditableSetting]
    readonly: dict[str, Any]
    secrets: dict[str, SecretState]


class UsageRow(BaseModel):
    key: str
    calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


class UsageOut(BaseModel):
    period: str
    group_by: str
    rows: list[UsageRow]
    total: UsageRow
    cap: SpendStatus
    snapshot_rows: list[UsageRow] = Field(default_factory=list)


# ------------------------------------------------------------------------------------------- SSE event models
class JobEventData(BaseModel):
    """Every job event carries job_id and at; the rest depends on the event type (05-api/03)."""

    job_id: str
    at: str
    model_config = {"extra": "allow"}


class ChatEventData(BaseModel):
    model_config = {"extra": "allow"}
