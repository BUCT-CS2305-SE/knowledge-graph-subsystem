"""数据库连接封装：MySQL（每请求独立连接）+ Neo4j（全局 driver）。"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

import pymysql
from neo4j import GraphDatabase

from .config import mysql_config, neo4j_config


# ---------- MySQL ----------

def get_mysql_conn() -> pymysql.connections.Connection:
    return pymysql.connect(
        host=mysql_config.host,
        port=mysql_config.port,
        user=mysql_config.user,
        password=mysql_config.password,
        database=mysql_config.database,
        cursorclass=pymysql.cursors.DictCursor,
    )


@contextmanager
def mysql_cursor() -> Iterator[pymysql.cursors.DictCursor]:
    conn = get_mysql_conn()
    try:
        yield conn.cursor()
    finally:
        conn.close()


# ---------- Neo4j ----------

_neo4j_driver: Optional[GraphDatabase.driver] = None


def get_neo4j_driver():
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = GraphDatabase.driver(
            neo4j_config.uri,
            auth=(neo4j_config.user, neo4j_config.password),
        )
    return _neo4j_driver


def close_neo4j_driver() -> None:
    global _neo4j_driver
    if _neo4j_driver is not None:
        try:
            _neo4j_driver.close()
        finally:
            _neo4j_driver = None
