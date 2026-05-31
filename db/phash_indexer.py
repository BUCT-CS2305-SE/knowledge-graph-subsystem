"""
图像感知哈希（pHash）离线索引构建器：扫描已下载图片，生成 64-bit pHash
并写回 MySQL `artifacts.phash` 列，供"以图搜图"使用（掌上博物馆 + Web）。

依赖：
    pip install pillow numpy pymysql

CLI：
    python3 db/phash_indexer.py                # 全量重建（仅处理 phash 为空的行）
    python3 db/phash_indexer.py --rebuild      # 强制重算所有
    python3 db/phash_indexer.py --limit 1000   # 调试用

环境变量：复用 KG_MYSQL_*。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import pymysql
except ImportError:
    print("ERROR: pip install pymysql", file=sys.stderr)
    raise

from server.utils import compute_phash  # noqa: E402


def get_conn():
    return pymysql.connect(
        host=os.environ.get("KG_MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("KG_MYSQL_PORT", "3306")),
        user=os.environ.get("KG_MYSQL_USER", "root"),
        password=os.environ.get("KG_MYSQL_PASSWORD", ""),
        database=os.environ.get("KG_MYSQL_DATABASE", "knowledge_graph_db"),
        cursorclass=pymysql.cursors.DictCursor,
    )


def build(rebuild: bool, limit: int | None) -> None:
    project_root = os.environ.get("KG_PROJECT_ROOT", str(ROOT))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            sql = (
                "SELECT object_id, image_path FROM artifacts "
                "WHERE image_path <> ''"
            )
            if not rebuild:
                sql += " AND (phash IS NULL OR phash = '')"
            if limit:
                sql += f" LIMIT {int(limit)}"
            cur.execute(sql)
            rows = cur.fetchall()

        total = len(rows)
        ok = miss = fail = 0
        for i, row in enumerate(rows, 1):
            rel = row["image_path"]
            abs_path = os.path.join(project_root, rel)
            if not os.path.exists(abs_path):
                miss += 1
                continue
            try:
                with open(abs_path, "rb") as f:
                    h = compute_phash(f.read())
            except Exception:
                h = None
            if not h:
                fail += 1
                continue
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE artifacts SET phash = %s WHERE object_id = %s",
                    (h, row["object_id"]),
                )
            ok += 1
            if i % 200 == 0:
                conn.commit()
                print(f"  [{i}/{total}] ok={ok} miss={miss} fail={fail}")
        conn.commit()
        print(f"DONE: total={total} ok={ok} miss={miss} fail={fail}")
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="pHash indexer")
    ap.add_argument("--rebuild", action="store_true", help="强制重算所有")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    build(args.rebuild, args.limit)


if __name__ == "__main__":
    main()
