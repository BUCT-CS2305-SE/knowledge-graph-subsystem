# 知识图谱模型设计与 Neo4j 构建方案

## 1. 本体模型图 (Ontology Design)
基于 CIDOC-CRM 的指导以及本系统核心需支撑的文物及周边实体展示功能，定义如下基础的三元组 (主体 - 关系 -> 客体) 模型概念：

### 核心节点 (Nodes/Labels)
1. **`Artifact` (文物实体)**
   - 包含的属性: `id`, `title`, `description`, `dimensions`, `url`, `image`, `crawl_date`
2. **`Museum` (博物馆)**
   - 包含的属性: `name`, `location`
3. **`Period` / `Dynasty` (时间或朝代实体)**
   - 包含的属性: `name` (例如 "Qing Dynasty (1644-1911)")
4. **`Type` (文物分类)**
   - 包含的属性: `name` (例如 "Painting", "Ceramics")
5. **`Material` (材质实体)**
   - 包含的属性: `name` (例如 "Silk", "Bronze")
6. **`Context` / `Artist` (可选外部实体, 后续扩充爬取或百度百科补充)**
   - 包含的属性: `name`, `bio`

### 核心关系 (Relationships)
- `(Artifact)-[:STORED_IN]->(Museum)`  ：收藏于某个博物馆
- `(Artifact)-[:BELONGS_TO_PERIOD]->(Period)` ：属于某个朝代/时期
- `(Artifact)-[:HAS_TYPE]->(Type)` ：属于哪种文物分类
- `(Artifact)-[:MADE_OF]->(Material)` ：由什么材质制造

---

## 2. Neo4j 数据库导入构建脚本 (Cypher / Build)

这部分脚本采用 Python 连接 Neo4j。这里设计为批量将整理后的 CSV 三元组注入到 Neo4j 图数据库。

```python
# db/neo4j_builder.py
import pandas as pd
import os
from neo4j import GraphDatabase

# Neo4j 连接配置
URI = "bolt://localhost:7687"
AUTH = ("neo4j", "your_password_here")

def clear_db(session):
    print("Clearing existing data...")
    session.run("MATCH (n) DETACH DELETE n")

def create_constraints(session):
    print("Creating constraints for fast merging...")
    # 在 neo4j v4/v5 版本里使用 CONSTRAINT 保证实体唯一性
    constraints = [
        "CREATE CONSTRAINT artifact_id IF NOT EXISTS FOR (a:Artifact) REQUIRE a.id IS UNIQUE",
        "CREATE CONSTRAINT museum_name IF NOT EXISTS FOR (m:Museum) REQUIRE m.name IS UNIQUE",
        "CREATE CONSTRAINT period_name IF NOT EXISTS FOR (p:Period) REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT type_name IF NOT EXISTS FOR (t:Type) REQUIRE t.name IS UNIQUE",
        "CREATE CONSTRAINT material_name IF NOT EXISTS FOR (mat:Material) REQUIRE mat.name IS UNIQUE",
    ]
    for c in constraints:
        try:
            session.run(c)
        except Exception as e:
            pass # 忽略已存在的约束

def import_csv_to_graph(session, csv_path):
    print(f"Importing {csv_path} into Graph...")
    if not os.path.exists(csv_path):
        return
        
    df = pd.read_csv(csv_path).fillna("Unknown")

    for _, row in df.iterrows():
        # 提取各个清洗好的核心参数
        a_id = row['object_id']
        a_title = row['title']
        a_desc = row['description']
        
        period = row['period']
        art_type = row['type']
        material = row['material']
        museum_name = row['museum']
        
        # Cypher MERGE 语句用于：如果存在则融合，不存在则创建节点
        # 并创建文物与其他元数据节点及关系
        cypher_query = """
            // 1. 核心 Artifact
            MERGE (a:Artifact {id: $a_id})
            SET a.title = $a_title, 
                a.description = $a_desc
            
            // 2. Museum 关系
            MERGE (m:Museum {name: $museum_name})
            MERGE (a)-[:STORED_IN]->(m)
            
            // 3. Period 关系 (清洗过的朝代)
            MERGE (p:Period {name: $period})
            MERGE (a)-[:BELONGS_TO_PERIOD]->(p)
            
            // 4. Type 关系
            MERGE (t:Type {name: $art_type})
            MERGE (a)-[:HAS_TYPE]->(t)
            
            // 5. Material 关系
            MERGE (mat:Material {name: $material})
            MERGE (a)-[:MADE_OF]->(mat)
        """
        
        session.run(cypher_query, 
            a_id=str(a_id), a_title=str(a_title), a_desc=str(a_desc),
            museum_name=str(museum_name), period=str(period),
            art_type=str(art_type), material=str(material)
        )

def main():
    driver = GraphDatabase.driver(URI, auth=AUTH)
    with driver.session() as session:
        # 1. 确保唯一性
        create_constraints(session)
        # 2. 从 cleaned 目录迭代导入
        cleaned_dir = "../scrapers/data/cleaned/"
        
        # 你可以打开此行来在重新跑爬虫前清库 
        # clear_db(session) 

        for root, dirs, files in os.walk(cleaned_dir):
            for file in files:
                if file.endswith(".csv"):
                    import_csv_to_graph(session, os.path.join(root, file))

    driver.close()
    print("Graph Data Model Initialization Completed.")

if __name__ == "__main__":
    main()
```
