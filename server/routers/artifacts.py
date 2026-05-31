"""文物列表 / 详情 / 单属性查询。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..db import mysql_cursor
from ..utils import (
    build_artifact_list_item,
    build_original_url,
    build_thumbnail_url,
    get_artifact_row,
    get_related_entities,
    localize_row,
    normalize_lang,
    parse_period_year,
)

router = APIRouter(prefix="/api", tags=["MVP"])


@router.get("/artifacts", summary="文物列表查询")
def list_artifacts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    type: Optional[str] = None,
    museum: Optional[str] = None,
    period_from: Optional[int] = None,
    period_to: Optional[int] = None,
    sort_by: str = Query("name", pattern="^(name|period|updated)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    lang: str = Query("zh", pattern="^(zh|en)$",
                      description="返回字段语言：zh=中文（默认），en=英文原文"),
):
    """获取文物列表（分页 + 基础筛选 + 简单排序，支持 ?lang=zh|en）。"""
    lang = normalize_lang(lang)
    base_query = "SELECT * FROM artifacts WHERE 1=1"
    params: list = []
    if type:
        # 同时匹配 type 与 type_en（任一精确匹配即命中）
        base_query += " AND (type = %s OR type_en = %s)"
        params.extend([type, type])
    if museum:
        base_query += " AND museum = %s"
        params.append(museum)

    with mysql_cursor() as cursor:
        if period_from is None and period_to is None:
            count_query = "SELECT COUNT(*) AS total FROM (" + base_query + ") t"
            cursor.execute(count_query, tuple(params))
            total = cursor.fetchone()["total"]

            sort_map = {"name": "title", "period": "period", "updated": "crawl_date"}
            order_clause = "ASC" if order == "asc" else "DESC"
            query = (
                f"{base_query} ORDER BY {sort_map[sort_by]} {order_clause} "
                f"LIMIT %s OFFSET %s"
            )
            cursor.execute(
                query, tuple(params + [page_size, (page - 1) * page_size])
            )
            rows = cursor.fetchall()
        else:
            cursor.execute(base_query, tuple(params))
            rows = cursor.fetchall()

            def in_range(row: dict) -> bool:
                year = parse_period_year(row.get("period", "")) \
                    or parse_period_year(row.get("period_en", ""))
                if year is None:
                    return False
                if period_from is not None and year < period_from:
                    return False
                if period_to is not None and year > period_to:
                    return False
                return True

            rows = [r for r in rows if in_range(r)]
            reverse = order == "desc"
            if sort_by == "name":
                rows.sort(key=lambda r: r.get("title", ""), reverse=reverse)
            elif sort_by == "updated":
                rows.sort(key=lambda r: r.get("crawl_date", ""), reverse=reverse)
            else:
                rows.sort(
                    key=lambda r: (parse_period_year(r.get("period", "")) or 0),
                    reverse=reverse,
                )
            total = len(rows)
            start = (page - 1) * page_size
            rows = rows[start : start + page_size]

    data = [build_artifact_list_item(row, lang) for row in rows]
    return {"page": page, "page_size": page_size, "total": total,
            "lang": lang, "data": data}


@router.get("/artifacts/{object_id}", summary="文物详情查询")
def get_artifact_detail(
    object_id: str,
    lang: str = Query("zh", pattern="^(zh|en)$"),
):
    """获取单件文物详情（含 Neo4j 关联实体；支持 ?lang=zh|en）。"""
    row = get_artifact_row(object_id)
    if not row:
        raise HTTPException(
            status_code=404,
            detail={"code": 404, "message": "Artifact not found"},
        )
    lang = normalize_lang(lang)
    r = localize_row(row, lang)
    return {
        "id": r.get("object_id"),
        "name": r.get("title", ""),
        "period": r.get("period", ""),
        "type": r.get("type", ""),
        "material": r.get("material", ""),
        "description": r.get("description", ""),
        "dimensions": r.get("dimensions", ""),
        "museum": r.get("museum", ""),
        "location": r.get("location", ""),
        "detail_url": r.get("detail_url", ""),
        "image_url": r.get("image_url", ""),
        "image_path": r.get("image_path", ""),
        "credit_line": r.get("credit_line", ""),
        "accession_number": r.get("accession_number", ""),
        "crawl_date": str(r.get("crawl_date", "")),
        "image_original_url": build_original_url(object_id),
        "image_thumbnail_url": build_thumbnail_url(object_id),
        "related_entities": get_related_entities(object_id),
        "lang": lang,
        # 同时回带另一种语言的关键字段，便于前端做"双语对照"
        "i18n": {
            "title_zh": row.get("title", ""),
            "title_en": row.get("title_en", "") or "",
            "period_zh": row.get("period", ""),
            "period_en": row.get("period_en", "") or "",
            "type_zh": row.get("type", ""),
            "type_en": row.get("type_en", "") or "",
            "material_zh": row.get("material", ""),
            "material_en": row.get("material_en", "") or "",
        },
    }


@router.get("/artifacts/{object_id}/property", summary="基础属性查询")
def get_artifact_property(
    object_id: str,
    prop: str = Query(...),
    lang: str = Query("zh", pattern="^(zh|en)$"),
):
    """读取文物的单个属性值，避免问答子系统直接写 Cypher。"""
    lang = normalize_lang(lang)
    # 中文列名 → 英文列名
    en_map = {
        "title": "title_en", "period": "period_en", "type": "type_en",
        "material": "material_en", "description": "description_en",
        "credit_line": "credit_line_en",
    }
    allowed = {
        "museum": "museum",
        "period": "period",
        "material": "material",
        "description": "description",
        "type": "type",
        "location": "location",
        "title": "title",
        "credit_line": "credit_line",
    }
    if prop not in allowed:
        raise HTTPException(
            status_code=400,
            detail={"code": 400, "message": "Unsupported property"},
        )
    column = allowed[prop]
    en_column = en_map.get(prop)
    sel_cols = column if not en_column else f"{column}, {en_column}"
    with mysql_cursor() as cursor:
        cursor.execute(
            f"SELECT {sel_cols} FROM artifacts WHERE object_id = %s",
            (object_id,),
        )
        row = cursor.fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail={"code": 404, "message": "Artifact not found"},
        )
    if lang == "en" and en_column:
        value = (row.get(en_column) or "").strip() or row.get(column, "")
    else:
        value = row.get(column, "")
    return {"id": object_id, "prop": prop, "value": value, "lang": lang}
