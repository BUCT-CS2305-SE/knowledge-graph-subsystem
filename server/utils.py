"""通用工具：年代解析、URL 构造、占位 SVG、图片路径解析、Neo4j 关联查询、pHash、双语本地化。"""

from __future__ import annotations

import os
import re
from typing import Optional

from .config import app_config
from .db import get_neo4j_driver, mysql_cursor


DEFAULT_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' width='640' height='480' "
    "viewBox='0 0 640 480'>"
    "<rect width='100%' height='100%' fill='#f2f2f2'/>"
    "<text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' "
    "font-family='Arial, sans-serif' font-size='24' fill='#666'>No Image</text>"
    "</svg>"
)

# zh ↔ en 的字段镜像表（key 为响应字段名 / DB 列名；values=英文列名）
LANG_FIELDS = {
    "title": "title_en",
    "period": "period_en",
    "type": "type_en",
    "material": "material_en",
    "description": "description_en",
    "credit_line": "credit_line_en",
}


def normalize_lang(lang: Optional[str]) -> str:
    """统一为 'zh' / 'en'；其它一律视为 zh（默认中文）。"""
    if isinstance(lang, str) and lang.lower() in ("en", "english", "en-us", "en_us"):
        return "en"
    return "zh"


def localize_row(row: dict, lang: str) -> dict:
    """根据 lang 将中文主列 / 英文列对调；空英文列自动回退到中文。

    返回新 dict（浅拷贝），不修改入参。
    """
    if not row:
        return row
    out = dict(row)
    if normalize_lang(lang) != "en":
        return out
    for zh_key, en_key in LANG_FIELDS.items():
        en_val = (out.get(en_key) or "").strip() if isinstance(out.get(en_key), str) else out.get(en_key)
        if en_val:
            out[zh_key] = en_val
        # 否则保留 zh 主列内容（回退）
    return out


def parse_period_year(period_value: Optional[str]) -> Optional[int]:
    if not isinstance(period_value, str) or not period_value.strip():
        return None
    value = period_value.replace("\u2013", "-")

    bc_match = re.search(r"(\d{1,4})\s*(BC|BCE)", value, re.IGNORECASE)
    if bc_match:
        return -int(bc_match.group(1))

    year_match = re.search(r"(\d{3,4})", value)
    if year_match:
        return int(year_match.group(1))
    return None


def build_thumbnail_url(object_id) -> str:
    return f"/api/images/{object_id}/thumbnail?size=200x200"


def build_original_url(object_id) -> str:
    return f"/api/images/{object_id}/original"


def get_artifact_row(object_id: str) -> Optional[dict]:
    with mysql_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM artifacts WHERE object_id = %s", (object_id,)
        )
        return cursor.fetchone()


def resolve_image_path(object_id: str) -> Optional[str]:
    row = get_artifact_row(object_id)
    if not row:
        return None
    image_path = row.get("image_path", "")
    if not image_path:
        return None
    abs_path = os.path.join(app_config.project_root, image_path)
    return abs_path if os.path.exists(abs_path) else None


def get_related_entities(object_id: str) -> list[dict]:
    """从 Neo4j 读取与该文物直接相连的实体；任何异常都吞掉，返回空列表。"""
    try:
        driver = get_neo4j_driver()
        with driver.session() as session:
            cypher = (
                "MATCH (a:Artifact {id: $obj_id})-[r]->(connected) "
                "RETURN type(r) AS relation, "
                "connected.name AS entity_name, "
                "labels(connected)[0] AS entity_type"
            )
            result = session.run(cypher, obj_id=str(object_id))
            return [
                {
                    "relation": record["relation"],
                    "name": record["entity_name"],
                    "type": record["entity_type"],
                }
                for record in result
            ]
    except Exception:
        return []


def build_artifact_list_item(row: dict, lang: str = "zh") -> dict:
    r = localize_row(row, lang)
    return {
        "id": r.get("object_id"),
        "name": r.get("title", ""),
        "thumbnail_url": build_thumbnail_url(r.get("object_id")),
        "period": r.get("period", ""),
        "museum": {
            "name": r.get("museum", ""),
            "location": r.get("location", ""),
        },
        "lang": normalize_lang(lang),
    }


# ---------- pHash（Perceptual Hash，用于以图搜图） ----------

def compute_phash(image_bytes: bytes) -> Optional[str]:
    """计算图片的 64-bit pHash，返回 16 位十六进制字符串。失败返回 None。

    依赖：Pillow + numpy（轻量，无需 PyTorch / CLIP / FAISS）。
    """
    try:
        import io

        import numpy as np
        from PIL import Image
    except Exception:
        return None
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("L").resize(
            (32, 32), Image.LANCZOS
        )
        pixels = np.asarray(img, dtype=np.float32)
        # 2D DCT-II（仅取左上 8x8 低频）
        dct_rows = np.fft.fft(pixels, axis=1).real
        dct = np.fft.fft(dct_rows, axis=0).real
        block = dct[:8, :8]
        # 排除 DC 分量后求中位数
        flat = block.flatten()
        med = np.median(flat[1:])
        bits = (flat > med).astype(int)
        value = 0
        for b in bits:
            value = (value << 1) | int(b)
        return f"{value:016x}"
    except Exception:
        return None


def hamming64(hex_a: str, hex_b: str) -> int:
    """两个 16 位十六进制 pHash 的 Hamming 距离（0~64，越小越相似）。"""
    try:
        return bin(int(hex_a, 16) ^ int(hex_b, 16)).count("1")
    except Exception:
        return 64
