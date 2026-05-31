# 知识图谱构建子系统 — 服务器部署指南

本文档面向一台干净的 Linux 服务器（已在 **Ubuntu 22.04 / 24.04 LTS** 验证），从 `git clone` 开始，
完整覆盖系统依赖安装、MySQL / Neo4j 部署、Python 环境、数据初始化、API 启动、
反向代理与定时增量任务。所有步骤已与本仓库的代码 / 默认配置对齐。

---

## 0. 总览

部署完成后，服务器上将运行 4 个组件：

| 组件 | 默认端口 | 说明 |
|------|----------|------|
| MySQL 8.0 | 3306 | 业务表 `artifacts` |
| Neo4j 5.x | 7474 / 7687 | 知识图谱（HTTP / Bolt） |
| FastAPI (uvicorn) | 8000 | 业务 API（`/api/...`） |
| Nginx (可选) | 80 / 443 | 反向代理 + HTTPS |

目录约定：仓库根 = `/opt/kg/knowledge-graph-subsystem`。如需替换路径，请同步修改下文 `cd` 命令与 systemd 配置中的 `WorkingDirectory`。

---

## 1. 系统准备

### 1.1 更新系统并创建工作目录

```bash
sudo apt update && sudo apt -y upgrade
sudo mkdir -p /opt/kg
sudo chown -R "$USER":"$USER" /opt/kg
```

### 1.2 安装基础工具

```bash
sudo apt -y install \
    git curl wget vim \
    build-essential pkg-config \
    python3 python3-pip python3-venv \
    libssl-dev libffi-dev \
    ca-certificates gnupg lsb-release
```

要求 Python ≥ 3.9。Ubuntu 22.04 自带 3.10，OK；Ubuntu 20.04 自带 3.8 太旧，请安装 3.10：

```bash
sudo apt -y install software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update && sudo apt -y install python3.10 python3.10-venv python3.10-dev
```

---

## 2. 拉取代码

```bash
cd /opt/kg
git clone <你的仓库地址> knowledge-graph-subsystem
cd knowledge-graph-subsystem
```

后续所有命令默认在 `/opt/kg/knowledge-graph-subsystem` 下执行。

---

## 3. 安装并初始化 MySQL 8.0

### 3.1 安装

```bash
sudo apt -y install mysql-server
sudo systemctl enable --now mysql
sudo mysql_secure_installation         # 按提示设置 root 密码、移除匿名/远程 root 等
```

### 3.2 创建专用用户与数据库

```bash
sudo mysql -uroot -p
```

进入 MySQL 后执行：

```sql
CREATE DATABASE IF NOT EXISTS knowledge_graph_db
    DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER 'kguser'@'127.0.0.1' IDENTIFIED BY '一个强密码';
GRANT ALL PRIVILEGES ON knowledge_graph_db.* TO 'kguser'@'127.0.0.1';
FLUSH PRIVILEGES;
EXIT;
```

> 表结构 `artifacts` 由 [db/mysql_builder.py](file:///opt/kg/knowledge-graph-subsystem/db/mysql_builder.py) 在首次运行时通过 `CREATE TABLE IF NOT EXISTS` 自动建立，无需手动建表。

---

## 4. 安装并初始化 Neo4j 5.x

### 4.1 安装 OpenJDK 17（Neo4j 5 必需）

```bash
sudo apt -y install openjdk-17-jre-headless
```

### 4.2 添加 Neo4j 官方源并安装

```bash
curl -fsSL https://debian.neo4j.com/neotechnology.gpg.key \
  | sudo gpg --dearmor -o /usr/share/keyrings/neo4j.gpg
echo 'deb [signed-by=/usr/share/keyrings/neo4j.gpg] https://debian.neo4j.com stable 5' \
  | sudo tee /etc/apt/sources.list.d/neo4j.list

sudo apt update
sudo apt -y install neo4j
sudo systemctl enable --now neo4j
```

### 4.3 设置初始密码

```bash
# 5.x 默认初始密码 neo4j，首次登录强制改密
sudo cypher-shell -u neo4j -p neo4j \
  "ALTER USER neo4j SET PASSWORD '一个强密码';"
```

### 4.4（可选）允许局域网访问

仅当 API 服务部署在另一台机器上时再放开。默认 `127.0.0.1` 即可：

```bash
sudo vim /etc/neo4j/neo4j.conf
# 取消注释并修改：
#   server.default_listen_address=0.0.0.0
sudo systemctl restart neo4j
```

---

## 5. 创建 Python 虚拟环境并安装依赖

```bash
cd /opt/kg/knowledge-graph-subsystem
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

> 仓库根 [requirements.txt](file:///opt/kg/knowledge-graph-subsystem/requirements.txt) 已合并爬虫、清洗、入库、API 全部依赖；不再需要单独 `pip install -r server/requirements.txt`。

---

## 6. 配置环境变量

复制模板并填写真实值：

```bash
cp server/.env.example .env
vim .env
```

`.env` 内容示例：

```bash
# ---- MySQL ----
KG_MYSQL_HOST=127.0.0.1
KG_MYSQL_PORT=3306
KG_MYSQL_USER=kguser
KG_MYSQL_PASSWORD=一个强密码
KG_MYSQL_DATABASE=knowledge_graph_db

# ---- Neo4j ----
KG_NEO4J_URI=bolt://localhost:7687
KG_NEO4J_USER=neo4j
KG_NEO4J_PASSWORD=一个强密码

# ---- API 服务 ----
KG_API_HOST=127.0.0.1
KG_API_PORT=8000
KG_API_RELOAD=0

# ---- 项目根（用于解析图片相对路径）----
KG_PROJECT_ROOT=/opt/kg/knowledge-graph-subsystem
```

把 `.env` 加载到当前 shell（手动运行 pipeline 时必须）：

```bash
set -a && source .env && set +a
```

> systemd 服务通过 `EnvironmentFile=` 自动加载 `.env`，无需手动 source。

---

## 7. 数据准备 — 一键全流程

仓库提供 [pipeline/run_pipeline.py](file:///opt/kg/knowledge-graph-subsystem/pipeline/run_pipeline.py) 串联全部步骤：

```
crawl  →  clean  →  align  →  enrichment  →  incremental  →  mysql  →  neo4j
```

### 7.0 输入数据源优先级（重要）

仓库已自带双语清洗 + 对齐结果，所有 builder 自动按下表选择输入：

| 优先级 | 路径 | 内容 | 备注 |
|---|---|---|---|
| 1 | `data_processing/alignment/by_dataset/` | 中文 + `*_original_en` 双语列 + `aligned_*` | MySQL builder 主输入 |
| 2 | `data_processing/alignment/neo4j_import/` | 中文 nodes/relationships CSV | Neo4j builder 主输入 |
| 3 | `data_processing/cleaning/cleaned/` | 双语清洗结果（无 aligned_*） | MySQL 兜底 |
| 4 | `data_processing/alignment/`（旧 nodes_*.csv 等） | 旧版英文对齐 | Neo4j 兜底 |
| 5 | `data_processing/cleaning/clean_*.csv` / `crawlers/data/raw/` | 清洗 / 原始 | 最低兜底 |

> Neo4j builder 还会自动从 `by_dataset/clean_*.csv` 读 `*_original_en` 列，
> 把 `Artifact.title_en/description_en` 和 `Period/Type/Material.name_en` 写入图谱。

### 7.1 首次完整初始化

```bash
source venv/bin/activate
set -a && source .env && set +a

python3 pipeline/run_pipeline.py
```

执行日志：[pipeline/pipeline.log](file:///opt/kg/knowledge-graph-subsystem/pipeline/pipeline.log)
状态记录（最近 50 次）：[pipeline/sync_state.json](file:///opt/kg/knowledge-graph-subsystem/pipeline/sync_state.json)

### 7.2 跳过已完成的步骤

仓库已自带清洗 / 对齐后的 CSV，部署到新服务器时通常只需要"补充 → 入库"：

```bash
python3 pipeline/run_pipeline.py \
    --skip-crawl --skip-clean --skip-align --skip-incremental
```

> **enrichment 卡住怎么办？**
> `enrichment` 步骤会逐个查询 Wikipedia 给 Period / Museum 补背景描述。
> 如果服务器**无法访问 wikipedia.org**（如部分 IDC 默认外网不通），
> 它会一个接一个超时，看起来像"卡住"。两种解决办法：
>
> 1. **直接跳过**（推荐 — 仓库已自带 `data_update/enrichment/augmented_entities.json`，不影响 API）：
>    ```bash
>    python3 pipeline/run_pipeline.py --skip-enrichment ...
>    ```
> 2. **降低连续失败阈值**：脚本内置网络探测，连续 5 次失败后自动放弃后续；
>    可用环境变量调整：
>    ```bash
>    KG_ENRICH_MAX_FAIL=3 python3 data_update/enrichment/enrichment.py --limit 20
>    ```
> enrichment 在 pipeline 中标记为非必需，失败/超时**不会阻塞** mysql/neo4j 构建。

### 7.3 仅重建数据库（场景：换库 / 回滚）

```bash
# 仅 MySQL
python3 db/mysql_builder.py

# 仅 Neo4j（先清空再重建）
python3 db/neo4j_builder.py --reset
```

### 7.4 从英文单语升级到中英双语（已有部署）

> 适用场景：服务器之前已用 **旧英文版本** 部署完毕（artifacts 表无 `*_en` / `phash` 列、Neo4j 节点无 `name_en`），
> 现在需要应用最新双语数据。**整个流程零停机** — 加列幂等、节点 MERGE 增量。

```bash
# 1) 拉新代码（新增 *_en 列、双语 builder、双语路由）
cd ~/se_apps/knowledge-graph-subsystem
git fetch && git pull

# 2) 上传新双语数据（本地 → 服务器）
#    本机执行：把 data_processing/ 整目录 rsync 上去
#    rsync -avz --delete data_processing/ \
#        root@<server>:/root/se_apps/knowledge-graph-subsystem/data_processing/

# 3) 验证服务器侧的输入路径
ls data_processing/alignment/by_dataset/clean_*.csv | head     # 应见 7 个馆
ls data_processing/alignment/neo4j_import/nodes_*.csv | head   # 应见 5 个 nodes_*.csv
head -1 data_processing/alignment/by_dataset/clean_met.csv | tr ',' '\n' | grep _original_en
#    ^ 应该列出 title_original_en / period_original_en / ... 多行

# 4) 重建 MySQL（自动 ALTER ADD COLUMN：title_en / period_en / ... / phash 列）
source venv/bin/activate
python3 db/mysql_builder.py
# [mysql] inputs:
#   - data_processing/alignment/by_dataset/clean_british_museum.csv  ← 路径变为 by_dataset
#   ...

# 5) 重建 Neo4j（清空 + 写 title_en / name_en）
python3 db/neo4j_builder.py --reset
# [neo4j] ... | en_lookup: artifacts=N period=M type=K material=L
#                                ^ 这行有数字才说明双语注入成功

# 6) 重建 pHash（先前因缺列报错，现在补列后跑通）
python3 db/phash_indexer.py --rebuild

# 7) （可选）CLIP 索引（首跑很慢，下载 ~600MB 模型 + GPU 推理）
python3 db/clip_indexer.py --rebuild

# 8) 重启 API 服务（让新路由的 lang 参数生效）
sudo systemctl restart kg-api
sleep 2
curl http://127.0.0.1:8000/api/health
```

**冒烟测试（验证双语接口已就绪）**：

```bash
HOST=http://127.0.0.1:8000
ID=$(curl -s "$HOST/api/artifacts?page=1&page_size=1" | python3 -c "import sys,json; print(json.load(sys.stdin)['items'][0]['id'])")

# 中文
curl -s "$HOST/api/artifacts/$ID?lang=zh" | python3 -m json.tool | head -20
# 英文
curl -s "$HOST/api/artifacts/$ID?lang=en" | python3 -m json.tool | head -20
# 双语 LIKE
curl -s "$HOST/api/search?keyword=Qing&lang=en"  | python3 -m json.tool | head
curl -s "$HOST/api/search?keyword=清&lang=zh"     | python3 -m json.tool | head
# 详情 i18n 双语对照
curl -s "$HOST/api/artifacts/$ID" | python3 -c "import sys,json; print(json.load(sys.stdin).get('i18n'))"
```

**关键预期值**：
- `[mysql] upserted=...` 行不再报错；`SHOW COLUMNS FROM artifacts` 应见 `title_en` / ... / `phash`
- `[neo4j] en_lookup: artifacts=5000+ period=400+` 才算双语注入成功
- `/api/artifacts/{id}?lang=en` 中 `name` 字段应为英文，且响应含 `i18n` 子对象
- `/api/image-search/status` 中 `clip_index_size > 0`（如已跑步骤 7）

**回滚**：双语化是**纯加列**，不删数据；如需回滚仅需回滚 git 即可，旧数据保留。


### 7.5 单步运行（调试用）

```bash
python3 pipeline/run_pipeline.py --only mysql_build neo4j_build
```

完成后到 MySQL / Neo4j 各做一次连通性自检：

```bash
mysql -ukguser -p -h127.0.0.1 knowledge_graph_db \
      -e "SELECT COUNT(*) FROM artifacts;"

cypher-shell -u neo4j -p '一个强密码' \
      "MATCH (n) RETURN labels(n) AS l, count(*) AS c ORDER BY c DESC;"
```

---

## 8. 启动 API 服务

### 8.1 前台开发模式（仅调试）

```bash
source venv/bin/activate
set -a && source .env && set +a
python3 -m server
# 或：uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

打开 `http://<server-ip>:8000/docs` 验证 OpenAPI 文档可访问。

### 8.2 生产部署 — systemd 托管

创建服务文件：

```bash
sudo tee /etc/systemd/system/kg-api.service > /dev/null <<'EOF'
[Unit]
Description=Knowledge Graph API (FastAPI/uvicorn)
After=network.target mysql.service neo4j.service

[Service]
Type=simple
User=kg
Group=kg
WorkingDirectory=/opt/kg/knowledge-graph-subsystem
EnvironmentFile=/opt/kg/knowledge-graph-subsystem/.env
ExecStart=/opt/kg/knowledge-graph-subsystem/venv/bin/python -m server
Restart=on-failure
RestartSec=5
StandardOutput=append:/var/log/kg-api.log
StandardError=append:/var/log/kg-api.log

[Install]
WantedBy=multi-user.target
EOF
```

创建运行账户并授权：

```bash
sudo useradd -r -s /usr/sbin/nologin kg || true
sudo chown -R kg:kg /opt/kg/knowledge-graph-subsystem
sudo touch /var/log/kg-api.log && sudo chown kg:kg /var/log/kg-api.log

sudo systemctl daemon-reload
sudo systemctl enable --now kg-api
sudo systemctl status kg-api
sudo journalctl -u kg-api -f          # 查看实时日志
```

---

## 9. 反向代理（Nginx + HTTPS，可选）

### 9.1 安装 Nginx

```bash
sudo apt -y install nginx
```

### 9.2 站点配置

```bash
sudo tee /etc/nginx/sites-available/kg-api > /dev/null <<'EOF'
server {
    listen 80;
    server_name kg.example.com;

    client_max_body_size 32m;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/kg-api /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 9.3 启用 HTTPS（Let's Encrypt）

```bash
sudo apt -y install certbot python3-certbot-nginx
sudo certbot --nginx -d kg.example.com
```

证书会自动续签（`/etc/cron.d/certbot`）。

---

## 10. 防火墙

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'           # 80 + 443
# 不要直接对外暴露 3306 / 7474 / 7687 / 8000
sudo ufw enable
sudo ufw status
```

---

## 11. 定时增量更新（cron）

每日 02:00 跑一次"增量爬取 + 重新入库"：

```bash
crontab -e
```

加入：

```cron
0 2 * * * cd /opt/kg/knowledge-graph-subsystem && \
    /opt/kg/knowledge-graph-subsystem/venv/bin/python3 pipeline/run_pipeline.py \
    --skip-crawl --skip-clean --skip-align \
    >> /var/log/kg-pipeline.log 2>&1
```

> 上次 vs 这次的差异（diff）由 [data_update/incremental/incremental.py](file:///opt/kg/knowledge-graph-subsystem/data_update/incremental/incremental.py) 通过 `sync_state.json` + 内容 hash 自动维护，幂等可重复运行。

---

## 12. 升级流程

```bash
cd /opt/kg/knowledge-graph-subsystem
git pull
source venv/bin/activate
pip install -r requirements.txt
python3 pipeline/run_pipeline.py --skip-crawl --skip-clean --skip-align
sudo systemctl restart kg-api
```

---

## 12.5 启用 CLIP + FAISS 语义检索（可选）

> 默认情况下，`/api/image-search` 使用轻量 **pHash**（感知哈希 + Hamming），擅长"找几乎一样的图"，但不擅长"找语义相似"。
> 安装 CLIP + FAISS 后，路由会自动切换到语义检索（`engine: "clip"`），并额外开放 **以文搜图** 端点 `/api/image-search/text`。
> 整个升级**零改动路由层**，未安装时自动 fallback 到 pHash。

### 12.5.1 安装依赖（约 2 GB，建议有外网且磁盘 ≥ 5 GB）

```bash
cd /opt/kg/knowledge-graph-subsystem
source venv/bin/activate
pip install -r requirements-clip.txt        # 含 torch / torchvision / transformers / faiss-cpu
```

> 若服务器有 GPU，可改装 `torch` 的 CUDA 版本，索引器会自动走 GPU；否则纯 CPU 即可（首次推理会下载 ~600MB 的 CLIP-ViT-B/32 权重到 `~/.cache/huggingface`）。

### 12.5.2 配置环境变量（可选）

编辑 [server/.env](file:///opt/kg/knowledge-graph-subsystem/server/.env)：

```ini
KG_CLIP_MODEL=openai/clip-vit-base-patch32
KG_CLIP_INDEX_DIR=/opt/kg/knowledge-graph-subsystem/data/clip_index
```

### 12.5.3 跑一次离线索引

```bash
# 方式 A：单独跑索引器
python3 db/clip_indexer.py

# 方式 B：在 pipeline 末尾追加 CLIP 索引步骤
python3 pipeline/run_pipeline.py --skip-crawl --skip-clean --skip-align --with-clip
```

产物：

```
data/clip_index/artifacts.faiss      # FAISS IndexFlatIP（cos 相似度）
data/clip_index/artifacts.ids.txt    # 与向量对齐的 object_id 列表
```

### 12.5.4 重启服务并验证

```bash
sudo systemctl restart kg-api
curl -s http://127.0.0.1:8000/api/image-search/status
# {"clip_available": true, "clip_index_size": 12345, "fallback": "phash"}

# 以图搜图（CLIP 模式）
curl -F "file=@some.jpg" "http://127.0.0.1:8000/api/image-search?top_k=10&model=clip"

# 以文搜图（仅 CLIP）
curl -F "text=blue and white porcelain dragon" \
     "http://127.0.0.1:8000/api/image-search/text?top_k=10"
```

> 后续库内文物变更后，按 §11 的 cron 习惯加一行 `python3 db/clip_indexer.py` 即可保持索引新鲜。

---

## 13. 运维与排错速查

| 现象 | 排查 |
|------|------|
| API 起不来 | `sudo journalctl -u kg-api -n 200` |
| 连不上 MySQL | `mysql -ukguser -p -h127.0.0.1`；检查 `KG_MYSQL_*` |
| 连不上 Neo4j | `sudo systemctl status neo4j`；`cypher-shell -u neo4j -p ...` |
| 中文乱码 | 库 / 表 / 连接均需 `utf8mb4`；本仓库已强制 |
| pipeline 慢 / 卡 | 看 [pipeline/pipeline.log](file:///opt/kg/knowledge-graph-subsystem/pipeline/pipeline.log) 末尾 |
| Wikipedia 抓取失败多 | 网络问题；enrichment 已对带括号名称做回退 + cache，会"软失败"，不影响入库 |
| 端口被占 | `sudo lsof -iTCP:8000 -sTCP:LISTEN` |
| `image-search/status` 返回 `clip_available:false` | 未装 CLIP 依赖，走 pHash 兜底；或 `pip install -r requirements-clip.txt` |
| `clip_index_size: 0` | 未跑过 [db/clip_indexer.py](file:///opt/kg/knowledge-graph-subsystem/db/clip_indexer.py)，或 `KG_CLIP_INDEX_DIR` 指向错误 |
| CLIP 首次启动很慢 | 正在下载 ~600MB 模型权重，仅首次；可预先 `huggingface-cli download` |
| CLIP 不走 GPU | `python3 -c "import torch;print(torch.cuda.is_available())"` 确认 CUDA 版 torch |

---

## 14. 卸载（如需重装）

```bash
sudo systemctl disable --now kg-api nginx neo4j mysql
sudo apt -y purge neo4j mysql-server
sudo rm -rf /opt/kg /etc/nginx/sites-{available,enabled}/kg-api \
            /etc/systemd/system/kg-api.service /var/log/kg-*.log
sudo systemctl daemon-reload
```

---

## 附录 A：环境变量索引

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `KG_MYSQL_HOST` / `_PORT` / `_USER` / `_PASSWORD` / `_DATABASE` | MySQL 连接 | 见 §6 |
| `KG_NEO4J_URI` / `_USER` / `_PASSWORD` | Neo4j 连接 | 见 §6 |
| `KG_API_HOST` / `_PORT` / `_RELOAD` | uvicorn 启动参数 | `127.0.0.1:8000` |
| `KG_PROJECT_ROOT` | 解析 `image_path` 相对路径 | 留空 → `server/..` |

## 附录 B：本仓库目录映射

| 目录 / 文件 | 作用 | target.md 章节 |
|---|---|---|
| [crawlers/](file:///opt/kg/knowledge-graph-subsystem/crawlers) | 爬虫（Princeton / Chicago / Brooklyn Museum 等 7 馆） | (1) 数据爬取 |
| [data_processing/cleaning/](file:///opt/kg/knowledge-graph-subsystem/data_processing/cleaning) | 字段标准化 / 去重 / 图片有效性 + 百度翻译 | (2) 数据清洗 |
| [data_processing/cleaning/cleaned/](file:///opt/kg/knowledge-graph-subsystem/data_processing/cleaning/cleaned) | 双语清洗结果（含 `*_original_en` 列） | (2) |
| [data_processing/alignment/](file:///opt/kg/knowledge-graph-subsystem/data_processing/alignment) | 实体对齐脚本 + 三元组 CSV | (3) 数据建模 / (5) 实体对齐 |
| [data_processing/alignment/by_dataset/](file:///opt/kg/knowledge-graph-subsystem/data_processing/alignment/by_dataset) | 各馆双语对齐 CSV（MySQL builder 主输入） | (3) |
| [data_processing/alignment/neo4j_import/](file:///opt/kg/knowledge-graph-subsystem/data_processing/alignment/neo4j_import) | Neo4j 节点 / 关系 CSV（builder 主输入） | (3)+(6) |
| [data_update/enrichment/](file:///opt/kg/knowledge-graph-subsystem/data_update/enrichment) | Wikipedia 实体补充 | (4) 数据补充 |
| [data_update/incremental/](file:///opt/kg/knowledge-graph-subsystem/data_update/incremental) | 增量爬取 + 状态管理 | (7) 增量更新 |
| [db/mysql_builder.py](file:///opt/kg/knowledge-graph-subsystem/db/mysql_builder.py) | 业务表 `artifacts` 入库 | (6) 数据存储 |
| [db/neo4j_builder.py](file:///opt/kg/knowledge-graph-subsystem/db/neo4j_builder.py) | CIDOC-CRM 风格知识图谱构建 | (3)+(6) |
| [db/phash_indexer.py](file:///opt/kg/knowledge-graph-subsystem/db/phash_indexer.py) | 图像 pHash 离线索引（以图搜图） | 跨子系统服务 |
| [db/clip_indexer.py](file:///opt/kg/knowledge-graph-subsystem/db/clip_indexer.py) | CLIP+FAISS 语义索引（以图/以文搜图，可选） | 跨子系统服务 |
| [pipeline/run_pipeline.py](file:///opt/kg/knowledge-graph-subsystem/pipeline/run_pipeline.py) | 全流程编排 | (7) |
| [server/](file:///opt/kg/knowledge-graph-subsystem/server) | FastAPI 业务 API（10 类接口） | 对外服务 |

## 附录 C：API 一览（供其它 4 个子系统对接）

> **双语支持**：所有"读"接口均支持 `?lang=zh|en` 查询参数（默认 `zh`）。
> 数据层会按 lang 切换 `title/period/type/material/description/credit_line` 等字段；
> 当英文列为空时自动回退中文。详情接口额外返回 `i18n` 双语对照对象。

| 路径 | 方法 | lang 支持 | 用途 | 主要使用方 |
|---|---|---|---|---|
| `/api/health` | GET | — | 健康探针 | 后台监控 |
| `/api/artifacts` | GET | ✅ | 列表查询（分页 / 筛选 / 排序，type 同时匹配 type_en） | Web、移动端 |
| `/api/artifacts/{id}` | GET | ✅ | 详情（含 Neo4j 关联实体 + `i18n` 双语对照） | Web、移动端 |
| `/api/artifacts/{id}/property` | GET | ✅ | 单属性读（按 lang 切中/英列） | 问答 |
| `/api/artifacts/{id}/related` | GET | ✅ | 相关推荐（同朝代/同类型双语匹配 + 视觉） | Web、移动端 |
| `/api/artifacts/compare` | POST | ✅ | 文物对比（2~3 件） | Web |
| `/api/search` | GET | ✅ | 全文检索（中英文列同时 LIKE） | Web、移动端 |
| `/api/search/advanced` | GET | ✅ | 多字段高级查询（每个条件双语 LIKE） | Web |
| `/api/search/export` | GET | ✅ | 查询结果导出 CSV/JSON | Web |
| `/api/filters` | GET | ✅ | 筛选枚举（按 lang 返回中/英枚举值） | Web、后台 |
| `/api/images/{id}/original` | GET | — | 原图（无图回退 SVG 占位） | Web、移动端 |
| `/api/images/{id}/thumbnail` | GET | — | 缩略图 | Web、移动端 |
| `/api/image-search` | POST | ✅ | 以图搜图（CLIP 优先，pHash 兜底；`model=auto\|clip\|phash`） | 移动端、Web |
| `/api/image-search/text` | POST | ✅ | 以文搜图（仅 CLIP，需先跑离线索引） | 移动端、Web |
| `/api/image-search/by-id/{id}` | GET | ✅ | 视觉相似（基于已有文物） | Web、移动端 |
| `/api/image-search/status` | GET | — | 探针：`clip_available` / `clip_index_size` / `fallback` | 后台、调试 |
| `/api/graph/neighbors/{id}` | GET | ✅ | 邻居子图（节点 name 按 lang 切 name/name_en） | Web 可视化 |
| `/api/graph/timeline` | GET | ✅ | 时间轴数据（period 按 lang 切） | Web 可视化 |
| `/api/graph/geo` | GET | — | 地理分布数据 | Web 可视化 |
| `/api/graph/path` | GET | ✅ | 两实体最短路径（节点同时返回 name 和 name_en） | 问答多跳 |
| `/api/qa/intents` | GET | — | 列出问答意图 | 问答 |
| `/api/qa/query` | POST | ✅ | 模板化 Cypher 查询（artifacts_of_period 返回 name+name_en） | 问答 |
| `/api/qa/grounding/{id}` | GET | ✅ | 单文物事实包（RAG 上下文，按 lang 切 object 文本） | 问答 |
| `/api/stats/summary` | GET | — | 基础统计（Top5） | 后台、Web |
| `/api/stats/distribution` | GET | — | 多维分布（饼图/柱状图） | 后台 |
| `/api/stats/growth` | GET | — | 增长曲线 | 后台 |
| `/api/admin/artifacts` | POST/PUT/DELETE | — | 后台 CRUD（X-Admin-Token） | 后台 |
| `/api/admin/consistency-check` | GET | — | MySQL ↔ Neo4j 一致性 | 后台 |

> **使用示例**：
> - 中文列表：`GET /api/artifacts?page=1&page_size=20`
> - 英文列表：`GET /api/artifacts?page=1&page_size=20&lang=en`
> - 双语全文检索：`GET /api/search?keyword=Qing&lang=en`（"Qing" 命中 `title_en`）
>   或 `GET /api/search?keyword=清&lang=zh`（"清" 命中 `title`）
> - 详情双语对照：`GET /api/artifacts/{id}` 响应中的 `i18n` 字段同时含
>   `title_zh / title_en / period_zh / period_en / type_zh / type_en / material_zh / material_en`
