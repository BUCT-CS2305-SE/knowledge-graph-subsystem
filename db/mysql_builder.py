"""
MySQL 入库构建器：从清洗 / 对齐结果写入 `artifacts` 业务表。

输入优先级（自动探测，先到先得）：
    1. data_processing/alignment/clean_*.csv
    2. data_processing/cleaning/clean_*.csv
    3. crawlers/data/raw/*.csv

输出：
    MySQL 数据库 `artifacts` 表（utf8mb4）。重复运行使用 upsert，不产生重复行。

CLI：
    python3 db/mysql_builder.py                # 全量构建
    python3 db/mysql_builder.py --create-only  # 仅建表 / 建索引
    python3 db/mysql_builder.py --inputs path1.csv path2.csv

环境变量（默认值见 server/config.py 同名变量）：
    KG_MYSQL_HOST / KG_MYSQL_PORT / KG_MYSQL_USER /
    KG_MYSQL_PASSWORD / KG_MYSQL_DATABASE
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Iterable, Iterator

try:
    import pymysql
except ImportError:  # pragma: no cover
    print("ERROR: 请先安装 pymysql -> pip install pymysql", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[1]

# 与 docs/project_specification.md 7.1 节保持一致的 15 列
ARTIFACT_COLUMNS = [
    "object_id", "title", "period", "type", "material",
    "description", "dimensions", "museum", "location",
    "detail_url", "image_url", "image_path",
    "credit_line", "accession_number", "crawl_date",
]

# 当对齐 CSV 中携带 aligned_* 列时，优先使用对齐后的标准值
ALIGNED_OVERRIDES = {
    "period": "aligned_period",
    "type": "aligned_type",
    "material": "aligned_material",
    "museum": "aligned_museum",
}

CREATE_DB_SQL = (
    "CREATE DATABASE IF NOT EXISTS `{db}` "
    "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS artifacts (
    object_id        VARCHAR(128) NOT NULL,
    title            VARCHAR(512) NOT NULL DEFAULT '',
    period           VARCHAR(255)          DEFAULT '',
    type             VARCHAR(128)          DEFAULT '',
    material         VARCHAR(255)          DEFAULT '',
    description      MEDIUMTEXT,
    dimensions       VARCHAR(255)          DEFAULT '',
    museum           VARCHAR(255)          DEFAULT '',
    location         VARCHAR(255)          DEFAULT '',
    detail_url       VARCHAR(1024)         DEFAULT '',
    image_url        VARCHAR(1024)         DEFAULT '',
    image_path       VARCHAR(512)          DEFAULT '',
    credit_line      VARCHAR(512)          DEFAULT '',
    accession_number VARCHAR(128)          DEFAULT '',
    crawl_date       DATE                  DEFAULT NULL,
    phash            CHAR(16)              DEFAULT '',
    PRIMARY KEY (object_id),
    KEY idx_museum (museum),
    KEY idx_period (period),
    KEY idx_type   (type),
    KEY idx_phash  (phash),
    FULLTEXT KEY ft_title_desc (title, description)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
"""

UPSERT_SQL = (
    "INSERT INTO artifacts ("
    + ",".join(f"`{c}`" for c in ARTIFACT_COLUMNS)
    + ") VALUES ("
    + ",".join(["%s"] * len(ARTIFACT_COLUMNS))
    + ") ON DUPLICATE KEY UPDATE "
    + ",".join(f"`{c}`=VALUES(`{c}`)" for c in ARTIFACT_COLUMNS if c != "object_id")
)


# ---------------------- 配置 ----------------------

def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def get_mysql_config() -> dict:
    return {
        "host": _env("KG_MYSQL_HOST", "127.0.0.1"),
        "port": int(_env("KG_MYSQL_PORT", "3306") or 3306),
        "user": _env("KG_MYSQL_USER", "root"),
        "password": _env("KG_MYSQL_PASSWORD", ""),
        "database": _env("KG_MYSQL_DATABASE", "knowledge_graph_db"),
        "charset": "utf8mb4",
    }


# ---------------------- 数据源探测 ----------------------

def discover_inputs() -> list[Path]:
    """按优先级返回所有可用的 CSV 文件。"""
    candidates: list[Path] = []
    align_dir = ROOT / "data_processing" / "alignment"
    clean_dir = ROOT / "data_processing" / "cleaning"
    raw_dir = ROOT / "crawlers" / "data" / "raw"

    # 1) alignment（含 aligned_* 列）
    if align_dir.exists():
        candidates.extend(sorted(align_dir.glob("clean_*.csv")))
    # 2) cleaning（已清洗）
    if not candidates and clean_dir.exists():
        candidates.extend(sorted(clean_dir.glob("clean_*.csv")))
    # 3) raw（最后的兜底）
    if not candidates and raw_dir.exists():
        candidates.extend(sorted(raw_dir.glob("*.csv")))
    return candidates


# ---------------------- CSV 行 → DB 行 ----------------------

def _coalesce(row: dict, *keys: str) -> str:
    for k in keys:
        v = row.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s and s.lower() not in {"none", "null", "nan"}:
            return s
    return ""


def normalize_row(row: dict) -> dict | None:
    """提取 15 列；object_id / title / detail_url 任一缺失则丢弃。"""
    obj_id = _coalesce(row, "object_id")
    if not obj_id:
        return None

    out = {}
    for col in ARTIFACT_COLUMNS:
        if col in ALIGNED_OVERRIDES:
            out[col] = _coalesce(row, ALIGNED_OVERRIDES[col], col)
        else:
            out[col] = _coalesce(row, col)

    if not out["title"]:
        return None

    # crawl_date 必须能转为 DATE，否则置 NULL
    cd = out["crawl_date"]
    out["crawl_date"] = cd if (len(cd) == 10 and cd[4] == "-" and cd[7] == "-") else None

    # MEDIUMTEXT description 不需要长度截断；其它字段做安全截断
    limits = {
        "title": 510, "period": 250, "type": 120, "material": 250,
        "dimensions": 250, "museum": 250, "location": 250,
        "detail_url": 1020, "image_url": 1020, "image_path": 510,
        "credit_line": 510, "accession_number": 120, "object_id": 120,
    }
    for col, lim in limits.items():
        if isinstance(out[col], str) and len(out[col]) > lim:
            out[col] = out[col][:lim]
    return out


def iter_rows(paths: Iterable[Path]) -> Iterator[dict]:
    for p in paths:
        with p.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                yield row


# ---------------------- DB 操作 ----------------------

def ensure_database(cfg: dict) -> None:
    """先连不带 database 的连接，建库再退出。"""
    conn = pymysql.connect(
        host=cfg["host"], port=cfg["port"],
        user=cfg["user"], password=cfg["password"],
        charset=cfg["charset"],
    )
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_DB_SQL.format(db=cfg["database"]))
        conn.commit()
    finally:
        conn.close()


def ensure_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(CREATE_TABLE_SQL)
    conn.commit()


def upsert_rows(conn, rows: list[dict], batch: int = 500) -> tuple[int, int]:
    inserted = 0
    skipped = 0
    buf: list[tuple] = []

    def flush() -> None:
        nonlocal inserted
        if not buf:
            return
        with conn.cursor() as cur:
            cur.executemany(UPSERT_SQL, buf)
        conn.commit()
        inserted += len(buf)
        buf.clear()

    for r in rows:
        if r is None:
            skipped += 1
            continue
        buf.append(tuple(r[c] for c in ARTIFACT_COLUMNS))
        if len(buf) >= batch:
            flush()
    flush()
    return inserted, skipped


# ---------------------- 主流程 ----------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="构建 / 同步 MySQL 文物表")
    parser.add_argument("--inputs", nargs="*", help="自定义输入 CSV，留空则自动探测")
    parser.add_argument("--create-only", action="store_true", help="仅建库建表")
    parser.add_argument("--batch", type=int, default=500, help="批量 upsert 大小")
    args = parser.parse_args(argv)

    cfg = get_mysql_config()
    print(f"[mysql] connecting {cfg['user']}@{cfg['host']}:{cfg['port']}/{cfg['database']}")

    ensure_database(cfg)
    conn = pymysql.connect(**cfg, cursorclass=pymysql.cursors.DictCursor)
    try:
        ensure_table(conn)
        if args.create_only:
            print("[mysql] schema ready, skip data load.")
            return 0

        if args.inputs:
            paths = [Path(p) for p in args.inputs]
        else:
            paths = discover_inputs()

        if not paths:
            print("[mysql] 未发现可用输入 CSV，跳过数据导入。")
            return 0

        print("[mysql] inputs:")
        for p in paths:
            print(f"  - {p.relative_to(ROOT) if p.is_absolute() else p}")

        rows_iter = (normalize_row(r) for r in iter_rows(paths))
        ok, skipped = upsert_rows(conn, rows_iter, batch=args.batch)
        print(f"[mysql] upserted={ok}, skipped(invalid)={skipped}")

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM artifacts")
            total = cur.fetchone()["c"]
        print(f"[mysql] artifacts total rows = {total}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
