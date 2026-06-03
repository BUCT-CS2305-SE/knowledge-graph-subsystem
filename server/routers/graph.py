"""知识图谱可视化数据接口：邻居图、朝代展开、地理分布。

供 Web 子系统"力导向图 / 时间轴 / 地图"使用。
所有响应支持 ?lang=zh|en 切换节点 name / 时间轴 period 文本。
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..db import get_neo4j_driver, mysql_cursor
from ..utils import normalize_lang

router = APIRouter(prefix="/api/graph", tags=["Graph"])


def _node_name(props: dict, lang: str) -> str:
    """根据 lang 选择节点显示文本：
       lang=en → name_en / title_en，缺失则回退中文。
    """
    if lang == "en":
        for key in ("name_en", "title_en"):
            v = props.get(key)
            if isinstance(v, str) and v.strip():
                return v
    return props.get("name") or props.get("title") or ""


@router.get("/neighbors/{object_id}", summary="文物的邻居子图（力导向图）")
def get_neighbors(
    object_id: str,
    depth: int = Query(1, ge=1, le=2),
    limit: int = Query(50, ge=1, le=200),
    lang: str = Query("zh", pattern="^(zh|en)$"),
):
    """返回 ECharts/D3 力导向图所需的 nodes + links 结构。"""
    lang = normalize_lang(lang)
    try:
        driver = get_neo4j_driver()
        with driver.session() as session:
            cypher = (
                f"MATCH path = (a:Artifact {{id: $oid}})-[*1..{depth}]-(n) "
                "WITH path LIMIT $lim "
                "UNWIND nodes(path) AS node "
                "WITH collect(distinct node) AS ns, "
                "     collect(distinct relationships(path)) AS rels "
                "RETURN ns, rels"
            )
            result = session.run(cypher, oid=str(object_id), lim=limit).single()
            if not result:
                return {"nodes": [], "links": [], "lang": lang}

            nodes = []
            seen_n = set()
            for n in result["ns"]:
                key = n.element_id if hasattr(n, "element_id") else id(n)
                if key in seen_n:
                    continue
                seen_n.add(key)
                labels = list(n.labels) if hasattr(n, "labels") else []
                props = dict(n)
                nodes.append({
                    "id": props.get("id") or props.get("name") or str(key),
                    "name": _node_name(props, lang),
                    "category": labels[0] if labels else "Entity",
                    "props": props,
                })

            links = []
            seen_l = set()
            for rels in result["rels"]:
                for r in rels:
                    sk = id(r.start_node), id(r.end_node), r.type
                    if sk in seen_l:
                        continue
                    seen_l.add(sk)
                    sn = dict(r.start_node)
                    en = dict(r.end_node)
                    links.append({
                        "source": sn.get("id") or sn.get("name") or "",
                        "target": en.get("id") or en.get("name") or "",
                        "relation": r.type,
                    })
            return {"nodes": nodes, "links": links, "lang": lang}
    except Exception as e:
        raise HTTPException(status_code=503, detail={
            "code": 503, "message": f"Neo4j unavailable: {e}"})


@router.get("/timeline", summary="时间轴：朝代/时期 → 文物分布")
def graph_timeline(
    top_periods: int = Query(20, ge=1, le=100),
    lang: str = Query("zh", pattern="^(zh|en)$"),
):
    """前端时间轴使用。返回每个时期下的代表性文物计数（按 lang 切换 period 列）。"""
    lang = normalize_lang(lang)
    col = "period_en" if lang == "en" else "period"
    with mysql_cursor() as cursor:
        cursor.execute(
            f"SELECT {col} AS name, COUNT(*) AS count "
            f"FROM artifacts WHERE {col} <> '' "
            f"GROUP BY {col} ORDER BY count DESC LIMIT %s",
            (top_periods,),
        )
        rows = cursor.fetchall()
    return {"lang": lang, "data": rows}


@router.get("/geo", summary="地理分布：博物馆 → 馆藏量（地图打点）")
def graph_geo():
    """前端世界地图使用：博物馆所在地 + 藏品数（museum/location 本身就是英文）。"""
    with mysql_cursor() as cursor:
        cursor.execute(
            "SELECT museum AS name, location, COUNT(*) AS count "
            "FROM artifacts WHERE museum <> '' "
            "GROUP BY museum, location ORDER BY count DESC"
        )
        rows = cursor.fetchall()
    return {"data": rows}


@router.get("/path", summary="两实体之间的最短路径（多跳问答用）")
def graph_path(
    src: str = Query(..., description="起点 id（文物/朝代/博物馆 等）"),
    dst: str = Query(...),
    max_depth: int = Query(4, ge=1, le=6),
    lang: str = Query("zh", pattern="^(zh|en)$"),
):
    lang = normalize_lang(lang)
    try:
        driver = get_neo4j_driver()
        with driver.session() as session:
            cypher = (
                "MATCH p = shortestPath((a {id:$src})-[*..%d]-(b {id:$dst})) "
                "RETURN [n IN nodes(p) | {id: n.id, "
                "name: coalesce(n.name, n.title), "
                "name_en: coalesce(n.name_en, n.title_en), "
                "labels: labels(n)}] AS nodes, "
                "[r IN relationships(p) | type(r)] AS rels"
            ) % max_depth
            r = session.run(cypher, src=src, dst=dst).single()
            if not r:
                return {"found": False, "nodes": [], "rels": [], "lang": lang}
            nodes = []
            for n in r["nodes"]:
                en = (n.get("name_en") or "").strip()
                nodes.append({
                    "id": n.get("id"),
                    "name": en if (lang == "en" and en) else n.get("name", ""),
                    "labels": n.get("labels", []),
                })
            return {"found": True, "nodes": nodes, "rels": r["rels"], "lang": lang}
    except Exception as e:
        raise HTTPException(status_code=503, detail={
            "code": 503, "message": f"Neo4j unavailable: {e}"})
