"""受限 Cypher / SPARQL-like 接口：供知识问答子系统的 RAG 检索使用。

为安全起见：
- 仅接受白名单"问答模板"，不直接执行用户字符串
- 所有模板均为 MATCH/RETURN 只读
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..db import get_neo4j_driver, mysql_cursor

router = APIRouter(prefix="/api/qa", tags=["QA"])


# 模板：问答子系统通过 intent 字段触发；参数走 params dict 防注入
TEMPLATES: dict[str, str] = {
    # 1. 文物收藏地
    "where_is_artifact":
        "MATCH (a:Artifact {id:$id})-[:STORED_IN]->(m:Museum) "
        "RETURN m.name AS museum, m.location AS location",
    # 2. 文物年代
    "period_of_artifact":
        "MATCH (a:Artifact {id:$id})-[:BELONGS_TO_PERIOD]->(p:Period) "
        "RETURN p.name AS period",
    # 3. 文物材质
    "material_of_artifact":
        "MATCH (a:Artifact {id:$id})-[:MADE_OF]->(m:Material) "
        "RETURN m.name AS material",
    # 4. 文物类型
    "type_of_artifact":
        "MATCH (a:Artifact {id:$id})-[:HAS_TYPE]->(t:Type) "
        "RETURN t.name AS type",
    # 9. 同朝代文物
    "artifacts_of_period":
        "MATCH (a:Artifact)-[:BELONGS_TO_PERIOD]->(p:Period {name:$period}) "
        "RETURN a.id AS id, a.title AS name LIMIT 50",
    # 收藏某类型最多的博物馆
    "top_museum_for_type":
        "MATCH (a:Artifact)-[:HAS_TYPE]->(:Type {name:$type}), "
        "(a)-[:STORED_IN]->(m:Museum) "
        "RETURN m.name AS museum, count(a) AS cnt "
        "ORDER BY cnt DESC LIMIT 1",
}


@router.post("/query", summary="模板化 Cypher 查询（安全白名单）")
def qa_query(payload: dict):
    """
    body 形如：
        {"intent": "where_is_artifact", "params": {"id": "12345"}}
    """
    intent = payload.get("intent")
    params = payload.get("params") or {}
    cypher = TEMPLATES.get(intent)
    if not cypher:
        raise HTTPException(status_code=400, detail={
            "code": 400,
            "message": f"Unknown intent. Available: {list(TEMPLATES)}",
        })
    try:
        driver = get_neo4j_driver()
        with driver.session() as s:
            res = s.run(cypher, **params)
            rows = [dict(r) for r in res]
        return {"intent": intent, "data": rows}
    except Exception as e:
        raise HTTPException(status_code=503, detail={
            "code": 503, "message": f"Neo4j unavailable: {e}"})


@router.get("/intents", summary="列出可用问答意图（前端构建意图分类器用）")
def list_intents():
    return {"intents": list(TEMPLATES.keys())}


@router.get("/grounding/{object_id}", summary="单文物完整事实包（RAG 上下文）")
def grounding_context(object_id: str):
    """
    返回知识图谱中关于该文物的全部事实 + 数据库描述文本。
    问答子系统拿到此包后塞给 LLM 作为上下文，避免幻觉。
    """
    with mysql_cursor() as cur:
        cur.execute("SELECT * FROM artifacts WHERE object_id=%s", (object_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={
            "code": 404, "message": "Artifact not found"})

    facts = []
    try:
        driver = get_neo4j_driver()
        with driver.session() as s:
            cypher = (
                "MATCH (a:Artifact {id:$id})-[r]->(n) "
                "RETURN type(r) AS rel, n.name AS name, labels(n)[0] AS kind"
            )
            for rec in s.run(cypher, id=object_id):
                facts.append({
                    "predicate": rec["rel"],
                    "object": rec["name"],
                    "object_type": rec["kind"],
                })
    except Exception:
        facts = []

    return {
        "id": row["object_id"],
        "title": row.get("title", ""),
        "description": row.get("description", ""),
        "period": row.get("period", ""),
        "type": row.get("type", ""),
        "material": row.get("material", ""),
        "dimensions": row.get("dimensions", ""),
        "museum": row.get("museum", ""),
        "location": row.get("location", ""),
        "source_url": row.get("detail_url", ""),
        "facts": facts,
    }
