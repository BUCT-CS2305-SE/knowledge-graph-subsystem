"""
回填 artifacts.image_path 列。
扫描 crawlers/data/raw/images/ 下所有图，按文件名（= safe(object_id)）匹配。
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pymysql

ROOT = Path(__file__).resolve().parents[1]
IMG_ROOT = ROOT / "crawlers" / "data" / "raw" / "images"

DB = dict(
    host=os.getenv("KG_MYSQL_HOST", "127.0.0.1"),
    port=int(os.getenv("KG_MYSQL_PORT", "3306")),
    user=os.getenv("KG_MYSQL_USER", "root"),
    password=os.getenv("KG_MYSQL_PASSWORD", ""),
    database=os.getenv("KG_MYSQL_DATABASE", "knowledge_graph_db"),
    charset="utf8mb4",
)


def main():
    # 1) 扫所有图：{object_id_safe: relative_path}
    file_index = {}
    for museum_dir in IMG_ROOT.iterdir() if IMG_ROOT.exists() else []:
        if not museum_dir.is_dir():
            continue
        for img in museum_dir.iterdir():
            if img.is_file() and img.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                key = img.stem  # 文件名去后缀 = safe(object_id)
                rel = str(img.relative_to(ROOT)).replace("\\", "/")
                file_index[key] = rel
    print(f"[scan] found {len(file_index)} images under {IMG_ROOT}")
    if not file_index:
        print("[ERROR] no images found, abort")
        sys.exit(1)

    # 2) 取所有 object_id
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    cur.execute("SELECT object_id FROM artifacts")
    oids = [r[0] for r in cur.fetchall()]
    print(f"[db] {len(oids)} artifacts in MySQL")

    # 3) 匹配 + UPDATE
    import re
    def safe(s):
        return re.sub(r'[<>:"/\\|?*]', "_", str(s).strip())

    updates = []
    for oid in oids:
        key = safe(oid)
        if key in file_index:
            updates.append((file_index[key], oid))

    print(f"[match] {len(updates)}/{len(oids)} matched")

    if not updates:
        print("[ERROR] zero matched, check object_id naming convention")
        sys.exit(1)

    cur.executemany("UPDATE artifacts SET image_path = %s WHERE object_id = %s", updates)
    conn.commit()
    print(f"[done] updated {cur.rowcount} rows")
    cur.close(); conn.close()


if __name__ == "__main__":
    main()