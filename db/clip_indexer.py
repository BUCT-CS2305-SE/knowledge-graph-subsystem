"""
CLIP + FAISS 离线索引构建器：扫描 MySQL `artifacts.image_path`，
用 CLIP-ViT-B/32 提取 512 维特征，写入 FAISS 内积索引（向量已 L2 归一化）。

依赖：
    pip install torch torchvision transformers faiss-cpu pillow pymysql

CLI：
    python3 db/clip_indexer.py                # 全量构建
    python3 db/clip_indexer.py --limit 1000   # 调试
    python3 db/clip_indexer.py --batch 32

输出：
    $KG_CLIP_INDEX_DIR/artifacts.faiss
    $KG_CLIP_INDEX_DIR/artifacts.ids.txt   行号 → object_id
默认 KG_CLIP_INDEX_DIR = <project>/data/clip_index
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import numpy as np
    import pymysql
except ImportError:
    print("ERROR: pip install pymysql numpy", file=sys.stderr)
    raise


def get_conn():
    return pymysql.connect(
        host=os.environ.get("KG_MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("KG_MYSQL_PORT", "3306")),
        user=os.environ.get("KG_MYSQL_USER", "root"),
        password=os.environ.get("KG_MYSQL_PASSWORD", ""),
        database=os.environ.get("KG_MYSQL_DATABASE", "knowledge_graph_db"),
        cursorclass=pymysql.cursors.DictCursor,
    )


def build(batch: int, limit: int | None) -> None:
    try:
        import faiss
        import torch
        from PIL import Image
        from transformers import CLIPModel, CLIPProcessor
    except ImportError as e:
        print(f"ERROR: {e}\n请先：pip install torch transformers faiss-cpu pillow",
              file=sys.stderr)
        sys.exit(1)

    project_root = os.environ.get("KG_PROJECT_ROOT", str(ROOT))
    index_dir = Path(os.environ.get(
        "KG_CLIP_INDEX_DIR",
        os.path.join(project_root, "data", "clip_index"),
    ))
    index_dir.mkdir(parents=True, exist_ok=True)
    model_name = os.environ.get("KG_CLIP_MODEL", "openai/clip-vit-base-patch32")

    print(f"[clip] loading model: {model_name}")
    model = CLIPModel.from_pretrained(model_name).eval()
    processor = CLIPProcessor.from_pretrained(model_name)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    print(f"[clip] device = {device}")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            sql = (
                "SELECT object_id, image_path FROM artifacts "
                "WHERE image_path <> ''"
            )
            if limit:
                sql += f" LIMIT {int(limit)}"
            cur.execute(sql)
            rows = cur.fetchall()
    finally:
        conn.close()

    vecs: list[np.ndarray] = []
    ids: list[str] = []
    miss = fail = 0

    def flush_batch(imgs, batch_ids):
        nonlocal fail
        if not imgs:
            return
        try:
            inputs = processor(images=imgs, return_tensors="pt").to(device)
            with torch.no_grad():
                feats = model.get_image_features(**inputs)
                feats = feats / feats.norm(dim=-1, keepdim=True)
            arr = feats.cpu().numpy().astype("float32")
            for v, oid in zip(arr, batch_ids):
                vecs.append(v)
                ids.append(oid)
        except Exception as e:
            print(f"  [batch fail] {e}")
            fail += len(imgs)

    pending_imgs: list = []
    pending_ids: list[str] = []
    total = len(rows)
    for i, row in enumerate(rows, 1):
        rel = row["image_path"]
        abs_path = os.path.join(project_root, rel)
        if not os.path.exists(abs_path):
            miss += 1
            continue
        try:
            img = Image.open(abs_path).convert("RGB")
        except Exception:
            fail += 1
            continue
        pending_imgs.append(img)
        pending_ids.append(row["object_id"])
        if len(pending_imgs) >= batch:
            flush_batch(pending_imgs, pending_ids)
            pending_imgs, pending_ids = [], []
            print(f"  [{i}/{total}] kept={len(ids)} miss={miss} fail={fail}")
    flush_batch(pending_imgs, pending_ids)

    if not vecs:
        print("[clip] no vectors generated, abort.")
        sys.exit(1)

    matrix = np.vstack(vecs).astype("float32")
    dim = matrix.shape[1]
    index = faiss.IndexFlatIP(dim)  # 向量已归一化，内积 == 余弦
    index.add(matrix)
    faiss.write_index(index, str(index_dir / "artifacts.faiss"))
    (index_dir / "artifacts.ids.txt").write_text(
        "\n".join(ids), encoding="utf-8"
    )
    print(
        f"[clip] DONE total={total} indexed={len(ids)} miss={miss} fail={fail} "
        f"-> {index_dir}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="CLIP+FAISS indexer")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    build(args.batch, args.limit)


if __name__ == "__main__":
    main()
