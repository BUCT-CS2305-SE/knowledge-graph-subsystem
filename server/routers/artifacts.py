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
):
    """获取文物列表（分页 + 基础筛选 + 简单排序）。"""
    base_query = "SELECT * FROM artifacts WHERE 1=1"
    params: list = []
    if type:
        base_query += " AND type = %s"
        params.append(type)
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
                year = parse_period_year(row.get("period", ""))
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

    data = [build_artifact_list_item(row) for row in rows]
    return {"page": page, "page_size": page_size, "total": total, "data": data}


@router.get("/artifacts/{object_id}", summary="文物详情查询")
def get_artifact_detail(object_id: str):
    """获取单件文物详情（含 Neo4j 关联实体）。"""
    row = get_artifact_row(object_id)
    if not row:
        raise HTTPException(
            status_code=404,
            detail={"code": 404, "message": "Artifact not found"},
        )
    return {
        "id": row.get("object_id"),
        "name": row.get("title", ""),
        "period": row.get("period", ""),
        "type": row.get("type", ""),
        "material": row.get("material", ""),
        "description": row.get("description", ""),
        "dimensions": row.get("dimensions", ""),
        "museum": row.get("museum", ""),
        "location": row.get("location", ""),
        "detail_url": row.get("detail_url", ""),
        "image_url": row.get("image_url", ""),
        "image_path": row.get("image_path", ""),
        "credit_line": row.get("credit_line", ""),
        "accession_number": row.get("accession_number", ""),
        "crawl_date": str(row.get("crawl_date", "")),
        "image_original_url": build_original_url(object_id),
        "image_thumbnail_url": build_thumbnail_url(object_id),
        "related_entities": get_related_entities(object_id),
    }


@router.get("/artifacts/{object_id}/property", summary="基础属性查询")
def get_artifact_property(object_id: str, prop: str = Query(...)):
    """读取文物的单个属性值，避免问答子系统直接写 Cypher。"""
    allowed = {
        "museum": "museum",
        "period": "period",
        "material": "material",
        "description": "description",
        "type": "type",
        "location": "location",
    }
    if prop not in allowed:
        raise HTTPException(
            status_code=400,
            detail={"code": 400, "message": "Unsupported property"},
        )
    column = allowed[prop]
    with mysql_cursor() as cursor:
        cursor.execute(
            f"SELECT {column} FROM artifacts WHERE object_id = %s",
            (object_id,),
        )
        row = cursor.fetchone()
    if not row:
        raise HTTPException(
            status_code=404,
            detail={"code": 404, "message": "Artifact not found"},
        )
    return {"id": object_id, "prop": prop, "value": row.get(column, "")}
