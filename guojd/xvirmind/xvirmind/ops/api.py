from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile

from xvirmind.config import load
from xvirmind.ops.rva import job_status as rva_job_status
from xvirmind.ops.service import OpsError, OpsService
from xvirmind.ops.specialist_report import render_specialist_html

CFG = load()
ROOT = Path(__file__).resolve().parents[2]
OPS_ROOT = ROOT / "runs" / "ops"
TESTDATA = Path("/data/user/guojindan/Projects/XvirMind/testdata")
KNOWLEDGE = Path("/data/user/guojindan/Projects/XvirMind/knowledge")
RVA_DEMO = ROOT / "runs" / "rva" / "kp641127"

ops = OpsService(OPS_ROOT, TESTDATA, KNOWLEDGE)
router = APIRouter(prefix="/api/ops", tags=["ops"])


def _user(x_user: str | None) -> str:
    return (x_user or "guojindan").strip() or "guojindan"


def _err(error: OpsError):
    raise HTTPException(status_code=error.status_code, detail=str(error)) from error


@router.get("/snapshot")
def snapshot() -> dict[str, Any]:
    data = ops.snapshot()
    data["rva_demo"] = rva_job_status(RVA_DEMO)
    return data


@router.get("/projects")
def projects() -> dict[str, Any]:
    return {"projects": ops.list_projects()}


@router.post("/projects/{project_id}/members")
def add_member(project_id: str, payload: dict[str, Any], x_user: str | None = Header(default=None)) -> dict[str, Any]:
    try:
        return ops.add_member(_user(x_user), project_id, str(payload.get("user") or ""), str(payload.get("role") or "viewer"))
    except OpsError as error:
        _err(error)


@router.post("/uploads/init")
def upload_init(payload: dict[str, Any], x_user: str | None = Header(default=None)) -> dict[str, Any]:
    try:
        return ops.init_upload(
            _user(x_user),
            str(payload.get("project_id") or "proj-testdata"),
            str(payload.get("filename") or ""),
            int(payload.get("size") or 0),
            payload.get("sha256"),
        )
    except OpsError as error:
        _err(error)


@router.post("/uploads/{upload_id}/chunk")
async def upload_chunk(upload_id: str, index: int = Form(...), file: UploadFile = File(...)) -> dict[str, Any]:
    payload = await file.read()
    try:
        return ops.put_chunk(upload_id, int(index), payload)
    except OpsError as error:
        _err(error)


@router.post("/uploads/{upload_id}/complete")
def upload_complete(upload_id: str) -> dict[str, Any]:
    try:
        return ops.complete_upload(upload_id)
    except OpsError as error:
        _err(error)


@router.get("/estimates")
def estimates() -> dict[str, Any]:
    return ops.estimates()


@router.post("/jobs")
def enqueue(payload: dict[str, Any], x_user: str | None = Header(default=None)) -> dict[str, Any]:
    try:
        return ops.enqueue(
            _user(x_user),
            str(payload.get("project_id") or "proj-testdata"),
            str(payload.get("kind") or ""),
            str(payload.get("priority") or "standard"),
            payload.get("payload") if isinstance(payload.get("payload"), dict) else None,
        )
    except OpsError as error:
        _err(error)


@router.post("/jobs/{job_id}/pause")
def pause(job_id: str, x_user: str | None = Header(default=None)) -> dict[str, Any]:
    try:
        return ops.pause(_user(x_user), job_id)
    except OpsError as error:
        _err(error)


@router.post("/jobs/{job_id}/recover")
def recover(job_id: str, x_user: str | None = Header(default=None)) -> dict[str, Any]:
    try:
        return ops.recover(_user(x_user), job_id)
    except OpsError as error:
        _err(error)


@router.post("/rules/evaluate")
def evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    candidates = payload.get("candidates") if isinstance(payload.get("candidates"), list) else []
    return ops.evaluate_candidates(candidates)


@router.post("/reviews")
def review(payload: dict[str, Any], x_user: str | None = Header(default=None)) -> dict[str, Any]:
    try:
        return ops.submit_review(
            _user(x_user),
            str(payload.get("project_id") or "proj-testdata"),
            str(payload.get("run_id") or ""),
            str(payload.get("decision") or ""),
            str(payload.get("reason") or ""),
            payload.get("findings") if isinstance(payload.get("findings"), list) else None,
        )
    except OpsError as error:
        _err(error)


@router.get("/rva")
def rva() -> dict[str, Any]:
    return rva_job_status(RVA_DEMO)


@router.get("/report/preview")
def report_preview() -> dict[str, Any]:
    specialist = Path(OPS_ROOT / "specialist.json")
    data = {}
    if specialist.exists():
        import json

        data = json.loads(specialist.read_text(encoding="utf-8"))
    html = render_specialist_html(
        taxonomy=data.get("taxonomy"),
        rva=data.get("rva"),
        citations=data.get("citations"),
        rules=data.get("rules"),
        review=data.get("review"),
    )
    return {"html": html, "data": data}
