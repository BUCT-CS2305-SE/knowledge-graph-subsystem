"""后台管理接口：artifact CRUD + 数据一致性检查 + 数据流水线一键触发。

使用 admin 侧签发的 JWT 进行鉴权（KG_JWT_SECRET / KG_JWT_ISSUER）。
"""

from __future__ import annotations

import subprocess
import sys
import threading
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from ..auth import verify_token
from ..config import app_config
from ..db import get_neo4j_driver, mysql_cursor

router = APIRouter(prefix="/api/admin", tags=["Admin"])

ROOT = Path(app_config.project_root)


def _check_token(authorization: Optional[str], x_token: Optional[str]) -> None:
    verify_token(authorization, x_token, allowed_user_types=["ADMIN"])


WRITABLE_COLS = (
    "title", "period", "type", "material", "description",
    "dimensions", "museum", "location",
    "detail_url", "image_url", "image_path",
    "credit_line", "accession_number",
)


@router.post("/artifacts", summary="新增文物")
def admin_create(
    payload: dict,
    authorization: Optional[str] = Header(None),
    x_token: Optional[str] = Header(None),
):
    _check_token(authorization, x_token)
    object_id = payload.get("object_id")
    if not object_id:
        raise HTTPException(status_code=400, detail={
            "code": 400, "message": "object_id required"})
    cols = ["object_id"] + [c for c in WRITABLE_COLS if c in payload]
    vals = [object_id] + [payload[c] for c in WRITABLE_COLS if c in payload]
    placeholders = ",".join(["%s"] * len(cols))
    sql = f"INSERT INTO artifacts ({','.join(cols)}) VALUES ({placeholders})"
    with mysql_cursor() as cur:
        try:
            cur.execute(sql, tuple(vals))
            cur.connection.commit()
        except Exception as e:
            raise HTTPException(status_code=400, detail={
                "code": 400, "message": str(e)})
    return {"ok": True, "id": object_id}


@router.put("/artifacts/{object_id}", summary="编辑文物")
def admin_update(
    object_id: str,
    payload: dict,
    authorization: Optional[str] = Header(None),
    x_token: Optional[str] = Header(None),
):
    _check_token(authorization, x_token)
    updates = {k: v for k, v in payload.items() if k in WRITABLE_COLS}
    if not updates:
        raise HTTPException(status_code=400, detail={
            "code": 400, "message": "No writable fields"})
    set_clause = ",".join(f"{k}=%s" for k in updates)
    sql = f"UPDATE artifacts SET {set_clause} WHERE object_id=%s"
    with mysql_cursor() as cur:
        cur.execute(sql, tuple(list(updates.values()) + [object_id]))
        cur.connection.commit()
        affected = cur.rowcount
    if affected == 0:
        raise HTTPException(status_code=404, detail={
            "code": 404, "message": "Artifact not found"})
    return {"ok": True, "affected": affected}


@router.delete("/artifacts/{object_id}", summary="删除文物")
def admin_delete(
    object_id: str,
    authorization: Optional[str] = Header(None),
    x_token: Optional[str] = Header(None),
):
    _check_token(authorization, x_token)
    with mysql_cursor() as cur:
        cur.execute("DELETE FROM artifacts WHERE object_id=%s", (object_id,))
        cur.connection.commit()
        affected = cur.rowcount
    # 同步删除 Neo4j 节点（best-effort）
    try:
        driver = get_neo4j_driver()
        with driver.session() as s:
            s.run("MATCH (a:Artifact {id:$id}) DETACH DELETE a", id=object_id)
    except Exception:
        pass
    if affected == 0:
        raise HTTPException(status_code=404, detail={
            "code": 404, "message": "Artifact not found"})
    return {"ok": True, "affected": affected}


@router.get("/consistency-check", summary="MySQL ↔ Neo4j 数据一致性检查")
def consistency_check(
    authorization: Optional[str] = Header(None),
    x_token: Optional[str] = Header(None),
):
    _check_token(authorization, x_token)
    with mysql_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM artifacts")
        sql_count = cur.fetchone()["c"]

    neo_count = 0
    try:
        driver = get_neo4j_driver()
        with driver.session() as s:
            r = s.run("MATCH (a:Artifact) RETURN count(a) AS c").single()
            neo_count = r["c"] if r else 0
    except Exception as e:
        return {
            "mysql_artifacts": sql_count,
            "neo4j_artifacts": None,
            "error": str(e),
        }
    return {
        "mysql_artifacts": sql_count,
        "neo4j_artifacts": neo_count,
        "diff": sql_count - neo_count,
        "consistent": sql_count == neo_count,
    }


# ======================= 数据流水线一键触发 =======================
#
# 把「清洗 / 补充 / 增量」三类离线脚本封装成后台任务，供后台管理子系统在
# API docs 上一键触发。脚本以子进程方式在仓库根目录运行，输出实时写入内存
# 日志环形缓冲；同一时间只允许一个任务运行，避免并发写库冲突。

# 任务名 -> 命令（相对仓库根，使用当前 Python 解释器）
_JOB_COMMANDS: dict[str, list[str]] = {
    "clean": [sys.executable, "data_processing/cleaning/run_all_clean.py"],
    "enrich": [sys.executable, "data_update/enrichment/enrichment.py"],
    "incremental": [
        sys.executable, "data_update/incremental/incremental.py", "scan",
        "--museums", "chicago", "princeton", "brooklyn_museum",
    ],
}

# 当前/最近一次任务状态
_job_lock = threading.Lock()
_current: dict | None = None
_history: deque[dict] = deque(maxlen=20)


def _run_job(job_id: str, name: str, cmd: list[str]) -> None:
    global _current
    logs: deque[str] = deque(maxlen=500)
    proc = None
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(ROOT),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        with _job_lock:
            if _current and _current["id"] == job_id:
                _current["logs"] = logs
        assert proc.stdout is not None
        for line in proc.stdout:
            logs.append(line.rstrip("\n"))
        proc.wait()
        rc = proc.returncode
    except Exception as exc:  # noqa: BLE001
        logs.append(f"EXCEPTION: {exc}")
        rc = -1
    finished = datetime.now().isoformat(timespec="seconds")
    with _job_lock:
        if _current and _current["id"] == job_id:
            _current["status"] = "succeeded" if rc == 0 else "failed"
            _current["return_code"] = rc
            _current["finished_at"] = finished
            _current["logs"] = logs
            _history.appendleft({
                k: _current[k] for k in
                ("id", "name", "status", "return_code",
                 "started_at", "finished_at")
            })


def _job_snapshot(job: dict, tail: int = 60) -> dict:
    logs = list(job.get("logs") or [])
    return {
        "id": job["id"],
        "name": job["name"],
        "status": job["status"],
        "return_code": job.get("return_code"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "log_tail": logs[-tail:],
    }


@router.post("/jobs/{name}", summary="一键触发数据任务（clean/enrich/incremental）")
def trigger_job(
    name: str,
    authorization: Optional[str] = Header(None),
    x_token: Optional[str] = Header(None),
):
    """触发离线数据脚本。name 取值：

    - clean       : 数据清洗（data_processing/cleaning/run_all_clean.py）
    - enrich      : 数据补充（百度百科优先，维基兜底）
    - incremental : 增量扫描（chicago/princeton/brooklyn_museum）
    """
    _check_token(authorization, x_token)
    if name not in _JOB_COMMANDS:
        raise HTTPException(status_code=400, detail={
            "code": 400,
            "message": f"unknown job '{name}', "
                       f"allowed: {sorted(_JOB_COMMANDS)}"})
    global _current
    with _job_lock:
        if _current and _current["status"] == "running":
            raise HTTPException(status_code=409, detail={
                "code": 409,
                "message": f"another job is running: "
                           f"{_current['name']} ({_current['id']})"})
        job_id = uuid.uuid4().hex[:12]
        _current = {
            "id": job_id,
            "name": name,
            "status": "running",
            "return_code": None,
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "finished_at": None,
            "logs": deque(maxlen=500),
        }
    cmd = _JOB_COMMANDS[name]
    threading.Thread(
        target=_run_job, args=(job_id, name, cmd), daemon=True,
    ).start()
    return {"ok": True, "id": job_id, "name": name, "status": "running"}


@router.get("/jobs/status", summary="查看当前/最近一次数据任务状态与日志")
def job_status(
    tail: int = 60,
    authorization: Optional[str] = Header(None),
    x_token: Optional[str] = Header(None),
):
    _check_token(authorization, x_token)
    with _job_lock:
        current = _job_snapshot(_current, tail) if _current else None
        history = list(_history)
    return {"current": current, "history": history}

