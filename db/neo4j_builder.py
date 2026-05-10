import pandas as pd
import os
import json
from neo4j import GraphDatabase

# Neo4j 数据库配置
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "se_jk2305"

DATA_DIR = os.path.join(os.path.dirname(__file__), "../scrapers/data/cleaned")
AUGMENTED_FILE = os.path.join(os.path.dirname(__file__), "../scrapers/data/augmented_entities.json")

def create_constraints(session):
    """为 Neo4j 节点创建唯一约束，避免导入时产生重复节点并加快 MERGE 速度"""
    print("Creating constraints for fast merging...")
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
        except Exception:
            pass

def import_augmented_data(session):
    """读取百度百科等补充的实体信息，更新到已有或新建的 Neo4j 节点上"""
    if not os.path.exists(AUGMENTED_FILE):
        print("No augmented data found, skipping...")
        return
        
    print("Importing augmented entity data to Graph...")
    with open(AUGMENTED_FILE, 'r', encoding='utf-8') as f:
        augmented_data = json.load(f)
        
    for period_name, info in augmented_data.items():
        # 这里以朝代时期 Period 为例进行实体增强信息的挂载
        cypher = """
            MERGE (p:Period {name: $name})
            SET p.uri = $uri,
                p.description = $desc,
                p.source = $source
        """
        session.run(cypher, name=period_name, uri=info.get('uri',''), desc=info.get('description',''), source=info.get('source',''))
    print("Augmented data loaded.")

def import_csv_to_graph(session, csv_path):
    print(f"Importing core artifacts from {os.path.basename(csv_path)} into Graph...")
    df = pd.read_csv(csv_path).fillna("Unknown")

    for _, row in df.iterrows():
        cypher_query = """
            // 1. Artifact
            MERGE (a:Artifact {id: $a_id})
            SET a.title = $a_title, 
                a.url = $detail_url
            
            // 2. Museum Relationships
            MERGE (m:Museum {name: $museum_name})
            MERGE (a)-[:STORED_IN]->(m)
            
            // 3. Period/Dynasty
            MERGE (p:Period {name: $period})
            MERGE (a)-[:BELONGS_TO_PERIOD]->(p)
            
            // 4. Object Type
            MERGE (t:Type {name: $art_type})
            MERGE (a)-[:HAS_TYPE]->(t)
            
            // 5. Material
            MERGE (mat:Material {name: $material})
            MERGE (a)-[:MADE_OF]->(mat)
        """
        session.run(cypher_query, 
            a_id=str(row['object_id']), a_title=str(row['title']), detail_url=str(row['detail_url']),
            museum_name=str(row['museum']), period=str(row['period']),
            art_type=str(row['type']), material=str(row['material'])
        )

def main():
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))
        with driver.session() as session:
            create_constraints(session)
            
            if os.path.exists(DATA_DIR):
                csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv')]
                for file in csv_files:
                    import_csv_to_graph(session, os.path.join(DATA_DIR, file))
            
            # 导入增强型数据 (Task 4 中的外挂知识)
            import_augmented_data(session)
            
        driver.close()
        print("Neo4j database loading complete.")
    except Exception as e:
        print(f"Error connecting or writing to Neo4j: {e}")
        print("Please ensure Neo4j Desktop/Server is running and credentials are valid.")

if __name__ == "__main__":
    main()
