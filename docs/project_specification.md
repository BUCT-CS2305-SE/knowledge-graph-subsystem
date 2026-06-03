# 知识图谱构建子系统统一规范文档

> 本文档为项目唯一正式规范文档，面向组员、后续维护者和 Agent。  
> 若本文档与其他说明存在冲突，以本文档为准。  
> 原始需求资料保留在 `docs/target.md` 与 `docs/global_goal.md`，不作为日常开发规范入口。

---

## 1. 项目定位

本项目是“海外藏中国文物知识管理与服务平台”中的知识图谱构建子系统，负责为后续知识服务、可视化展示、智能问答、移动端应用和后台管理系统提供可信、结构化、可持续更新的数据基础。

本子系统的核心职责包括：

1. 从海外博物馆网站抓取中国文物数据。
2. 对原始数据进行清洗、标准化和质量控制。
3. 对艺术家、朝代、地点、博物馆等实体进行识别、对齐和去重。
4. 从外部资料源补充实体背景信息，并保留来源和补充日期。
5. 将清洗后的数据写入 MySQL，并同步构建 Neo4j 图数据库。
6. 支持后续增量爬取、数据更新和图谱同步。

---

## 2. 项目范围与验收要求

### 2.1 指定博物馆

本组为 5 团，需完成以下三家海外博物馆的数据采集：

| 序号 | 博物馆 | 当前代码文件 | 数据产物 |
| --- | --- | --- | --- |
| 5 | Princeton University Art Museum | `scrapers/spiders/princeton_spider.py` | `scrapers/data/princeton_museum.csv` |
| 10 | Art Institute of Chicago | `scrapers/spiders/chicago_spider.py` | `scrapers/data/chicago_museum.csv` |
| 15 | Brooklyn Museum | `scrapers/spiders/brooklyn_spider.py` | `scrapers/data/brooklyn_museum.csv` |

### 2.2 数据量要求

最终三馆有效记录合计不少于 5000 条，建议目标分配如下：

| 博物馆 | 建议目标数 |
| --- | ---: |
| Art Institute of Chicago | 1700 |
| Princeton University Art Museum | 1700 |
| Brooklyn Museum | 1600 |

### 2.3 基础验收标准

最终提交前至少满足以下条件：

1. 三家博物馆均有有效 CSV 数据。
2. 三馆合计有效记录不少于 5000 条。
3. `object_id`、`title`、`detail_url`、`image_url`、`crawl_date` 等关键字段尽量完整。
4. CSV 文件使用 UTF-8 编码，可被 pandas 正常读取。
5. 图片链接尽量为原图链接，不使用缩略图作为最终图像来源。
6. 随机抽查 20 条图片可正常打开。
7. 随机抽查 10 条详情页 URL 可访问。
8. 清洗结果可写入 MySQL。
9. MySQL 数据可同步到 Neo4j。
10. 流水线可重复运行，重复运行不应造成明显重复数据。

---

## 3. 当前仓库结构

当前仓库已完成目录去重，保留一条主链路：

```text
knowledge-graph-subsystem/
├── app.py
├── config.py
├── db/
│   ├── mysql_builder.py
│   └── neo4j_builder.py
├── docs/
│   ├── project_specification.md
│   ├── global_goal.md
│   └── target.md
├── pipeline/
│   └── run_pipeline.py
├── scrapers/
│   ├── spiders/
│   │   ├── chicago_spider.py
│   │   ├── princeton_spider.py
│   │   └── brooklyn_spider.py
│   ├── clean_qa.py
│   ├── augmentation.py
│   ├── requirements.txt
│   └── data/
└── tests/
    ├── fixtures/
    │   └── _mock_50.csv
    └── test_schema.py
```

### 3.1 主目录职责

| 目录或文件 | 职责 |
| --- | --- |
| `scrapers/spiders/` | 三家博物馆爬虫 |
| `scrapers/clean_qa.py` | 数据清洗、标准化、质量报告 |
| `scrapers/augmentation.py` | 实体补充与外部百科增强 |
| `db/mysql_builder.py` | 清洗数据写入 MySQL |
| `db/neo4j_builder.py` | MySQL 或 CSV 数据同步到 Neo4j |
| `pipeline/run_pipeline.py` | 全流程调度与增量状态记录 |
| `app.py` | FastAPI 服务入口 |
| `config.py` | MySQL、Neo4j、API Key 等环境变量配置 |
| `tests/test_schema.py` | CSV schema 与基础质量校验 |

### 3.2 已清理内容

旧的 `mvp/` 原型目录已删除。原因如下：

1. 旧目录与当前 `scrapers + db + pipeline` 主链路重复。
2. 旧目录中大量文件为占位实现，容易误导后续 Agent 或组员。
3. 当前主链路已有可运行入口，应避免维护两套结构。

---

## 4. 四名组员任务安排评价

你给其他四名组员的任务划分如下：

1. 爬取普林斯顿数据。
2. 爬取布鲁克林数据，并与组员 A 完成通用爬虫框架，便于后续直接接入 pipeline。
3. 数据清洗与实体对齐。
4. 数据补充与增量爬取。

该安排总体合理，符合当前仓库结构和项目交付目标。

### 4.1 优点

1. 职责边界清晰，四名组员分别对应爬虫、公共框架、清洗对齐、数据增强与增量。
2. 与现有主链路匹配，所有工作都可以围绕 `scrapers/`、`pipeline/` 和 `db/` 展开。
3. 普林斯顿与布鲁克林分开爬取，可以并行推进，降低单点阻塞。
4. 布鲁克林相对更复杂，将其与通用爬虫框架绑定，有利于沉淀公共抓取能力。
5. 清洗与实体对齐由同一人负责，可以避免标准化规则分散。
6. 数据补充与增量爬取由同一人负责，便于统一记录来源、补充日期和变更记录。

### 4.2 需要注意的风险

1. “通用爬虫框架”如果没有明确接口，容易影响普林斯顿和布鲁克林两条线的交付节奏。
2. “数据清洗”和“实体对齐”工作量偏大，需要尽早使用 mock 数据和现有 `chicago_museum.csv` 开始开发。
3. “数据补充”和“增量爬取”与 `pipeline/run_pipeline.py` 有耦合，需要由组长把入口边界提前定好。
4. 布鲁克林爬虫和通用框架交给同一人，任务难度高于普林斯顿爬虫，需要设置第一阶段交付物，避免后期一次性集成失败。

### 4.3 调整建议

建议将四人任务正式命名为：

| 成员 | 任务名称 | 主要文件 | 交付物 |
| --- | --- | --- | --- |
| 成员 A | 普林斯顿数据采集 | `scrapers/spiders/princeton_spider.py` | `scrapers/data/princeton_museum.csv` |
| 成员 B | 布鲁克林数据采集与通用爬虫框架 | `scrapers/spiders/brooklyn_spider.py`、`scrapers/common.py` 或 `scrapers/common/` | `scrapers/data/brooklyn_museum.csv`、公共 HTTP/CSV/图片工具 |
| 成员 C | 数据清洗与实体对齐 | `scrapers/clean_qa.py` | `scrapers/data/cleaned/`、质量报告、对齐结果 |
| 成员 D | 数据补充与增量爬取 | `scrapers/augmentation.py`、`pipeline/run_pipeline.py` | `scrapers/data/augmented_entities.json`、增量运行记录 |

组长负责：

1. 芝加哥爬虫基准样例。
2. MySQL 与 Neo4j 入库。
3. 全流程 pipeline 集成。
4. API 服务与最终联调。
5. 统一规范、验收和合并控制。

---

## 5. 代码所有权规范

### 5.1 文件级负责人

| 负责人 | 主要负责文件 |
| --- | --- |
| 组长 | `scrapers/spiders/chicago_spider.py`、`db/mysql_builder.py`、`db/neo4j_builder.py`、`pipeline/run_pipeline.py`、`app.py`、`config.py` |
| 成员 A | `scrapers/spiders/princeton_spider.py` |
| 成员 B | `scrapers/spiders/brooklyn_spider.py`、通用爬虫工具模块 |
| 成员 C | `scrapers/clean_qa.py` |
| 成员 D | `scrapers/augmentation.py`、`pipeline/run_pipeline.py` 中增量相关逻辑 |

### 5.2 合作原则

1. 每名成员优先修改自己负责的文件。
2. 如需修改他人负责文件，需先说明原因。
3. 公共函数应沉淀到通用模块，不应在三个爬虫里重复复制。
4. 不允许擅自修改 CSV 字段顺序。
5. 不允许擅自修改数据库表结构。
6. 不允许提交真实大规模数据、图片和运行日志。
7. 合并前必须通过 `pytest tests/test_schema.py`。

---

## 6. 通用爬虫框架规范

通用爬虫框架由成员 B 主导，成员 A 配合，组长负责最终接入 pipeline。

### 6.1 推荐位置

推荐新增以下结构：

```text
scrapers/
├── common/
│   ├── __init__.py
│   ├── http_client.py
│   ├── csv_writer.py
│   ├── image_downloader.py
│   └── incremental.py
```

若暂时不拆目录，也可以先使用：

```text
scrapers/common.py
```

### 6.2 必须提供的能力

| 模块 | 职责 |
| --- | --- |
| `http_client.py` | 统一请求头、超时、重试、限流 |
| `csv_writer.py` | 统一字段顺序、编码、缺失字段补齐 |
| `image_downloader.py` | 统一图片下载、路径生成、原图链接检查 |
| `incremental.py` | 统一内容 hash、是否重爬判断、运行记录 |

### 6.3 爬虫输出要求

三个爬虫最终都必须输出同一 schema：

```text
object_id,title,period,type,material,description,dimensions,museum,location,detail_url,image_url,image_path,credit_line,accession_number,crawl_date
```

### 6.4 接入 pipeline 的要求

三个爬虫必须支持命令行参数：

```bash
--target-count
--incremental-since
```

示例：

```bash
python3 spiders/princeton_spider.py --target-count 1700 --incremental-since 2026-05-01
```

如果某个博物馆暂时无法根据时间增量过滤，也必须接受该参数并安全忽略，不得导致 pipeline 报错。

---

## 7. 数据字段规范

### 7.1 原始 CSV 字段

| 字段 | 中文说明 | 是否必填 | 说明 |
| --- | --- | --- | --- |
| `object_id` | 文物唯一标识符 | 必填 | 建议包含馆前缀或保证全局唯一 |
| `title` | 文物名称 | 必填 | 优先保留英文原名 |
| `period` | 年代或时期 | 必填 | 保留博物馆原始描述，清洗阶段再标准化 |
| `type` | 文物类型 | 必填 | 保留原始类型 |
| `material` | 材质 | 建议 | 缺失填空字符串 |
| `description` | 文物介绍 | 必填 | 应去除明显 HTML 标签 |
| `dimensions` | 尺寸 | 建议 | 缺失填空字符串 |
| `museum` | 所属博物馆 | 必填 | 使用英文全称 |
| `location` | 博物馆所在地 | 必填 | 格式建议为 `City, Country` |
| `detail_url` | 文物详情页 URL | 必填 | 原始页面链接 |
| `image_url` | 图片原始链接 | 必填 | 尽量为原图地址 |
| `image_path` | 本地图片路径 | 必填 | 未下载可暂为空，但最终验收需补齐 |
| `credit_line` | 版权或来源说明 | 建议 | 缺失填空字符串 |
| `accession_number` | 藏品编号 | 建议 | 缺失填空字符串 |
| `crawl_date` | 爬取日期 | 必填 | `YYYY-MM-DD` |

### 7.2 文件命名

| 博物馆 | 文件名 |
| --- | --- |
| Art Institute of Chicago | `scrapers/data/chicago_museum.csv` |
| Princeton University Art Museum | `scrapers/data/princeton_museum.csv` |
| Brooklyn Museum | `scrapers/data/brooklyn_museum.csv` |

### 7.3 编码规范

1. CSV 使用 UTF-8 编码。
2. 缺失字段填空字符串。
3. 不允许省略列。
4. 不允许写入 `None` 或 `null` 字面值。
5. 文本字段中出现换行、逗号时，应由 CSV writer 正确转义。

---

## 8. 清洗与实体对齐规范

成员 C 负责该部分。

### 8.1 输入

```text
scrapers/data/chicago_museum.csv
scrapers/data/princeton_museum.csv
scrapers/data/brooklyn_museum.csv
```

### 8.2 输出

```text
scrapers/data/cleaned/clean_chicago_museum.csv
scrapers/data/cleaned/clean_princeton_museum.csv
scrapers/data/cleaned/clean_brooklyn_museum.csv
docs/data_quality_report.md
scrapers/data/quality_report.json
```

### 8.3 必做任务

1. 补齐缺失列，保持字段顺序一致。
2. 标准化年代表达，如 Qing、Ming、Tang 等。
3. 标准化文物类型，如 Painting、Ceramics、Jade、Textiles 等。
4. 检查 `object_id`、`title`、`detail_url`、`image_url`、`crawl_date` 完整率。
5. 校验本地图片是否存在且文件大小合理。
6. 对重复记录进行识别和处理。
7. 输出质量报告。

### 8.4 实体对齐目标

优先对以下实体做对齐：

1. 朝代或时期。
2. 博物馆。
3. 文物类型。
4. 材质。
5. 艺术家或作者。
6. 地点。

实体对齐不要求一次完成全部，但必须保证朝代、博物馆、类型、材质四类实体可支撑 Neo4j 构建。

---

## 9. 数据补充与增量爬取规范

成员 D 负责该部分。

### 9.1 数据补充

当前补充入口：

```text
scrapers/augmentation.py
```

当前补充结果：

```text
scrapers/data/augmented_entities.json
```

补充数据至少包含：

| 字段 | 说明 |
| --- | --- |
| `uri` | 实体唯一标识 |
| `description` | 补充说明 |
| `source` | 来源，如 Baidu Baike、Wikipedia |

### 9.2 推荐补充对象

优先级如下：

1. 朝代背景。
2. 艺术家生平。
3. 地点信息。
4. 文物类型说明。
5. 特定文物的扩展介绍。

### 9.3 增量爬取

当前 pipeline 已有运行状态文件：

```text
pipeline/sync_state.json
```

后续增量机制应记录：

1. 本次运行时间。
2. 每家博物馆目标数量。
3. 原始记录数。
4. 清洗记录数。
5. 相比上次运行的变化数量。
6. 执行过的步骤。

### 9.4 参数约定

三个爬虫均应支持：

```bash
--incremental-since <date>
```

如果目标网站不支持按更新时间筛选，则以本地 `object_id` 或内容 hash 去重方式实现弱增量。

---

## 10. 图谱建模规范

### 10.1 Neo4j 节点类型

当前最低节点类型：

| 节点 | 含义 | 主要属性 |
| --- | --- | --- |
| `Artifact` | 文物 | `id`、`title`、`url` |
| `Museum` | 博物馆 | `name` |
| `Period` | 朝代或时期 | `name`、`uri`、`description` |
| `Type` | 文物类型 | `name` |
| `Material` | 材质 | `name` |

后续可扩展：

| 节点 | 含义 |
| --- | --- |
| `Artist` | 艺术家或作者 |
| `Location` | 地点 |
| `Context` | 补充背景实体 |

### 10.2 Neo4j 关系类型

当前最低关系类型：

| 关系 | 含义 |
| --- | --- |
| `STORED_IN` | 文物收藏于博物馆 |
| `BELONGS_TO_PERIOD` | 文物属于某一时期或朝代 |
| `HAS_TYPE` | 文物属于某一类型 |
| `MADE_OF` | 文物由某种材质制成 |

### 10.3 与 CIDOC-CRM 的对应关系

项目不要求实现完整 CIDOC-CRM，但应参考其语义：

| 项目实体 | CIDOC-CRM 参考 |
| --- | --- |
| `Artifact` | `E22 Human-Made Object` |
| `Museum` | `E40 Legal Body` |
| `Period` | `E4 Period` |
| `Artist` | `E21 Person` |
| `Location` | `E53 Place` |
| `Material` | `E57 Material` |
| `Type` | `E55 Type` |

---

## 11. 数据库存储规范

### 11.1 MySQL

MySQL 用于业务查询和 API 数据读取。

当前主要表：

```text
artifacts
```

关键要求：

1. `object_id` 应作为主键或唯一键。
2. 重复导入应使用 upsert，不应产生重复行。
3. 字符集使用 `utf8mb4`。
4. 数据库连接信息必须从环境变量读取。

### 11.2 Neo4j

Neo4j 用于图查询和关系遍历。

构建脚本：

```text
db/neo4j_builder.py
```

关键要求：

1. 使用 `MERGE` 避免重复节点。
2. 为核心节点创建唯一约束。
3. 优先从 MySQL 读取数据构建图谱。
4. 增强实体数据可补充写入 Period 等节点。

---

## 12. API 服务规范

服务入口：

```text
app.py
```

启动方式：

```bash
uvicorn app:app --host 127.0.0.1 --port 8000
```

### 12.1 API 能力范围

API 面向后续前端、问答和可视化系统，至少应支持：

1. 文物列表查询。
2. 文物详情查询。
3. 图片代理或本地图片访问。
4. 关键词搜索。
5. 文物相关实体查询。
6. 统计信息查询。

### 12.2 错误格式

建议统一返回：

```json
{
  "code": 404,
  "message": "Artifact not found"
}
```

### 12.3 安全配置

如启用 API Key，应通过环境变量配置：

```bash
export KG_API_KEY='your_api_key'
```

不得在代码中硬编码密钥。

---

## 13. Pipeline 规范

统一入口：

```text
pipeline/run_pipeline.py
```

### 13.1 执行顺序

1. 执行三家博物馆爬虫。
2. 执行 `scrapers/clean_qa.py`。
3. 执行 `scrapers/augmentation.py`。
4. 执行 `db/mysql_builder.py`。
5. 执行 `db/neo4j_builder.py`。
6. 写入运行状态。

### 13.2 状态文件

```text
pipeline/sync_state.json
```

应记录：

1. `last_run`
2. `total_records`
3. 最近若干次运行历史
4. 每次运行的目标数、原始数、清洗数和增量变化

### 13.3 失败处理

1. 任一步骤失败，pipeline 应停止后续步骤。
2. 错误应写入日志。
3. 不应在失败时更新成功状态。

---

## 14. 运行与复现方式

### 14.1 环境变量

```bash
export KG_MYSQL_HOST=127.0.0.1
export KG_MYSQL_PORT=3306
export KG_MYSQL_USER=root
export KG_MYSQL_PASSWORD='your_mysql_password'
export KG_MYSQL_DATABASE=knowledge_graph_db
export KG_NEO4J_URI=bolt://localhost:7687
export KG_NEO4J_USER=neo4j
export KG_NEO4J_PASSWORD='your_neo4j_password'
```

### 14.2 安装依赖

```bash
python3 -m pip install -r scrapers/requirements.txt
python3 -m pip install fastapi uvicorn pymysql sqlalchemy neo4j
python3 -m pip install -e .[dev]
```

### 14.3 运行完整流水线

```bash
cd /Users/bytedance/Desktop/knowledge-graph-subsystem
python3 pipeline/run_pipeline.py
```

### 14.4 单独运行爬虫

```bash
cd /Users/bytedance/Desktop/knowledge-graph-subsystem/scrapers
python3 spiders/chicago_spider.py --target-count 1700
python3 spiders/princeton_spider.py --target-count 1700
python3 spiders/brooklyn_spider.py --target-count 1600
```

### 14.5 单独运行清洗与补充

```bash
cd /Users/bytedance/Desktop/knowledge-graph-subsystem/scrapers
python3 clean_qa.py
python3 augmentation.py
```

### 14.6 单独运行数据库同步

```bash
cd /Users/bytedance/Desktop/knowledge-graph-subsystem/db
python3 mysql_builder.py
python3 neo4j_builder.py
```

### 14.7 启动 API

```bash
cd /Users/bytedance/Desktop/knowledge-graph-subsystem
uvicorn app:app --host 127.0.0.1 --port 8000
```

---

## 15. 测试规范

测试入口：

```text
tests/test_schema.py
```

运行：

```bash
cd /Users/bytedance/Desktop/knowledge-graph-subsystem
pytest tests/test_schema.py
```

### 15.1 测试数据

| 路径 | 用途 |
| --- | --- |
| `tests/fixtures/_mock_50.csv` | 严格 schema 样例 |
| `scrapers/data/*.csv` | 实际爬虫输出样例 |

### 15.2 合并前要求

1. 测试必须通过。
2. 新增 CSV 产物必须符合字段顺序。
3. 不得提交大型真实数据、图片、数据库文件或运行日志。

---

## 16. Git 与文件提交规范

### 16.1 可以提交

1. 源代码。
2. 规范文档。
3. 小规模测试 fixture。
4. 必要的配置模板。

### 16.2 不应提交

1. 大规模真实 CSV。
2. 图片文件。
3. 数据库文件。
4. `pipeline/sync_state.json`。
5. `pipeline/pipeline.log`。
6. `.pytest_cache/`。
7. `__pycache__/`。

### 16.3 分支建议

| 成员 | 建议分支 |
| --- | --- |
| 成员 A | `feat/princeton-crawler` |
| 成员 B | `feat/brooklyn-common-crawler` |
| 成员 C | `feat/cleaning-alignment` |
| 成员 D | `feat/enrichment-incremental` |
| 组长 | `feat/pipeline-storage-integration` |

---

## 17. 近期实施计划

### 17.1 第一阶段

1. 组长确认统一规范文档。
2. 成员 A 修正并补齐普林斯顿爬虫。
3. 成员 B 提交通用爬虫框架最小版本。
4. 成员 C 基于现有 Chicago 数据和 fixture 开始清洗规则。
5. 成员 D 明确数据补充来源和增量状态结构。

### 17.2 第二阶段

1. 三家爬虫全部输出统一 schema。
2. 清洗脚本能够处理三家数据。
3. 增强脚本输出可被 Neo4j builder 使用。
4. Pipeline 能一次串起全流程。

### 17.3 第三阶段

1. 完成不少于 5000 条数据的真实运行。
2. 完成数据质量报告。
3. 完成 MySQL 与 Neo4j 同步。
4. 完成 API 查询验证。
5. 完成最终演示准备。

---

## 18. Agent 执行守则

如果后续由 Agent 接手开发，必须遵守：

1. 先阅读本文档。
2. 优先沿 `scrapers -> db -> pipeline -> app` 主链路工作。
3. 不要重新引入旧的 `mvp/` 结构。
4. 不要擅自改变 CSV 字段顺序。
5. 不要擅自修改数据库连接配置方式。
6. 不要提交真实大规模数据和图片。
7. 修改公共逻辑时，优先抽象到 `scrapers/common/` 或等价公共模块。
8. 修改后必须运行 `pytest tests/test_schema.py`。

---

## 19. 总结

当前项目应以本规范为唯一协作依据。四名组员的任务安排总体合理，但必须通过统一 CSV schema、通用爬虫框架、pipeline 参数约定和测试校验来降低集成风险。后续所有开发应围绕现有主链路推进，不再维护第二套原型目录或重复规范文档。
