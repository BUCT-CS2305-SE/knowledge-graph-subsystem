"""检索接口：全文检索 / 高级查询 / 筛选枚举 / 结果导出。

所有读接口支持 ?lang=zh|en，返回字段会按语言切换；
检索 LIKE 默认同时扫描中文 + 英文列，因此 zh / en 关键字都能命中。
"""

from __future__ import annotations

import csv
import io
import json
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import Response

from ..db import mysql_cursor
from ..utils import (
    build_artifact_list_item,
    localize_row,
    normalize_lang,
    parse_period_year,
)

router = APIRouter(prefix="/api", tags=["Search"])


@router.get("/search", summary="全文检索（中英双语）")
def search_artifacts(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    lang: str = Query("zh", pattern="^(zh|en)$"),
):
    """关键字检索文物：title / museum / description / *_en（中英双语模糊匹配）。"""
    lang = normalize_lang(lang)
    like_value = f"%{q}%"
    where = (
        "title LIKE %s OR title_en LIKE %s "
        "OR museum LIKE %s "
        "OR description LIKE %s OR description_en LIKE %s"
    )
    params = (like_value,) * 5
    with mysql_cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) AS total FROM artifacts WHERE {where}", params)
        total = cursor.fetchone()["total"]

        cursor.execute(
            f"SELECT * FROM artifacts WHERE {where} "
            f"ORDER BY crawl_date DESC LIMIT %s OFFSET %s",
            params + (page_size, (page - 1) * page_size),
        )
        rows = cursor.fetchall()

    data = [build_artifact_list_item(row, lang) for row in rows]
    return {"page": page, "page_size": page_size, "total": total,
            "lang": lang, "data": data}


@router.get("/search/advanced", summary="高级查询（多字段组合，中英双语）")
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
    lang: str = Query("zh", pattern="^(zh|en)$"),
):
    """多字段组合查询；每个文本字段都对中英两列各做一次 LIKE。"""
    lang = normalize_lang(lang)
    sql = "SELECT * FROM artifacts WHERE 1=1"
    params: list = []

    def _add_bilingual_like(zh_col: str, en_col: str | None, value: str) -> None:
        nonlocal sql
        if en_col:
            sql += f" AND ({zh_col} LIKE %s OR {en_col} LIKE %s)"
            params.extend([f"%{value}%", f"%{value}%"])
        else:
            sql += f" AND {zh_col} LIKE %s"
            params.append(f"%{value}%")

    if title:
        _add_bilingual_like("title", "title_en", title)
    if type:
        _add_bilingual_like("type", "type_en", type)
    if museum:
        _add_bilingual_like("museum", None, museum)
    if material:
        _add_bilingual_like("material", "material_en", material)
    if location:
        _add_bilingual_like("location", None, location)
    if period:
        _add_bilingual_like("period", "period_en", period)

    with mysql_cursor() as cursor:
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()

    if period_from is not None or period_to is not None:
        def in_range(r):
            y = parse_period_year(r.get("period", "")) \
                or parse_period_year(r.get("period_en", ""))
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
    data = [build_artifact_list_item(r, lang) for r in page_rows]
    return {"page": page, "page_size": page_size, "total": total,
            "lang": lang, "data": data}


@router.get("/filters", summary="筛选枚举（前端下拉框使用）")
def get_filter_options(
    top: int = Query(50, ge=1, le=500),
    lang: str = Query("zh", pattern="^(zh|en)$"),
):
    """返回各维度的可选值。lang=en 时优先取 *_en 列；空值会回退到中文列。"""
    lang = normalize_lang(lang)
    # 列映射：lang=en 时尽量走英文列，无英文列（museum/location）保持原列
    col_map = {
        "type":     ("type_en"     if lang == "en" else "type"),
        "museum":   "museum",
        "period":   ("period_en"   if lang == "en" else "period"),
        "material": ("material_en" if lang == "en" else "material"),
        "location": "location",
    }
    with mysql_cursor() as cursor:
        out = {}
        for key, col in col_map.items():
            cursor.execute(
                f"SELECT {col} AS name, COUNT(*) AS count FROM artifacts "
                f"WHERE {col}<>'' GROUP BY {col} ORDER BY count DESC LIMIT %s",
                (top,),
            )
            out[key] = cursor.fetchall()
    return {"lang": lang, **out}


@router.get("/search/export", summary="查询结果导出（CSV / JSON，中英双语）")
def export_search(
    q: Optional[str] = None,
    type: Optional[str] = None,
    museum: Optional[str] = None,
    period: Optional[str] = None,
    format: str = Query("csv", pattern="^(csv|json)$"),
    limit: int = Query(1000, ge=1, le=10000),
    lang: str = Query("zh", pattern="^(zh|en)$",
                      description="导出时主字段使用的语言；同时附加另一语言列"),
):
    """供 Web 端"导出 CSV/JSON"按钮使用。"""
    lang = normalize_lang(lang)
    sql = "SELECT * FROM artifacts WHERE 1=1"
    params: list = []
    if q:
        sql += (
            " AND (title LIKE %s OR title_en LIKE %s "
            "OR museum LIKE %s "
            "OR description LIKE %s OR description_en LIKE %s)"
        )
        like = f"%{q}%"
        params.extend([like, like, like, like, like])
    if type:
        sql += " AND (type = %s OR type_en = %s)"
        params.extend([type, type])
    if museum:
        sql += " AND museum = %s"
        params.append(museum)
    if period:
        sql += " AND (period LIKE %s OR period_en LIKE %s)"
        params.extend([f"%{period}%", f"%{period}%"])
    sql += " LIMIT %s"
    params.append(limit)

    with mysql_cursor() as cursor:
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()

    # 序列化日期对象 + 按 lang 切换主列
    out_rows = []
    for r in rows:
        if r.get("crawl_date"):
            r["crawl_date"] = str(r["crawl_date"])
        out_rows.append(localize_row(r, lang))

    if format == "json":
        payload = json.dumps(out_rows, ensure_ascii=False, indent=2)
        return Response(
            content=payload,
            media_type="application/json",
            headers={"Content-Disposition":
                     f'attachment; filename="artifacts_{lang}.json"'},
        )

    buf = io.StringIO()
    if out_rows:
        writer = csv.DictWriter(buf, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition":
                 f'attachment; filename="artifacts_{lang}.csv"'},
    )
