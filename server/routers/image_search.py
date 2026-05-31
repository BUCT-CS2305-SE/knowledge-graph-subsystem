"""以图搜图 + 以文搜图。

策略：
- model=auto（默认）：CLIP 可用且索引已构建 → CLIP；否则 pHash
- model=clip       ：强制 CLIP，缺依赖时 503
- model=phash      ：强制 pHash
- /text 端点：仅 CLIP（语义跨模态），失败 503
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from .. import vector_search
from ..db import mysql_cursor
from ..utils import (
    build_thumbnail_url,
    compute_phash,
    hamming64,
)

router = APIRouter(prefix="/api/image-search", tags=["ImageSearch"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


# ---------- 共享：MySQL 行 → 列表项 ----------

def _row_to_item(row: dict, score: float) -> dict:
    return {
        "id": row["object_id"],
        "name": row.get("title", ""),
        "thumbnail_url": build_thumbnail_url(row["object_id"]),
        "period": row.get("period", ""),
        "museum": {
            "name": row.get("museum", ""),
            "location": row.get("location", ""),
        },
        "score": round(score, 4),
    }


def _fetch_rows_by_ids(ids: list[str]) -> dict[str, dict]:
    if not ids:
        return {}
    placeholders = ",".join(["%s"] * len(ids))
    with mysql_cursor() as cursor:
        cursor.execute(
            f"SELECT object_id, title, period, museum, location "
            f"FROM artifacts WHERE object_id IN ({placeholders})",
            tuple(ids),
        )
        return {r["object_id"]: r for r in cursor.fetchall()}


# ---------- pHash 兜底 ----------

def _phash_search(query_hash: str, top_k: int, threshold: int,
                  exclude_id: str | None = None) -> list[dict]:
    with mysql_cursor() as cursor:
        if exclude_id:
            cursor.execute(
                "SELECT object_id, title, period, museum, location, phash "
                "FROM artifacts WHERE phash <> '' AND object_id <> %s",
                (exclude_id,),
            )
        else:
            cursor.execute(
                "SELECT object_id, title, period, museum, location, phash "
                "FROM artifacts WHERE phash <> ''"
            )
        rows = cursor.fetchall()

    scored: list[tuple[int, dict]] = []
    for row in rows:
        d = hamming64(query_hash, row["phash"])
        if d <= threshold:
            scored.append((d, row))
    scored.sort(key=lambda x: x[0])
    return [
        {**_row_to_item(r, 1 - d / 64.0), "hamming": d}
        for d, r in scored[:top_k]
    ]


# ---------- API ----------

@router.get("/status", summary="检索引擎状态（前端可探测启用 CLIP 与否）")
def status():
    return {
        "clip_available": vector_search.is_available(),
        "clip_index_size": vector_search.index_size(),
        "fallback": "phash",
    }


@router.post("", summary="以图搜图（上传图片，CLIP 优先 / pHash 兜底）")
async def search_by_image(
    file: UploadFile = File(...),
    top_k: int = Query(20, ge=1, le=100),
    threshold: int = Query(20, ge=0, le=64,
                           description="pHash 模式下 Hamming 距离阈值"),
    model: str = Query("auto", pattern="^(auto|clip|phash)$"),
):
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail={
            "code": 413, "message": "Image too large (>10MB)"})

    # 决策：使用 CLIP 还是 pHash
    use_clip = (
        model == "clip"
        or (model == "auto"
            and vector_search.is_available()
            and vector_search.index_size() > 0)
    )

    if use_clip:
        vec = vector_search.encode_image_bytes(raw)
        if vec is None:
            if model == "clip":
                raise HTTPException(status_code=503, detail={
                    "code": 503, "message": "CLIP unavailable"})
            use_clip = False  # 自动降级
        else:
            hits = vector_search.search_vector(vec, top_k=top_k)
            if not hits and model == "clip":
                raise HTTPException(status_code=503, detail={
                    "code": 503, "message": "CLIP index empty"})
            if hits:
                rows = _fetch_rows_by_ids([oid for oid, _ in hits])
                data = [
                    _row_to_item(rows[oid], score)
                    for oid, score in hits if oid in rows
                ]
                return {
                    "engine": "clip",
                    "matched": len(data),
                    "data": data,
                }
            # 索引为空且 model=auto → 走 pHash

    # pHash 模式
    query_hash = compute_phash(raw)
    if not query_hash:
        raise HTTPException(status_code=400, detail={
            "code": 400, "message": "Cannot decode image"})
    data = _phash_search(query_hash, top_k, threshold)
    return {
        "engine": "phash",
        "query_phash": query_hash,
        "matched": len(data),
        "data": data,
    }


@router.post("/text", summary="以文搜图（CLIP 跨模态，需要安装 torch）")
def search_by_text(
    text: str = Form(..., min_length=1),
    top_k: int = Query(20, ge=1, le=100),
):
    if not (vector_search.is_available() and vector_search.index_size() > 0):
        raise HTTPException(status_code=503, detail={
            "code": 503,
            "message": "CLIP not ready: install torch/transformers/faiss-cpu "
                       "and run db/clip_indexer.py",
        })
    vec = vector_search.encode_text(text)
    if vec is None:
        raise HTTPException(status_code=503, detail={
            "code": 503, "message": "CLIP encode failed"})
    hits = vector_search.search_vector(vec, top_k=top_k)
    rows = _fetch_rows_by_ids([oid for oid, _ in hits])
    data = [
        _row_to_item(rows[oid], score)
        for oid, score in hits if oid in rows
    ]
    return {"engine": "clip", "query_text": text, "matched": len(data), "data": data}


@router.get("/by-id/{object_id}", summary="基于已有文物 id 找视觉相似")
def search_by_artifact_id(
    object_id: str,
    top_k: int = Query(10, ge=1, le=50),
    model: str = Query("auto", pattern="^(auto|clip|phash)$"),
):
    """基于已有文物找视觉/语义相似品。优先 CLIP，pHash 兜底。"""
    use_clip = (
        model == "clip"
        or (model == "auto"
            and vector_search.is_available()
            and vector_search.index_size() > 0)
    )

    if use_clip:
        # 用图片重算特征（避免再额外存特征列）
        from ..utils import resolve_image_path  # 局部 import 避免循环

        img_path = resolve_image_path(object_id)
        if img_path:
            try:
                with open(img_path, "rb") as f:
                    raw = f.read()
            except Exception:
                raw = b""
            if raw:
                vec = vector_search.encode_image_bytes(raw)
                if vec is not None:
                    hits = vector_search.search_vector(vec, top_k=top_k + 1)
                    hits = [(oid, s) for oid, s in hits if oid != object_id][:top_k]
                    rows = _fetch_rows_by_ids([oid for oid, _ in hits])
                    return {
                        "engine": "clip",
                        "data": [
                            _row_to_item(rows[oid], s)
                            for oid, s in hits if oid in rows
                        ],
                    }
        if model == "clip":
            raise HTTPException(status_code=404, detail={
                "code": 404, "message": "Artifact image not found"})

    # pHash fallback
    with mysql_cursor() as cursor:
        cursor.execute(
            "SELECT phash FROM artifacts WHERE object_id = %s", (object_id,)
        )
        row = cursor.fetchone()
        if not row or not row.get("phash"):
            raise HTTPException(status_code=404, detail={
                "code": 404, "message": "Artifact has no phash"})
    data = _phash_search(row["phash"], top_k, threshold=64,
                        exclude_id=object_id)
    return {"engine": "phash", "data": data}
