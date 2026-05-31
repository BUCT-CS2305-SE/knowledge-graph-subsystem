"""统计接口：基础摘要 + 多维分布（供后台仪表盘 + Web 看板）。"""

from __future__ import annotations

from fastapi import APIRouter

from ..db import mysql_cursor

router = APIRouter(prefix="/api/stats", tags=["Stats"])


@router.get("/summary", summary="基础统计数据")
def get_stats_summary():
    """文物总数、类型 / 博物馆 / 时期 Top5。"""
    with mysql_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM artifacts")
        total = cursor.fetchone()["total"]

        cursor.execute(
            "SELECT type AS name, COUNT(*) AS count "
            "FROM artifacts WHERE type<>'' GROUP BY type "
            "ORDER BY count DESC LIMIT 5"
        )
        top_types = cursor.fetchall()

        cursor.execute(
            "SELECT museum AS name, COUNT(*) AS count "
            "FROM artifacts WHERE museum<>'' GROUP BY museum "
            "ORDER BY count DESC LIMIT 5"
        )
        top_museums = cursor.fetchall()

        cursor.execute(
            "SELECT period AS name, COUNT(*) AS count "
            "FROM artifacts WHERE period<>'' GROUP BY period "
            "ORDER BY count DESC LIMIT 5"
        )
        top_periods = cursor.fetchall()

    return {
        "total_artifacts": total,
        "top_types": top_types,
        "top_museums": top_museums,
        "top_periods": top_periods,
    }


@router.get("/distribution", summary="多维分布（供后台仪表盘 / Web 看板）")
def get_distribution():
    """返回 4 个维度的完整分布（去 Top5 限制），用于饼图 / 柱状图。"""
    with mysql_cursor() as cursor:
        cursor.execute(
            "SELECT type AS name, COUNT(*) AS count "
            "FROM artifacts WHERE type<>'' GROUP BY type ORDER BY count DESC"
        )
        types = cursor.fetchall()

        cursor.execute(
            "SELECT museum AS name, COUNT(*) AS count "
            "FROM artifacts WHERE museum<>'' GROUP BY museum ORDER BY count DESC"
        )
        museums = cursor.fetchall()

        cursor.execute(
            "SELECT period AS name, COUNT(*) AS count "
            "FROM artifacts WHERE period<>'' GROUP BY period ORDER BY count DESC"
        )
        periods = cursor.fetchall()

        cursor.execute(
            "SELECT material AS name, COUNT(*) AS count "
            "FROM artifacts WHERE material<>'' GROUP BY material ORDER BY count DESC"
        )
        materials = cursor.fetchall()

    return {
        "types": types,
        "museums": museums,
        "periods": periods,
        "materials": materials,
    }


@router.get("/growth", summary="数据增长趋势（按 crawl_date 聚合）")
def get_growth():
    """供后台监控看板：按 crawl_date 分组的入库增长曲线。"""
    with mysql_cursor() as cursor:
        cursor.execute(
            "SELECT DATE(crawl_date) AS date, COUNT(*) AS count "
            "FROM artifacts WHERE crawl_date IS NOT NULL "
            "GROUP BY DATE(crawl_date) ORDER BY date"
        )
        rows = cursor.fetchall()
    return {"data": [{"date": str(r["date"]), "count": r["count"]} for r in rows]}
