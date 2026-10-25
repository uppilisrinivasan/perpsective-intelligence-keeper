from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends

from keeper.app import schemas as S
from keeper.app.deps import Ctx, get_ctx
from keeper.services import pulls

router = APIRouter(tags=["pulls"])


@router.get("/projects/{pid}/pulls/{n}", response_model=S.PullDetail)
def get_pull(pid: str, n: int) -> S.PullDetail:
    return pulls.get_pull(pid, n)


@router.get("/projects/{pid}/pulls/{n}/diff", response_model=S.DiffResponse)
def get_diff(pid: str, n: int, file: str | None = None) -> S.DiffResponse:
    return pulls.get_diff(pid, n, file)


@router.get("/projects/{pid}/pulls/{n}/analysis", response_model=S.AnalysisResponse)
def get_analysis(pid: str, n: int, ctx: Ctx = Depends(get_ctx)) -> S.AnalysisResponse:
    return pulls.get_analysis(pid, n, ctx)


@router.post("/projects/{pid}/pulls/{n}/analysis", response_model=S.JobAccepted, status_code=202)
def analyze(pid: str, n: int, body: S.AnalyzeRequest, ctx: Ctx = Depends(get_ctx)) -> S.JobAccepted:
    return pulls.analyze(pid, n, body, ctx)


@router.get("/projects/{pid}/pulls/{n}/compare", response_model=S.CompareResponse)
def get_compare(pid: str, n: int) -> S.CompareResponse:
    return pulls.get_compare(pid, n)


@router.get("/projects/{pid}/pulls/{n}/history", response_model=S.HistoryResponse)
def get_history(pid: str, n: int, person_id: str | None = None) -> S.HistoryResponse:
    return pulls.get_history(pid, n, person_id)


@router.get("/projects/{pid}/pulls/{n}/human-review", response_model=S.HumanReviewResponse)
def get_human_review(pid: str, n: int) -> S.HumanReviewResponse:
    return pulls.get_human_review(pid, n)


@router.patch("/projects/{pid}/findings/{rf_id}", response_model=S.RoutedFindingOut)
def patch_finding(pid: str, rf_id: str, body: S.FeedbackRequest, ctx: Ctx = Depends(get_ctx)) -> S.RoutedFindingOut:
    return pulls.patch_finding(pid, rf_id, body, ctx)


@router.post("/projects/{pid}/pulls/{n}/notes", response_model=S.RoutedFindingOut, status_code=201)
def add_note(pid: str, n: int, body: S.NoteRequest, ctx: Ctx = Depends(get_ctx)) -> S.RoutedFindingOut:
    return pulls.add_note(pid, n, body, ctx)


@router.post("/projects/{pid}/pulls/{n}/lane", response_model=S.LaneOverrideResponse)
def override_lane(pid: str, n: int, body: S.LaneOverrideRequest, ctx: Ctx = Depends(get_ctx)) -> S.LaneOverrideResponse:
    return pulls.override_lane(pid, n, body, ctx)


@router.get("/projects/{pid}/pulls/{n}/review-draft", response_model=S.ReviewDraftOut)
def get_review_draft(pid: str, n: int) -> S.ReviewDraftOut:
    return pulls.get_review_draft(pid, n)


@router.put("/projects/{pid}/pulls/{n}/review-draft", response_model=S.ReviewDraftOut)
def put_review_draft(pid: str, n: int, body: S.ReviewDraftUpdate, ctx: Ctx = Depends(get_ctx)) -> S.ReviewDraftOut:
    return pulls.put_review_draft(pid, n, body, ctx)


@router.get("/projects/{pid}/pulls/{n}/review-draft/export", response_model=S.ReviewDraftExport)
def export_review_draft(pid: str, n: int, format: Literal["md", "github_json"] = "md") -> S.ReviewDraftExport:
    return pulls.export_review_draft(pid, n, format)


@router.post("/projects/{pid}/pulls/{n}/handoff", response_model=S.JobAccepted, status_code=202)
def start_handoff(pid: str, n: int, body: S.ActionRequest, ctx: Ctx = Depends(get_ctx)) -> S.JobAccepted:
    return pulls.start_handoff(pid, n, body, ctx)


@router.get("/projects/{pid}/pulls/{n}/handoff", response_model=S.HandoffOut)
def get_handoff(pid: str, n: int) -> S.HandoffOut:
    return pulls.get_handoff(pid, n)


@router.get("/projects/{pid}/pulls/{n}/outcomes", response_model=S.OutcomesResponse)
def get_outcomes(pid: str, n: int) -> S.OutcomesResponse:
    return pulls.get_outcomes(pid, n)
