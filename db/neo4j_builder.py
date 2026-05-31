"""
Neo4j 知识图谱构建器：把 alignment 输出与 enrichment 结果写入 Neo4j。

实体类型（参考 CIDOC-CRM）：
    Artifact  ↔ E22 Human-Made Object
    Museum    ↔ E40 Legal Body
    Period    ↔ E4  Period
    Type      ↔ E55 Type
    Material  ↔ E57 Material

关系类型：
    (Artifact)-[:STORED_IN]->(Museum)
    (Artifact)-[:BELONGS_TO_PERIOD]->(Period)
    (Artifact)-[:HAS_TYPE]->(Type)
    (Artifact)-[:MADE_OF]->(Material)

数据来源：
    必需：
        data_processing/alignment/nodes_artworks.csv
        data_processing/alignment/nodes_museums.csv
        data_processing/alignment/nodes_periods.csv
        data_processing/alignment/nodes_types.csv
        data_processing/alignment/nodes_materials.csv
        data_processing/alignment/relationships_artwork_museum.csv
        data_processing/alignment/relationships_artwork_period.csv
        data_processing/alignment/relationships_artwork_type.csv
        data_processing/alignment/relationships_artwork_material.csv
    可选：
        data_update/enrichment/augmented_entities.json
        ／ enrichment/augmented_entities.json （兼容旧路径）

CLI：
    python3 db/neo4j_builder.py
    python3 db/neo4j_builder.py --reset            # 先清空再重建
    python3 db/neo4j_builder.py --skip-enrichment  # 不写入补充属性

环境变量：KG_NEO4J_URI / KG_NEO4J_USER / KG_NEO4J_PASSWORD
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Iterable

try:
    from neo4j import GraphDatabase
except ImportError:  # pragma: no cover
    print("ERROR: 请先安装 neo4j 驱动 -> pip install neo4j", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[1]
ALIGN_DIR = ROOT / "data_processing" / "alignment"

ENRICH_CANDIDATES = [
    ROOT / "data_update" / "enrichment" / "augmented_entities.json",
    ROOT / "enrichment" / "augmented_entities.json",
]


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def get_driver():
    uri = _env("KG_NEO4J_URI", "bolt://localhost:7687")
    user = _env("KG_NEO4J_USER", "neo4j")
    pwd = _env("KG_NEO4J_PASSWORD", "")
    return GraphDatabase.driver(uri, auth=(user, pwd))


# ---------------------- 通用 ----------------------

def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def chunked(seq: list, size: int) -> Iterable[list]:
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


# ---------------------- 节点 / 关系写入 ----------------------

CONSTRAINTS = [
    "CREATE CONSTRAINT artifact_id IF NOT EXISTS FOR (a:Artifact) REQUIRE a.id IS UNIQUE",
    "CREATE CONSTRAINT museum_name IF NOT EXISTS FOR (m:Museum)   REQUIRE m.name IS UNIQUE",
    "CREATE CONSTRAINT period_name IF NOT EXISTS FOR (p:Period)   REQUIRE p.name IS UNIQUE",
    "CREATE CONSTRAINT type_name   IF NOT EXISTS FOR (t:Type)     REQUIRE t.name IS UNIQUE",
    "CREATE CONSTRAINT material_name IF NOT EXISTS FOR (x:Material) REQUIRE x.name IS UNIQUE",
]


def setup_schema(session) -> None:
    for stmt in CONSTRAINTS:
        try:
            session.run(stmt)
        except Exception as exc:  # 旧版 Neo4j 语法兼容（极少见）
            print(f"[neo4j] constraint warning: {exc}")


def reset_graph(session) -> None:
    print("[neo4j] DETACH DELETE all nodes ...")
    session.run("MATCH (n) DETACH DELETE n")


def merge_artifacts(session, rows: list[dict], batch: int = 500) -> int:
    cypher = (
        "UNWIND $rows AS r "
        "MERGE (a:Artifact {id: r.id}) "
        "SET a.title = r.title, "
        "    a.description = r.description, "
        "    a.dimensions = r.dimensions, "
        "    a.accession_number = r.accession_number, "
        "    a.detail_url = r.detail_url, "
        "    a.image_url = r.image_url, "
        "    a.quality_score = r.quality_score"
    )
    payload = []
    for r in rows:
        oid = (r.get("object_id") or "").strip()
        if not oid:
            continue
        payload.append({
            "id": oid,
            "title": r.get("title", "") or "",
            "description": r.get("description", "") or "",
            "dimensions": r.get("dimensions", "") or "",
            "accession_number": r.get("accession_number", "") or "",
            "detail_url": r.get("detail_url", "") or "",
            "image_url": r.get("image_url", "") or "",
            "quality_score": r.get("data_quality_score", "") or "",
        })
    total = 0
    for chunk in chunked(payload, batch):
        session.run(cypher, rows=chunk)
        total += len(chunk)
    return total


def merge_simple_nodes(session, label: str, rows: list[dict],
                       extra_props: list[str] | None = None) -> int:
    extra_props = extra_props or []
    set_clause = ""
    if extra_props:
        set_clause = ", ".join(f"n.{p} = r.{p}" for p in extra_props)
        set_clause = " SET " + set_clause
    cypher = (
        f"UNWIND $rows AS r MERGE (n:{label} {{name: r.name}})"
        f"{set_clause}"
    )
    payload = []
    for r in rows:
        name = (r.get("name") or "").strip()
        if not name:
            continue
        item = {"name": name}
        for p in extra_props:
            item[p] = (r.get(p) or "").strip()
        payload.append(item)
    total = 0
    for chunk in chunked(payload, 500):
        session.run(cypher, rows=chunk)
        total += len(chunk)
    return total


def merge_relationships(
    session,
    rel_type: str,
    target_label: str,
    target_key: str,            # CSV 列名，如 aligned_museum
    rows: list[dict],
) -> int:
    cypher = (
        "UNWIND $rows AS r "
        "MATCH (a:Artifact {id: r.id}) "
        f"MERGE (b:{target_label} {{name: r.target}}) "
        f"MERGE (a)-[:{rel_type}]->(b)"
    )
    payload = []
    for r in rows:
        oid = (r.get("object_id") or "").strip()
        target = (r.get(target_key) or "").strip()
        if not oid or not target:
            continue
        payload.append({"id": oid, "target": target})
    total = 0
    for chunk in chunked(payload, 500):
        session.run(cypher, rows=chunk)
        total += len(chunk)
    return total


# ---------------------- enrichment ----------------------

def find_enrichment_path() -> Path | None:
    for p in ENRICH_CANDIDATES:
        if p.exists():
            return p
    return None


KIND_TO_LABEL = {
    "period": "Period",
    "museum": "Museum",
    "type": "Type",
    "material": "Material",
}


def apply_enrichment(session, path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cypher = (
        "UNWIND $rows AS r "
        f"MERGE (n) "  # placeholder, replaced below per kind
    )
    grouped: dict[str, list[dict]] = {}
    for item in payload:
        label = KIND_TO_LABEL.get(item.get("kind", ""))
        if not label:
            continue
        grouped.setdefault(label, []).append({
            "name": item.get("name", "") or "",
            "uri": item.get("uri", "") or "",
            "description": item.get("description", "") or "",
            "source": item.get("source", "") or "",
            "source_url": item.get("source_url", "") or "",
            "enrich_date": item.get("enrich_date", "") or "",
        })

    total = 0
    for label, items in grouped.items():
        cy = (
            f"UNWIND $rows AS r "
            f"MERGE (n:{label} {{name: r.name}}) "
            "SET n.uri = r.uri, "
            "    n.description = r.description, "
            "    n.source = r.source, "
            "    n.source_url = r.source_url, "
            "    n.enrich_date = r.enrich_date"
        )
        for chunk in chunked(items, 500):
            session.run(cy, rows=chunk)
            total += len(chunk)
    return total


# ---------------------- 主流程 ----------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Neo4j 知识图谱构建")
    parser.add_argument("--reset", action="store_true", help="先清空全图再重建")
    parser.add_argument("--skip-enrichment", action="store_true",
                        help="不写入 augmented_entities.json")
    args = parser.parse_args(argv)

    if not ALIGN_DIR.exists():
        print(f"[neo4j] alignment 目录不存在: {ALIGN_DIR}", file=sys.stderr)
        return 1

    artworks = read_csv(ALIGN_DIR / "nodes_artworks.csv")
    museums = read_csv(ALIGN_DIR / "nodes_museums.csv")
    periods = read_csv(ALIGN_DIR / "nodes_periods.csv")
    types = read_csv(ALIGN_DIR / "nodes_types.csv")
    materials = read_csv(ALIGN_DIR / "nodes_materials.csv")
    rel_museum = read_csv(ALIGN_DIR / "relationships_artwork_museum.csv")
    rel_period = read_csv(ALIGN_DIR / "relationships_artwork_period.csv")
    rel_type = read_csv(ALIGN_DIR / "relationships_artwork_type.csv")
    rel_material = read_csv(ALIGN_DIR / "relationships_artwork_material.csv")

    print(f"[neo4j] artifacts={len(artworks)} museums={len(museums)} "
          f"periods={len(periods)} types={len(types)} materials={len(materials)}")

    driver = get_driver()
    try:
        with driver.session() as session:
            setup_schema(session)
            if args.reset:
                reset_graph(session)

            n_a = merge_artifacts(session, artworks)
            n_m = merge_simple_nodes(session, "Museum", museums, ["location"])
            n_p = merge_simple_nodes(session, "Period", periods, ["era"])
            n_t = merge_simple_nodes(session, "Type", types, ["category", "subcategory"])
            n_x = merge_simple_nodes(session, "Material", materials, ["category"])
            print(f"[neo4j] nodes upserted: Artifact={n_a} Museum={n_m} "
                  f"Period={n_p} Type={n_t} Material={n_x}")

            r1 = merge_relationships(session, "STORED_IN", "Museum",
                                     "aligned_museum", rel_museum)
            r2 = merge_relationships(session, "BELONGS_TO_PERIOD", "Period",
                                     "aligned_period", rel_period)
            r3 = merge_relationships(session, "HAS_TYPE", "Type",
                                     "aligned_type", rel_type)
            r4 = merge_relationships(session, "MADE_OF", "Material",
                                     "aligned_material", rel_material)
            print(f"[neo4j] rels upserted: STORED_IN={r1} BELONGS_TO_PERIOD={r2} "
                  f"HAS_TYPE={r3} MADE_OF={r4}")

            if not args.skip_enrichment:
                enrich = find_enrichment_path()
                if enrich:
                    n = apply_enrichment(session, enrich)
                    print(f"[neo4j] enrichment applied: {enrich.name} ({n} entities)")
                else:
                    print("[neo4j] no augmented_entities.json found, skip enrichment.")
    finally:
        driver.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
