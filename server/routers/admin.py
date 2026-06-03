"""后台管理接口：artifact CRUD + 数据一致性检查。

⚠️ 这些接口应在反向代理层加 Token 鉴权（KG_ADMIN_TOKEN）。
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from ..db import get_neo4j_driver, mysql_cursor

router = APIRouter(prefix="/api/admin", tags=["Admin"])

ADMIN_TOKEN = os.environ.get("KG_ADMIN_TOKEN", "")


def _check_token(x_admin_token: Optional[str]) -> None:
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail={
            "code": 503, "message": "Admin disabled (KG_ADMIN_TOKEN not set)"})
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail={
            "code": 401, "message": "Unauthorized"})


WRITABLE_COLS = (
    "title", "period", "type", "material", "description",
    "dimensions", "museum", "location",
    "detail_url", "image_url", "image_path",
    "credit_line", "accession_number",
)


@router.post("/artifacts", summary="新增文物")
def admin_create(payload: dict, x_admin_token: Optional[str] = Header(None)):
    _check_token(x_admin_token)
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
    x_admin_token: Optional[str] = Header(None),
):
    _check_token(x_admin_token)
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
def admin_delete(object_id: str, x_admin_token: Optional[str] = Header(None)):
    _check_token(x_admin_token)
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
def consistency_check(x_admin_token: Optional[str] = Header(None)):
    _check_token(x_admin_token)
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
