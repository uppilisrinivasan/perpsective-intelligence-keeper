from __future__ import annotations

from fastapi import APIRouter, Depends

from keeper.app import schemas as S
from keeper.app.deps import Ctx, get_ctx
from keeper.services import proof

router = APIRouter(tags=["proof"])


@router.get("/projects/{pid}/fidelity-runs", response_model=S.FidelityRunList)
def list_runs(pid: str) -> S.FidelityRunList:
    return proof.list_runs(pid)


@router.get("/fidelity-runs/{fid}", response_model=S.FidelityRunOut)
def get_run(fid: str) -> S.FidelityRunOut:
    return proof.get_run(fid)


@router.get("/fidelity-runs/{fid}/cases", response_model=S.CaseList)
def list_cases(fid: str, q: str | None = None, outcome: str | None = None) -> S.CaseList:
    return proof.list_cases(fid, q, outcome)


@router.get("/fidelity-runs/{fid}/cases/{n}", response_model=S.CaseDetail)
def get_case(fid: str, n: int) -> S.CaseDetail:
    return proof.get_case(fid, n)


@router.post("/projects/{pid}/fidelity-runs", response_model=S.JobAccepted, status_code=202)
def start_run(pid: str, body: S.FidelityRunRequest, ctx: Ctx = Depends(get_ctx)) -> S.JobAccepted:
    return proof.start_run(pid, body, ctx)
