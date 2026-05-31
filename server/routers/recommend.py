"""相关文物推荐：同朝代 / 同类型 / 同博物馆 / 视觉相似的混合推荐。

供 Web 子系统"详情页推荐"、移动端"相关文物"使用。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..db import mysql_cursor
from ..utils import build_artifact_list_item, get_artifact_row, hamming64

router = APIRouter(prefix="/api/artifacts", tags=["Recommend"])


@router.get(
    "/{object_id}/related",
    summary="相关文物推荐（同朝代+同类型+视觉相似的混合）",
)
def recommend_related(
    object_id: str,
    top_k: int = Query(8, ge=1, le=50),
    strategy: str = Query(
        "mixed", pattern="^(mixed|same_period|same_type|same_museum|visual)$"
    ),
):
    base = get_artifact_row(object_id)
    if not base:
        raise HTTPException(status_code=404, detail={
            "code": 404, "message": "Artifact not found"})

    period = (base.get("period") or "").strip()
    typ = (base.get("type") or "").strip()
    museum = (base.get("museum") or "").strip()
    base_phash = (base.get("phash") or "").strip()

    with mysql_cursor() as cursor:
        if strategy in ("same_period", "mixed") and period:
            cursor.execute(
                "SELECT * FROM artifacts WHERE period = %s AND object_id <> %s "
                "LIMIT 200", (period, object_id))
            same_period = cursor.fetchall()
        else:
            same_period = []

        if strategy in ("same_type", "mixed") and typ:
            cursor.execute(
                "SELECT * FROM artifacts WHERE type = %s AND object_id <> %s "
                "LIMIT 200", (typ, object_id))
            same_type = cursor.fetchall()
        else:
            same_type = []

        if strategy == "same_museum" and museum:
            cursor.execute(
                "SELECT * FROM artifacts WHERE museum = %s AND object_id <> %s "
                "LIMIT 200", (museum, object_id))
            same_museum = cursor.fetchall()
        else:
            same_museum = []

        if strategy in ("visual", "mixed") and base_phash:
            cursor.execute(
                "SELECT * FROM artifacts WHERE phash <> '' AND object_id <> %s",
                (object_id,))
            with_phash = cursor.fetchall()
        else:
            with_phash = []

    # 评分：每条候选记得分（同朝代+1, 同类型+1, 同博物馆+0.5, 视觉相似度 0~1）
    scored: dict[str, dict] = {}

    def add(rows: list[dict], weight: float):
        for r in rows:
            oid = r["object_id"]
            if oid not in scored:
                scored[oid] = {"row": r, "score": 0.0}
            scored[oid]["score"] += weight

    if strategy == "same_museum":
        add(same_museum, 1.0)
    else:
        add(same_period, 1.0)
        add(same_type, 1.0)
        # 视觉相似（基于 pHash）
        if base_phash:
            for r in with_phash:
                d = hamming64(base_phash, r.get("phash") or "")
                if d <= 16:
                    sim = 1 - d / 64.0
                    oid = r["object_id"]
                    if oid not in scored:
                        scored[oid] = {"row": r, "score": 0.0}
                    scored[oid]["score"] += sim

    ranked = sorted(scored.values(), key=lambda x: x["score"], reverse=True)[:top_k]
    return {
        "base_id": object_id,
        "strategy": strategy,
        "data": [
            {**build_artifact_list_item(item["row"]), "score": round(item["score"], 3)}
            for item in ranked
        ],
    }


@router.post(
    "/compare",
    summary="文物对比（2~3 件）",
)
def compare_artifacts(payload: dict):
    """
    body: {"ids": ["id1","id2","id3"]}

    返回 2~3 件文物的并排属性，前端可直接渲染对比表格。
    """
    ids = payload.get("ids") or []
    if not (2 <= len(ids) <= 3):
        raise HTTPException(status_code=400, detail={
            "code": 400, "message": "ids must contain 2 or 3 elements"})

    rows: list[dict] = []
    for oid in ids:
        row = get_artifact_row(oid)
        if not row:
            raise HTTPException(status_code=404, detail={
                "code": 404, "message": f"Artifact {oid} not found"})
        rows.append({
            "id": row["object_id"],
            "name": row.get("title", ""),
            "thumbnail_url": f"/api/images/{row['object_id']}/thumbnail",
            "period": row.get("period", ""),
            "type": row.get("type", ""),
            "material": row.get("material", ""),
            "dimensions": row.get("dimensions", ""),
            "museum": row.get("museum", ""),
            "location": row.get("location", ""),
            "description": row.get("description", ""),
        })
    return {"data": rows}
