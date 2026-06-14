# 知识图谱构建子系统

从海外博物馆网站爬取中国文物信息，经数据清洗、建模与存储，构建结构化的海外文物知识图谱，为知识服务、问答及可视化提供数据基础。

> 本组（5 团）负责的三家博物馆：**普林斯顿大学艺术博物馆、芝加哥艺术博物馆、布鲁克林艺术博物馆**。
> 需求原文见 [docs/target.md](docs/target.md)。

---

## 1. 功能概览

| 模块 | 目录 | 作用 |
| --- | --- | --- |
| 数据爬取 | `crawlers/` | 抓取各馆中国文物，输出统一 schema 的 CSV + 原图 |
| 数据清洗 | `data_processing/cleaning/` | 字段标准化、年代/类型/材质归一、去重、图片校验、质量报告 |
| 实体对齐 | `data_processing/alignment/` | 跨馆实体对齐 + 生成唯一 URI + 产出 Neo4j 导入文件 |
| 数据补充 | `data_update/enrichment/` | 从百度百科/维基百科补充实体背景，标注来源与日期 |
| 增量更新 | `data_update/incremental/` | 基于内容 hash 识别新增/更新记录 |
| 数据存储 | `db/` | 写入 MySQL（业务查询）与 Neo4j（图谱查询） |
| API 服务 | `server/` | FastAPI 提供列表/详情/搜索/图谱/统计/问答等接口 |
| 全流程调度 | `pipeline/` | 串联以上各步骤，记录运行状态 |

---

## 2. 目录结构

```text
knowledge-graph-subsystem/
├── crawlers/                  # 爬虫
│   ├── main.py                #   统一入口（python3 -m crawlers.main --museum <id>）
│   ├── spiders.py             #   各馆爬虫实现
│   ├── base_crawler.py        #   通用爬虫基类
│   └── data/raw/              #   原始 CSV/JSONL 产物
├── data_processing/
│   ├── cleaning/              # 清洗
│   │   ├── run_all_clean.py   #   清洗总入口
│   │   ├── clean_<museum>.py  #   各馆清洗逻辑
│   │   └── cleaned/           #   清洗产物 + 质量报告
│   └── alignment/             # 实体对齐
│       ├── entity_alignment.py
│       ├── by_dataset/        #   对齐后各馆 CSV（MySQL 入库用）
│       └── neo4j_import/      #   节点 + 关系 CSV（Neo4j 入库用）
├── data_update/
│   ├── enrichment/enrichment.py    # 数据补充
│   └── incremental/incremental.py  # 增量扫描
├── db/
│   ├── mysql_builder.py       # 写入 MySQL
│   ├── neo4j_builder.py       # 构建 Neo4j 图谱（含 enrichment 注入）
│   ├── phash_indexer.py       # 图片 pHash 索引（以图搜图）
│   └── clip_indexer.py        # CLIP + FAISS 语义索引（可选）
├── server/                    # FastAPI 服务（routers/ 下分模块）
├── pipeline/run_pipeline.py   # 全流程调度
├── docs/                      # 需求与部署文档
└── tests/test_schema.py       # CSV schema 校验
```

---

## 3. 数据模型（参考 CIDOC-CRM）

### 实体（Neo4j 节点）

| 节点 | 含义 | CIDOC-CRM 参考 |
| --- | --- | --- |
| `Artifact` | 文物 | E22 Human-Made Object |
| `Museum` | 博物馆 | E40 Legal Body |
| `Period` | 朝代/时期 | E4 Period |
| `Type` | 文物类型 | E55 Type |
| `Material` | 材质 | E57 Material |
| `Artist` | 艺术家 | E21 Person |
| `Location` | 地点 | E53 Place |

每类实体均带唯一标识 `uri`（形如 `http://buct-kg.org/resource/{kind}/{slug}`），同名实体跨数据源映射到同一 URI 以实现去重。

### 关系

| 关系 | 含义 |
| --- | --- |
| `(Artifact)-[:STORED_IN]->(Museum)` | 收藏于 |
| `(Artifact)-[:BELONGS_TO_PERIOD]->(Period)` | 属于朝代 |
| `(Artifact)-[:HAS_TYPE]->(Type)` | 类型为 |
| `(Artifact)-[:MADE_OF]->(Material)` | 材质为 |
| `(Artifact)-[:CREATED_BY]->(Artist)` | 创作于 |
| `(Artifact)-[:ORIGINATES_FROM]->(Location)` | 产自/出土 |

### 双层存储

- **MySQL**：`artifacts` 表存文物明细，供业务查询；`object_id` 唯一键，重复导入用 upsert。
- **Neo4j**：存全部实体与关系，供图查询；`MERGE` 避免重复节点，核心节点建唯一约束。

---

## 4. 数据字段（CSV schema）

```text
object_id,title,period,type,material,description,dimensions,museum,location,
detail_url,image_url,image_path,credit_line,accession_number,crawl_date
```

详见 [docs/target.md](docs/target.md) 字段表。缺失字段填空字符串，不省略列，UTF-8 编码。

---

## 5. 快速开始

### 5.1 安装依赖

```bash
python3 -m pip install -r requirements.txt          # 数据处理依赖（pandas 等）
python3 -m pip install -r server/requirements.txt   # 服务依赖（fastapi/uvicorn/pymysql/neo4j 等）
```

### 5.2 配置环境变量

复制 `server/.env.example` 为 `.env`，填入数据库连接：

```bash
KG_MYSQL_HOST=127.0.0.1
KG_MYSQL_PORT=3306
KG_MYSQL_USER=kguser
KG_MYSQL_PASSWORD=******
KG_MYSQL_DATABASE=knowledge_graph_db
KG_NEO4J_URI=bolt://localhost:7687
KG_NEO4J_USER=neo4j
KG_NEO4J_PASSWORD=******
```

### 5.3 运行全流程

```bash
# 已有原始数据时跳过爬取
python3 pipeline/run_pipeline.py --skip-crawl

# 只重建数据库
python3 pipeline/run_pipeline.py --only mysql_build neo4j_build
```

各步骤也可单独运行：

```bash
python3 data_processing/cleaning/run_all_clean.py        # 清洗
python3 data_processing/alignment/entity_alignment.py    # 对齐
python3 data_update/enrichment/enrichment.py --kinds period museum artist location --source both
python3 data_update/incremental/incremental.py scan --museums chicago princeton brooklyn_museum
python3 db/mysql_builder.py
python3 db/neo4j_builder.py --reset                      # --reset 先清空全图再重建
```

### 5.4 启动 API 服务

```bash
set -a && source .env && set +a
python3 -m server
# 文档： http://127.0.0.1:8000/docs
```

`/api/*` 默认需要 JWT；本地联调可在 `.env` 设 `KG_ADMIN_AUTH_ENABLED=0` 临时关闭。

管理端在 `/docs` 提供一键任务按钮（需 admin token）：

```text
POST /api/admin/jobs/clean         触发清洗
POST /api/admin/jobs/enrich        触发补充
POST /api/admin/jobs/incremental   触发增量扫描
GET  /api/admin/jobs/status        查看运行状态
```

---

## 6. 部署与数据同步

服务器部署、清空旧库 → 重新入库、数据同步等完整步骤见 [docs/DEPLOY.md](docs/DEPLOY.md)。

要点：
- MySQL 是 upsert（只增改不删），重灌前需先 `TRUNCATE TABLE artifacts;`
- Neo4j 是 MERGE，重灌需用 `python3 db/neo4j_builder.py --reset` 先清空全图
- 本地准备数据（不含图片即可入库），上传 `data_processing/alignment/` 与 `data_update/enrichment/augmented_entities.json` 后在服务器入库

---

## 7. 测试

```bash
pytest tests/test_schema.py
```

校验 CSV 字段顺序与基础数据质量。

---

## 8. 相关文档

- [docs/target.md](docs/target.md) — 需求原文与验收标准
- [docs/DEPLOY.md](docs/DEPLOY.md) — 部署与运维手册
- 各模块 README：[crawlers](crawlers/README.md)、[cleaning](data_processing/cleaning/README.md)、[alignment](data_processing/alignment/README.md)、[enrichment](data_update/enrichment/README.md)、[incremental](data_update/incremental/README.md)、[server](server/README.md)
