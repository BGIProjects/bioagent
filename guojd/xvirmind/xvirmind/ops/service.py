from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from xvirmind.ops.store import JsonStore

ROLES = ("owner", "analyst", "reviewer", "viewer")
PERMISSIONS = {
    "owner": {"upload", "execute", "review", "publish_kb", "manage_members", "recover"},
    "analyst": {"upload", "execute", "recover"},
    "reviewer": {"review", "execute"},
    "viewer": set(),
}

# Calibrated ranges for the 20k-pair testdata pack. DB search dominates W2/W4.
ESTIMATES = {
    "workflow1": {
        "label": "W1 质控组装",
        "reads": 20000,
        "wall_min": "8–25",
        "queue_reason": "CPU 组装；小样本仍要跑完 bowtie/megahit",
        "heavy": False,
    },
    "workflow2": {
        "label": "W2 virusid",
        "reads": 20000,
        "wall_min": "90–360",
        "queue_reason": "NT/NR/HMM 库检索，耗时几乎不随抽样子线性下降",
        "heavy": True,
    },
    "workflow3": {
        "label": "W3 宿主鉴定",
        "reads": 20000,
        "wall_min": "20–90",
        "queue_reason": "宿主比对与覆盖度",
        "heavy": True,
    },
    "workflow4": {
        "label": "W4 Kraken/Bracken",
        "reads": 20000,
        "wall_min": "15–45",
        "queue_reason": "Kraken 库常驻内存，排队看节点空闲",
        "heavy": True,
    },
    "workflow6": {
        "label": "W6 流程注释",
        "reads": 20000,
        "wall_min": "20–90",
        "queue_reason": "依赖 W2 候选；无候选则跳过",
        "heavy": False,
    },
    "rva": {
        "label": "RVA 专项注释",
        "reads": 1,
        "wall_min": "10–60",
        "queue_reason": "rnavirus 环境 + HMM/Diamond；GPU 可选",
        "heavy": True,
    },
}

PRIORITY = {"emergency": 0, "high": 1, "standard": 2, "low": 3}


class OpsError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class OpsService:
    def __init__(self, root: Path, testdata: Path, knowledge_root: Path):
        self.root = Path(root)
        self.testdata = Path(testdata)
        self.knowledge_root = Path(knowledge_root)
        self.store = JsonStore(self.root)
        self.uploads = self.root / "uploads"
        self.uploads.mkdir(parents=True, exist_ok=True)
        self._seed()

    def _seed(self) -> None:
        projects = self.store.load("projects.json", None)
        if projects is None:
            projects = {
                "projects": [
                    {
                        "id": "proj-testdata",
                        "name": "XvirMind 测试窗口",
                        "members": [
                            {"user": "guojindan", "role": "owner"},
                            {"user": "lihuyang", "role": "analyst"},
                            {"user": "liufangzhou", "role": "analyst"},
                            {"user": "wangdaxi", "role": "reviewer"},
                        ],
                    }
                ]
            }
            self.store.save("projects.json", projects)
        if self.store.load("jobs.json", None) is None:
            self.store.save("jobs.json", {"jobs": []})
        if self.store.load("reviews.json", None) is None:
            self.store.save("reviews.json", {"reviews": []})
        if self.store.load("uploads.json", None) is None:
            self.store.save("uploads.json", {"uploads": []})

    def snapshot(self) -> dict[str, Any]:
        return {
            "projects": self.store.load("projects.json", {"projects": []}),
            "jobs": self.store.load("jobs.json", {"jobs": []}),
            "reviews": self.store.load("reviews.json", {"reviews": []}),
            "uploads": self.store.load("uploads.json", {"uploads": []}),
            "estimates": ESTIMATES,
            "knowledge_releases": self.list_packs(),
        }

    # --- governance ---
    def list_projects(self) -> list[dict[str, Any]]:
        return self.store.load("projects.json", {"projects": []})["projects"]

    def require(self, user: str, project_id: str, permission: str) -> dict[str, Any]:
        project = next((p for p in self.list_projects() if p["id"] == project_id), None)
        if not project:
            raise OpsError(f"unknown project {project_id}", 404)
        member = next((m for m in project["members"] if m["user"] == user), None)
        if not member:
            raise OpsError(f"{user} is not a member of {project_id}", 403)
        allowed = PERMISSIONS.get(member["role"], set())
        if permission not in allowed:
            raise OpsError(f"role {member['role']} cannot {permission}", 403)
        return {"project": project, "member": member}

    def add_member(self, actor: str, project_id: str, user: str, role: str) -> dict[str, Any]:
        if role not in ROLES:
            raise OpsError(f"invalid role {role}")
        self.require(actor, project_id, "manage_members")
        data = self.store.load("projects.json", {"projects": []})
        for project in data["projects"]:
            if project["id"] != project_id:
                continue
            existing = next((m for m in project["members"] if m["user"] == user), None)
            if existing:
                existing["role"] = role
            else:
                project["members"].append({"user": user, "role": role})
            self.store.save("projects.json", data)
            return project
        raise OpsError("project not found", 404)

    # --- chunked upload ---
    def init_upload(
        self,
        actor: str,
        project_id: str,
        filename: str,
        size: int,
        sha256: str | None = None,
    ) -> dict[str, Any]:
        self.require(actor, project_id, "upload")
        if size <= 0 or size > 32 * 1024 * 1024 * 1024:
            raise OpsError("file size must be between 1 byte and 32 GiB")
        safe = Path(filename).name
        if not safe or ".." in safe:
            raise OpsError("invalid filename")
        upload_id = f"up_{uuid.uuid4().hex[:16]}"
        dest = self.uploads / upload_id
        dest.mkdir(parents=True, exist_ok=True)
        record = {
            "id": upload_id,
            "project_id": project_id,
            "actor": actor,
            "filename": safe,
            "size": size,
            "sha256": sha256,
            "chunk_size": 4 * 1024 * 1024,
            "received": [],
            "status": "uploading",
            "created_at": self.store.now(),
            "final_path": None,
        }
        data = self.store.load("uploads.json", {"uploads": []})
        data["uploads"].append(record)
        self.store.save("uploads.json", data)
        return record

    def put_chunk(self, upload_id: str, index: int, payload: bytes) -> dict[str, Any]:
        data = self.store.load("uploads.json", {"uploads": []})
        record = next((u for u in data["uploads"] if u["id"] == upload_id), None)
        if not record:
            raise OpsError("upload not found", 404)
        if record["status"] != "uploading":
            raise OpsError("upload is not active")
        chunk_path = self.uploads / upload_id / f"{index:08d}.part"
        chunk_path.write_bytes(payload)
        if index not in record["received"]:
            record["received"].append(index)
            record["received"] = sorted(record["received"])
        self.store.save("uploads.json", data)
        return {"id": upload_id, "received": record["received"], "status": record["status"]}

    def complete_upload(self, upload_id: str) -> dict[str, Any]:
        data = self.store.load("uploads.json", {"uploads": []})
        record = next((u for u in data["uploads"] if u["id"] == upload_id), None)
        if not record:
            raise OpsError("upload not found", 404)
        parts = sorted((self.uploads / upload_id).glob("*.part"))
        if not parts:
            raise OpsError("no chunks received")
        incoming = self.testdata / "uploads"
        incoming.mkdir(parents=True, exist_ok=True)
        final = incoming / record["filename"]
        with final.open("wb") as out:
            for part in parts:
                out.write(part.read_bytes())
        digest = hashlib.sha256(final.read_bytes()).hexdigest()
        if record.get("sha256") and record["sha256"] != digest:
            final.unlink(missing_ok=True)
            raise OpsError("sha256 mismatch")
        record["status"] = "completed"
        record["final_path"] = str(final)
        record["sha256_actual"] = digest
        record["bytes_written"] = final.stat().st_size
        self.store.save("uploads.json", data)
        shutil.rmtree(self.uploads / upload_id, ignore_errors=True)
        return record

    # --- queue / recover ---
    def estimates(self) -> dict[str, Any]:
        return {"testdata_reads": 20000, "workflows": ESTIMATES}

    def enqueue(
        self,
        actor: str,
        project_id: str,
        kind: str,
        priority: str = "standard",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.require(actor, project_id, "execute")
        if kind not in ESTIMATES:
            raise OpsError(f"unknown job kind {kind}")
        if priority not in PRIORITY:
            raise OpsError(f"unknown priority {priority}")
        jobs = self.store.load("jobs.json", {"jobs": []})
        job = {
            "id": f"job_{uuid.uuid4().hex[:12]}",
            "project_id": project_id,
            "actor": actor,
            "kind": kind,
            "priority": priority,
            "priority_rank": PRIORITY[priority],
            "status": "queued",
            "checkpoint": None,
            "payload": payload or {},
            "estimate": ESTIMATES[kind],
            "created_at": self.store.now(),
            "updated_at": self.store.now(),
            "error": None,
        }
        jobs["jobs"].append(job)
        jobs["jobs"].sort(key=lambda item: (item["priority_rank"], item["created_at"]))
        self.store.save("jobs.json", jobs)
        return job

    def list_jobs(self) -> list[dict[str, Any]]:
        return self.store.load("jobs.json", {"jobs": []})["jobs"]

    def _job(self, job_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        data = self.store.load("jobs.json", {"jobs": []})
        job = next((item for item in data["jobs"] if item["id"] == job_id), None)
        if not job:
            raise OpsError("job not found", 404)
        return data, job

    def set_job_status(
        self,
        job_id: str,
        status: str,
        checkpoint: str | None = None,
        error: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data, job = self._job(job_id)
        job["status"] = status
        if checkpoint is not None:
            job["checkpoint"] = checkpoint
        if error is not None:
            job["error"] = error
        if extra:
            job.update(extra)
        job["updated_at"] = self.store.now()
        self.store.save("jobs.json", data)
        return job

    def recover(self, actor: str, job_id: str) -> dict[str, Any]:
        data, job = self._job(job_id)
        self.require(actor, job["project_id"], "recover")
        if job["status"] not in {"failed", "paused"}:
            raise OpsError("only failed or paused jobs can be recovered")
        job["status"] = "queued"
        job["error"] = None
        job["updated_at"] = self.store.now()
        job["recovered_from"] = job.get("checkpoint")
        self.store.save("jobs.json", data)
        return job

    def pause(self, actor: str, job_id: str) -> dict[str, Any]:
        data, job = self._job(job_id)
        self.require(actor, job["project_id"], "recover")
        if job["status"] not in {"queued", "running"}:
            raise OpsError("job cannot be paused")
        job["status"] = "paused"
        job["updated_at"] = self.store.now()
        self.store.save("jobs.json", data)
        return job

    # --- knowledge packs ---
    def list_packs(self) -> list[dict[str, Any]]:
        releases = self.knowledge_root / "releases"
        if not releases.exists():
            return []
        out = []
        seen = set()
        for path in sorted(releases.glob("*/manifest.json")):
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            pack_id = item.get("pack_id") or path.parent.name
            if pack_id in seen:
                continue
            seen.add(pack_id)
            out.append(item)
        return out

    # --- candidate rules ---
    def evaluate_candidates(self, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        for index, item in enumerate(candidates):
            cid = str(item.get("id") or f"cand-{index+1}")
            family = item.get("family") or item.get("w2_family")
            rva_family = item.get("rva_family")
            taxonomy = item.get("taxonomy") or {}
            evidence = item.get("evidence") or []
            locator = taxonomy.get("locator") or item.get("kb_locator")
            if not family:
                findings.append(_finding(cid, "MISSING_TAXONOMY", "error", "候选缺少科级分类"))
            if family and rva_family and family != rva_family:
                findings.append(
                    _finding(
                        cid,
                        "FAMILY_CONFLICT",
                        "error",
                        f"W2 科 {family} 与 RVA 科 {rva_family} 不一致",
                    )
                )
            if family and not locator:
                findings.append(
                    _finding(
                        cid,
                        "INCOMPLETE_EVIDENCE",
                        "warn",
                        "无 kb.jsonl locator，不能作为正式定种引用",
                    )
                )
            if item.get("rva_status") in {None, "AWAITING_CONFIRM", "NOT_RUN"}:
                findings.append(
                    _finding(cid, "RVA_NOT_CONFIRMED", "info", "RVA 未确认实跑或未完成")
                )
            if not evidence:
                findings.append(
                    _finding(cid, "INCOMPLETE_EVIDENCE", "warn", "缺少证据条目")
                )
        completeness = "complete" if not any(f["severity"] == "error" for f in findings) else "blocked"
        return {
            "candidate_count": len(candidates),
            "finding_count": len(findings),
            "completeness": completeness,
            "findings": findings,
        }

    # --- expert review ---
    def submit_review(
        self,
        actor: str,
        project_id: str,
        run_id: str,
        decision: str,
        reason: str = "",
        findings: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self.require(actor, project_id, "review")
        if decision not in {"approve", "reject"}:
            raise OpsError("decision must be approve or reject")
        if decision == "reject" and len(reason.strip()) < 4:
            raise OpsError("reject requires a reason (打回意见)")
        data = self.store.load("reviews.json", {"reviews": []})
        review = {
            "id": f"rv_{uuid.uuid4().hex[:12]}",
            "project_id": project_id,
            "run_id": run_id,
            "actor": actor,
            "decision": decision,
            "reason": reason,
            "findings": findings or [],
            "created_at": self.store.now(),
            "final": decision == "approve",
        }
        data["reviews"].append(review)
        self.store.save("reviews.json", data)
        return review

    def reviews_for(self, run_id: str) -> list[dict[str, Any]]:
        return [r for r in self.store.load("reviews.json", {"reviews": []})["reviews"] if r["run_id"] == run_id]


def _finding(candidate_id: str, code: str, severity: str, message: str) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "code": code,
        "severity": severity,
        "message": message,
        "requires_expert_review": severity == "error",
    }
