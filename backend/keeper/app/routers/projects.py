from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from keeper.app import schemas as S
from keeper.app.deps import Ctx, get_ctx
from keeper.services import projects

router = APIRouter(tags=["projects"])


@router.get("/projects", response_model=S.ProjectList)
def list_projects() -> S.ProjectList:
    return projects.list_projects()


@router.get("/projects/{pid}", response_model=S.ProjectDetail)
def get_project(pid: str) -> S.ProjectDetail:
    return projects.get_project(pid)


@router.post("/projects/import", response_model=S.JobAccepted, status_code=202)
def import_project(body: S.ImportRequest, ctx: Ctx = Depends(get_ctx)) -> S.JobAccepted:
    return projects.import_project(body, ctx)


@router.delete("/projects/{pid}", status_code=204, response_class=Response, response_model=None)
def delete_project(pid: str, ctx: Ctx = Depends(get_ctx)) -> None:
    projects.delete_project(pid, ctx)


@router.get("/projects/{pid}/people", response_model=S.PeopleList)
def list_people(pid: str, role: str | None = None) -> S.PeopleList:
    return projects.list_people(pid, role)


@router.get("/projects/{pid}/people/{person_id}", response_model=S.PersonDetail)
def get_person(pid: str, person_id: str) -> S.PersonDetail:
    return projects.get_person(pid, person_id)


@router.post("/projects/{pid}/people/{person_id}/consent", response_model=S.PersonDetail)
def record_consent(pid: str, person_id: str, body: S.ConsentRequest, ctx: Ctx = Depends(get_ctx)) -> S.PersonDetail:
    return projects.record_consent(pid, person_id, body, ctx)
