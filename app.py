# app.py
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException as FastAPIHTTPException
import pymysql
import os
import re
from neo4j import GraphDatabase
from typing import Optional

app = FastAPI(
    title="中国海外流失文物知识图谱 API",
    description="提供基于 MySQL 和 Neo4j 的文物检索、关系查询、以及沉浸式主题视图接口。",
    version="1.0.0"
)


@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": str(exc.detail)}
    )

# MySQL 配置
DB_USER = "root"
DB_PASS = "se_jk2305"  # 替换为您实际的密码
DB_HOST = "127.0.0.1"
DB_NAME = "knowledge_graph_db"

# Neo4j 配置
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "se_jk2305" 

def get_mysql_conn():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )


PROJECT_ROOT = os.path.dirname(__file__)
DEFAULT_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='640' height='480' viewBox='0 0 640 480'>"
    "<rect width='100%' height='100%' fill='#f2f2f2'/>"
    "<text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' "
    "font-family='Arial, sans-serif' font-size='24' fill='#666'>No Image</text>"
    "</svg>"
)


def parse_period_year(period_value):
    if not isinstance(period_value, str) or not period_value.strip():
        return None
    value = period_value.replace("–", "-")

    bc_match = re.search(r"(\d{1,4})\s*(BC|BCE)", value, re.IGNORECASE)
    if bc_match:
        return -int(bc_match.group(1))

    year_match = re.search(r"(\d{3,4})", value)
    if year_match:
        return int(year_match.group(1))
    return None


def build_thumbnail_url(object_id):
    return f"/api/images/{object_id}/thumbnail?size=200x200"


def build_original_url(object_id):
    return f"/api/images/{object_id}/original"


def get_artifact_row(object_id):
    conn = get_mysql_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM artifacts WHERE object_id = %s", (object_id,))
    row = cursor.fetchone()
    conn.close()
    return row


def get_related_entities(object_id):
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
        with driver.session() as session:
            cypher = """
                MATCH (a:Artifact {id: $obj_id})-[r]->(connected)
                RETURN type(r) as relation, connected.name as entity_name, labels(connected)[0] as entity_type
            """
            result = session.run(cypher, obj_id=str(object_id))
            relations = [
                {
                    "relation": record["relation"],
                    "name": record["entity_name"],
                    "type": record["entity_type"]
                }
                for record in result
            ]
        driver.close()
        return relations
    except Exception:
        return []


def build_artifact_list_item(row):
    return {
        "id": row.get("object_id"),
        "name": row.get("title", ""),
        "thumbnail_url": build_thumbnail_url(row.get("object_id")),
        "period": row.get("period", ""),
        "museum": {
            "name": row.get("museum", ""),
            "location": row.get("location", "")
        }
    }


@app.get("/api/artifacts", summary="文物列表查询", tags=["MVP"])
def list_artifacts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    type: Optional[str] = None,
    museum: Optional[str] = None,
    period_from: Optional[int] = None,
    period_to: Optional[int] = None,
    sort_by: str = Query("name", pattern="^(name|period|updated)$"),
    order: str = Query("asc", pattern="^(asc|desc)$")
):
    """
    获取文物列表（分页 + 基础筛选 + 简单排序）。

    - 适用场景：列表页/瀑布流、后台浏览
    - 过滤：按文物类型、博物馆、年代范围
    - 排序：名称/年代/更新时间
        - 返回：文物ID、名称、缩略图URL、年代、所属博物馆简要信息

        示例请求：
        - GET /api/artifacts?page=1&page_size=10&type=Ceramics&sort_by=period&order=desc

        示例响应：
        {
            "page": 1,
            "page_size": 10,
            "total": 120,
            "data": [
                {
                    "id": 123,
                    "name": "Tea Bowl",
                    "thumbnail_url": "/api/images/123/thumbnail?size=200x200",
                    "period": "Qing Dynasty (1644-1911)",
                    "museum": {"name": "Art Institute of Chicago", "location": "Chicago, USA"}
                }
            ]
        }
    """
    base_query = "SELECT * FROM artifacts WHERE 1=1"
    params = []

    if type:
        base_query += " AND type = %s"
        params.append(type)
    if museum:
        base_query += " AND museum = %s"
        params.append(museum)

    conn = get_mysql_conn()
    cursor = conn.cursor()

    if period_from is None and period_to is None:
        count_query = "SELECT COUNT(*) AS total FROM (" + base_query + ") t"
        cursor.execute(count_query, tuple(params))
        total = cursor.fetchone()["total"]

        sort_map = {
            "name": "title",
            "period": "period",
            "updated": "crawl_date"
        }
        order_clause = "ASC" if order == "asc" else "DESC"
        query = f"{base_query} ORDER BY {sort_map[sort_by]} {order_clause} LIMIT %s OFFSET %s"
        cursor.execute(query, tuple(params + [page_size, (page - 1) * page_size]))
        rows = cursor.fetchall()
    else:
        cursor.execute(base_query, tuple(params))
        rows = cursor.fetchall()

        def in_range(row):
            year = parse_period_year(row.get("period", ""))
            if year is None:
                return False
            if period_from is not None and year < period_from:
                return False
            if period_to is not None and year > period_to:
                return False
            return True

        rows = [row for row in rows if in_range(row)]

        reverse = order == "desc"
        if sort_by == "name":
            rows.sort(key=lambda r: r.get("title", ""), reverse=reverse)
        elif sort_by == "updated":
            rows.sort(key=lambda r: r.get("crawl_date", ""), reverse=reverse)
        else:
            rows.sort(key=lambda r: (parse_period_year(r.get("period", "")) or 0), reverse=reverse)

        total = len(rows)
        start = (page - 1) * page_size
        rows = rows[start:start + page_size]

    conn.close()

    data = [build_artifact_list_item(row) for row in rows]
    return {"page": page, "page_size": page_size, "total": total, "data": data}


@app.get("/api/artifacts/{object_id}", summary="文物详情查询", tags=["MVP"])
def get_artifact_detail(object_id: str):
    """
    获取单件文物详情。

    - 返回：完整字段 + 图片URL + 关联实体列表（来自 Neo4j）
        - 适用场景：详情页、问答溯源

        示例请求：
        - GET /api/artifacts/123

        示例响应（部分字段）：
        {
            "id": 123,
            "name": "Tea Bowl",
            "period": "Qing Dynasty (1644-1911)",
            "image_original_url": "/api/images/123/original",
            "related_entities": [
                {"relation": "STORED_IN", "name": "Art Institute of Chicago", "type": "Museum"}
            ]
        }

        错误：
        - 404 Artifact not found
    """
    row = get_artifact_row(object_id)
    if not row:
        raise HTTPException(status_code=404, detail={"code": 404, "message": "Artifact not found"})

    detail = {
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
        "related_entities": get_related_entities(object_id)
    }
    return detail


@app.get("/api/search", summary="全文检索", tags=["MVP"])
def search_artifacts(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200)
):
    """
    关键字检索文物。

    - 检索范围：文物名称、博物馆名称、描述文本
    - 支持分页
        - 返回：文物列表（同列表接口）

        示例请求：
        - GET /api/search?q=porcelain&page=1&page_size=20

        示例响应：
        {
            "page": 1,
            "page_size": 20,
            "total": 42,
            "data": [
                {"id": 456, "name": "Tea Bowl", "thumbnail_url": "/api/images/456/thumbnail?size=200x200"}
            ]
        }
    """
    like_value = f"%{q}%"

    conn = get_mysql_conn()
    cursor = conn.cursor()
    count_sql = (
        "SELECT COUNT(*) AS total FROM artifacts "
        "WHERE title LIKE %s OR museum LIKE %s OR description LIKE %s"
    )
    cursor.execute(count_sql, (like_value, like_value, like_value))
    total = cursor.fetchone()["total"]

    sql = (
        "SELECT * FROM artifacts "
        "WHERE title LIKE %s OR museum LIKE %s OR description LIKE %s "
        "ORDER BY crawl_date DESC LIMIT %s OFFSET %s"
    )
    cursor.execute(sql, (like_value, like_value, like_value, page_size, (page - 1) * page_size))
    rows = cursor.fetchall()
    conn.close()

    data = [build_artifact_list_item(row) for row in rows]
    return {"page": page, "page_size": page_size, "total": total, "data": data}


def resolve_image_path(object_id):
    row = get_artifact_row(object_id)
    if not row:
        return None
    image_path = row.get("image_path", "")
    if not image_path:
        return None
    abs_path = os.path.join(PROJECT_ROOT, image_path)
    if os.path.exists(abs_path):
        return abs_path
    return None


@app.get("/api/images/{object_id}/original", summary="原始图片", tags=["MVP"])
def get_image_original(object_id: str):
    """
    获取原始图片（二进制流）。

    - 若本地无图，返回默认占位图
    - 启用缓存控制

    示例请求：
    - GET /api/images/123/original

    响应：image/jpeg 或 image/svg+xml
    """
    image_path = resolve_image_path(object_id)
    headers = {"Cache-Control": "public, max-age=86400"}
    if image_path:
        return FileResponse(image_path, headers=headers)
    return Response(content=DEFAULT_SVG, media_type="image/svg+xml", headers=headers)


@app.get("/api/images/{object_id}/thumbnail", summary="缩略图", tags=["MVP"])
def get_image_thumbnail(object_id: str, size: str = Query("200x200")):
    """
    获取缩略图（二进制流）。

    - size 参数仅用于客户端标记，MVP 返回同一图片
    - 若本地无图，返回默认占位图
    - 启用缓存控制

    示例请求：
    - GET /api/images/123/thumbnail?size=200x200

    响应：image/jpeg 或 image/svg+xml
    """
    image_path = resolve_image_path(object_id)
    headers = {"Cache-Control": "public, max-age=86400"}
    if image_path:
        return FileResponse(image_path, headers=headers)
    return Response(content=DEFAULT_SVG, media_type="image/svg+xml", headers=headers)


@app.get("/api/artifacts/{object_id}/property", summary="基础属性查询", tags=["MVP"])
def get_artifact_property(object_id: str, prop: str = Query(...)):
    """
    读取文物的单个属性值。

    - 避免问答子系统直接写 Cypher
    - prop 示例：museum, period, material, description, type, location

    示例请求：
    - GET /api/artifacts/123/property?prop=period

    示例响应：
    {"id": "123", "prop": "period", "value": "Qing Dynasty (1644-1911)"}

    错误：
    - 400 Unsupported property
    - 404 Artifact not found
    """
    allowed = {
        "museum": "museum",
        "period": "period",
        "material": "material",
        "description": "description",
        "type": "type",
        "location": "location"
    }
    if prop not in allowed:
        raise HTTPException(status_code=400, detail={"code": 400, "message": "Unsupported property"})

    conn = get_mysql_conn()
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT {allowed[prop]} FROM artifacts WHERE object_id = %s",
        (object_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail={"code": 404, "message": "Artifact not found"})

    return {"id": object_id, "prop": prop, "value": row.get(allowed[prop], "")}


@app.get("/api/stats/summary", summary="基础统计数据", tags=["MVP"])
def get_stats_summary():
    """
    提供最小统计摘要。

    - 文物总数
    - 类型 Top5
    - 博物馆 Top5
        - 朝代/时期 Top5

        示例请求：
        - GET /api/stats/summary

        示例响应：
        {
            "total_artifacts": 1000,
            "top_types": [{"name": "Ceramics", "count": 320}],
            "top_museums": [{"name": "Art Institute of Chicago", "count": 1000}],
            "top_periods": [{"name": "Qing Dynasty (1644-1911)", "count": 420}]
        }
    """
    conn = get_mysql_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM artifacts")
    total = cursor.fetchone()["total"]

    cursor.execute(
        "SELECT type AS name, COUNT(*) AS count "
        "FROM artifacts GROUP BY type ORDER BY count DESC LIMIT 5"
    )
    top_types = cursor.fetchall()

    cursor.execute(
        "SELECT museum AS name, COUNT(*) AS count "
        "FROM artifacts GROUP BY museum ORDER BY count DESC LIMIT 5"
    )
    top_museums = cursor.fetchall()

    cursor.execute(
        "SELECT period AS name, COUNT(*) AS count "
        "FROM artifacts GROUP BY period ORDER BY count DESC LIMIT 5"
    )
    top_periods = cursor.fetchall()

    conn.close()

    return {
        "total_artifacts": total,
        "top_types": top_types,
        "top_museums": top_museums,
        "top_periods": top_periods
    }