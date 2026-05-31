"""服务端配置：所有连接信息从环境变量读取，避免在仓库中硬编码密钥。"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class MySQLConfig:
    host: str = _env("KG_MYSQL_HOST", "127.0.0.1")
    port: int = int(_env("KG_MYSQL_PORT", "3306") or 3306)
    user: str = _env("KG_MYSQL_USER", "root")
    password: str = _env("KG_MYSQL_PASSWORD", "")
    database: str = _env("KG_MYSQL_DATABASE", "knowledge_graph_db")


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str = _env("KG_NEO4J_URI", "bolt://localhost:7687")
    user: str = _env("KG_NEO4J_USER", "neo4j")
    password: str = _env("KG_NEO4J_PASSWORD", "")


@dataclass(frozen=True)
class AppConfig:
    title: str = "中国海外流失文物知识图谱 API"
    description: str = (
        "提供基于 MySQL 和 Neo4j 的文物检索、关系查询、以及沉浸式主题视图接口。"
    )
    version: str = "1.0.0"
    # 项目根：用于解析 image_path 等相对路径
    project_root: str = _env(
        "KG_PROJECT_ROOT",
        os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)),
    )


mysql_config = MySQLConfig()
neo4j_config = Neo4jConfig()
app_config = AppConfig()
