# 数据补充（Enrichment）

为知识图谱中的共享实体（朝代 / 博物馆 / 文物类型 / 材质）补充背景信息，
保留来源与补充日期，供 Neo4j 图谱写入使用。

## 数据来源策略

实体名通常是英文，会先用百度翻译 API 译成中文（常见朝代/类型/博物馆内置了
本地映射，免翻译更准），再去查百科。

| `--source` | 行为 |
| --- | --- |
| `baidu` | 仅百度百科（抓词条页解析摘要） |
| `wiki`  | 中文维基（按中文名）→ 英文/原名维基 |
| `both`  | 百度百科 → 中文维基 → 英文维基（**默认，最稳**） |

> 为什么默认 `both`：百度百科对高频抓取会临时返回 403 限流；此时中文维基
> 自动兜底，保证补充不中断。

## 用法

```bash
# 默认：both 策略，补充 period 与 museum
python3 data_update/enrichment/enrichment.py

# 只用百度百科
python3 data_update/enrichment/enrichment.py --source baidu

# 补充全部四类实体，放慢请求间隔降低被限流概率
python3 data_update/enrichment/enrichment.py \
    --kinds period museum type material --delay 1.0
```

常用参数：

- `--kinds`：要补充的实体种类（period / museum / type / material）
- `--source`：baidu / wiki / both
- `--delay`：请求间隔秒数（被限流时调大，如 1.0）
- `--limit`：最多处理多少个实体（调试用）

环境变量（退避重试，应对临时限流）：

- `KG_ENRICH_MAX_FAIL`：连续失败多少次触发退避（默认 5）
- `KG_ENRICH_BACKOFF`：每次退避等待秒数（默认 20）
- `KG_ENRICH_MAX_BACKOFF`：连续退避多少次仍失败才判定断网放弃（默认 3）

## 输入 / 输出

输入（对齐阶段产物，优先读 `neo4j_import/`，回退读 `alignment/`）：

```text
data_processing/alignment/nodes_periods.csv
data_processing/alignment/nodes_museums.csv
data_processing/alignment/nodes_types.csv
data_processing/alignment/nodes_materials.csv
```

输出：

```text
data_update/enrichment/augmented_entities.json
data_update/enrichment/augmented_entities.csv
```

字段：`uri / kind / name / description / source / source_url / enrich_date`

## 一键执行（补充 + 增量）

本地跑这一个脚本即可同时完成「补充 + 增量扫描」，并打印需要上传到服务器的
文件清单：

```bash
python3 pipeline/run_update.py                 # 默认 both
python3 pipeline/run_update.py --source baidu --delay 1.0
python3 pipeline/run_update.py --skip-incremental   # 只补充
```

## 通过 API 一键触发（后台管理，需 ADMIN 权限）

服务端提供了管理接口，可在 `/docs` 上点击触发（需先 Authorize 粘贴 admin JWT）：

```text
POST /api/admin/jobs/enrich        # 触发数据补充
POST /api/admin/jobs/clean         # 触发数据清洗
POST /api/admin/jobs/incremental   # 触发增量扫描
GET  /api/admin/jobs/status        # 查看运行状态与日志尾部
```
