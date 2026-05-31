"""检索接口：全文检索 / 高级查询 / 筛选枚举 / 结果导出。"""

from __future__ import annotations

import csv
import io
import json
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import Response

from ..db import mysql_cursor
from ..utils import build_artifact_list_item, parse_period_year

router = APIRouter(prefix="/api", tags=["Search"])


@router.get("/search", summary="全文检索")
def search_artifacts(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """关键字检索文物：title / museum / description。"""
    like_value = f"%{q}%"
    with mysql_cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) AS total FROM artifacts "
            "WHERE title LIKE %s OR museum LIKE %s OR description LIKE %s",
            (like_value, like_value, like_value),
        )
        total = cursor.fetchone()["total"]

        cursor.execute(
            "SELECT * FROM artifacts "
            "WHERE title LIKE %s OR museum LIKE %s OR description LIKE %s "
            "ORDER BY crawl_date DESC LIMIT %s OFFSET %s",
            (like_value, like_value, like_value, page_size, (page - 1) * page_size),
        )
        rows = cursor.fetchall()

    data = [build_artifact_list_item(row) for row in rows]
    return {"page": page, "page_size": page_size, "total": total, "data": data}


@router.get("/search/advanced", summary="高级查询（多字段组合）")
def advanced_search(
    title: Optional[str] = None,
    type: Optional[str] = None,
    museum: Optional[str] = None,
    material: Optional[str] = None,
    location: Optional[str] = None,
    period: Optional[str] = None,
    period_from: Optional[int] = Query(None, description="起始年（公元后正数，公元前负数）"),
    period_to: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    """多字段组合查询，覆盖 Web 高级搜索 + 知识问答的"某朝代瓷器"类问题。"""
    sql = "SELECT * FROM artifacts WHERE 1=1"
    params: list = []
    if title:
        sql += " AND title LIKE %s"
        params.append(f"%{title}%")
    if type:
        sql += " AND type = %s"
        params.append(type)
    if museum:
        sql += " AND museum = %s"
        params.append(museum)
    if material:
        sql += " AND material LIKE %s"
        params.append(f"%{material}%")
    if location:
        sql += " AND location LIKE %s"
        params.append(f"%{location}%")
    if period:
        sql += " AND period LIKE %s"
        params.append(f"%{period}%")

    with mysql_cursor() as cursor:
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()

    if period_from is not None or period_to is not None:
        def in_range(r):
            y = parse_period_year(r.get("period", ""))
            if y is None:
                return False
            if period_from is not None and y < period_from:
                return False
            if period_to is not None and y > period_to:
                return False
            return True
        rows = [r for r in rows if in_range(r)]

    total = len(rows)
    start = (page - 1) * page_size
    page_rows = rows[start:start + page_size]
    data = [build_artifact_list_item(r) for r in page_rows]
    return {"page": page, "page_size": page_size, "total": total, "data": data}


@router.get("/filters", summary="筛选枚举（前端下拉框使用）")
def get_filter_options(top: int = Query(50, ge=1, le=500)):
    """返回各维度的可选值（用于"博物馆/类型/材质"下拉框）。"""
    with mysql_cursor() as cursor:
        out = {}
        for col in ("type", "museum", "period", "material", "location"):
            cursor.execute(
                f"SELECT {col} AS name, COUNT(*) AS count FROM artifacts "
                f"WHERE {col}<>'' GROUP BY {col} ORDER BY count DESC LIMIT %s",
                (top,),
            )
            out[col] = cursor.fetchall()
    return out


@router.get("/search/export", summary="查询结果导出（CSV / JSON）")
def export_search(
    q: Optional[str] = None,
    type: Optional[str] = None,
    museum: Optional[str] = None,
    period: Optional[str] = None,
    format: str = Query("csv", pattern="^(csv|json)$"),
    limit: int = Query(1000, ge=1, le=10000),
):
    """供 Web 端"导出 CSV/JSON"按钮使用。"""
    sql = "SELECT * FROM artifacts WHERE 1=1"
    params: list = []
    if q:
        sql += " AND (title LIKE %s OR museum LIKE %s OR description LIKE %s)"
        like = f"%{q}%"
        params.extend([like, like, like])
    if type:
        sql += " AND type = %s"
        params.append(type)
    if museum:
        sql += " AND museum = %s"
        params.append(museum)
    if period:
        sql += " AND period LIKE %s"
        params.append(f"%{period}%")
    sql += " LIMIT %s"
    params.append(limit)

    with mysql_cursor() as cursor:
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()

    # 序列化日期对象
    for r in rows:
        if r.get("crawl_date"):
            r["crawl_date"] = str(r["crawl_date"])

    if format == "json":
        payload = json.dumps(rows, ensure_ascii=False, indent=2)
        return Response(
            content=payload,
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="artifacts.json"'},
        )

    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="artifacts.csv"'},
    )
