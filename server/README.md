# 服务端（Server）

将原 `app.py` 拆分为分层模块，由 FastAPI 暴露知识图谱子系统的对外 API。
所有连接信息均从环境变量读取。

## 目录

```text
server/
├── __init__.py
├── __main__.py        # python -m server 启动入口
├── main.py            # FastAPI app 工厂、异常处理、路由挂载
├── config.py          # 环境变量解析
├── db.py              # MySQL 连接与 Neo4j driver
├── utils.py           # 通用工具：年代解析、图片路径、关联查询
├── routers/
│   ├── artifacts.py   # 列表 / 详情 / 单属性
│   ├── search.py      # 全文检索
│   ├── images.py      # 原图 / 缩略图
│   └── stats.py       # 统计
├── requirements.txt
└── .env.example
```

## 环境

- Python 3.9+
- 已运行 MySQL（`artifacts` 表已建好）与 Neo4j（可选，详情接口会尝试读取关联实体）

## 安装

```bash
python3 -m pip install -r server/requirements.txt
```

## 配置

复制环境变量模板并按实际填入：

```bash
cp server/.env.example server/.env
export $(grep -v '^#' server/.env | xargs)
```

或者直接 `export`：

```bash
export KG_MYSQL_PASSWORD='your_password'
export KG_NEO4J_PASSWORD='your_password'
```

## 启动

```bash
# 方式 A：模块启动
python3 -m server

# 方式 B：直接调用 uvicorn（推荐生产）
uvicorn server.main:app --host 127.0.0.1 --port 8000

# 方式 C：开启热重载（开发）
KG_API_RELOAD=1 python3 -m server
```

启动后访问：

- `http://127.0.0.1:8000/docs`  Swagger 文档
- `http://127.0.0.1:8000/api/stats/summary`  快速联通性检查

## 主要接口

| Method | Path | 说明 |
| --- | --- | --- |
| GET | `/api/artifacts` | 文物列表（分页、筛选、排序） |
| GET | `/api/artifacts/{id}` | 文物详情 + Neo4j 关联实体 |
| GET | `/api/artifacts/{id}/property?prop=` | 单属性查询 |
| GET | `/api/search?q=` | 全文检索 |
| GET | `/api/images/{id}/original` | 原图（缺图返回占位 SVG） |
| GET | `/api/images/{id}/thumbnail?size=` | 缩略图 |
| GET | `/api/stats/summary` | 基础统计 |

## 错误格式

统一返回：

```json
{ "code": 404, "message": "Artifact not found" }
```
