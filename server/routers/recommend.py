"""相关文物推荐：同朝代 / 同类型 / 同博物馆 / 视觉相似的混合推荐。

供 Web 子系统"详情页推荐"、移动端"相关文物"使用。
所有响应字段都支持 ?lang=zh|en 切换。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..db import mysql_cursor
from ..utils import (
    build_artifact_list_item,
    get_artifact_row,
    hamming64,
    localize_row,
    normalize_lang,
)

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
    lang: str = Query("zh", pattern="^(zh|en)$"),
):
    base = get_artifact_row(object_id)
    if not base:
        raise HTTPException(status_code=404, detail={
            "code": 404, "message": "Artifact not found"})

    lang = normalize_lang(lang)
    period = (base.get("period") or "").strip()
    period_en = (base.get("period_en") or "").strip()
    typ = (base.get("type") or "").strip()
    typ_en = (base.get("type_en") or "").strip()
    museum = (base.get("museum") or "").strip()
    base_phash = (base.get("phash") or "").strip()

    with mysql_cursor() as cursor:
        if strategy in ("same_period", "mixed") and (period or period_en):
            cursor.execute(
                "SELECT * FROM artifacts WHERE (period = %s OR period_en = %s) "
                "AND object_id <> %s LIMIT 200",
                (period, period_en or period, object_id))
            same_period = cursor.fetchall()
        else:
            same_period = []

        if strategy in ("same_type", "mixed") and (typ or typ_en):
            cursor.execute(
                "SELECT * FROM artifacts WHERE (type = %s OR type_en = %s) "
                "AND object_id <> %s LIMIT 200",
                (typ, typ_en or typ, object_id))
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
        "lang": lang,
        "data": [
            {**build_artifact_list_item(item["row"], lang),
             "score": round(item["score"], 3)}
            for item in ranked
        ],
    }


@router.post(
    "/compare",
    summary="文物对比（2~3 件）",
)
def compare_artifacts(payload: dict, lang: str = Query("zh", pattern="^(zh|en)$")):
    """
    body: {"ids": ["id1","id2","id3"]}
    query: ?lang=zh|en

    返回 2~3 件文物的并排属性，前端可直接渲染对比表格。
    """
    lang = normalize_lang(lang)
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
        r = localize_row(row, lang)
        rows.append({
            "id": r["object_id"],
            "name": r.get("title", ""),
            "thumbnail_url": f"/api/images/{r['object_id']}/thumbnail",
            "period": r.get("period", ""),
            "type": r.get("type", ""),
            "material": r.get("material", ""),
            "dimensions": r.get("dimensions", ""),
            "museum": r.get("museum", ""),
            "location": r.get("location", ""),
            "description": r.get("description", ""),
        })
    return {"lang": lang, "data": rows}
