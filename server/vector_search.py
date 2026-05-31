"""
CLIP + FAISS 语义检索封装。

设计要点：
- 懒加载：进程启动时不加载模型，首次调用时再 import torch 与初始化。
- 优雅降级：torch / faiss / transformers 任一缺失，外层自动 fallback 到 pHash。
- 索引格式：保存 (D=512) float32 向量 + id 列表到 KG_CLIP_INDEX_DIR。
  - artifacts.faiss   FAISS L2 归一化后等价于内积
  - artifacts.ids.txt 行号 → object_id 映射
"""

from __future__ import annotations

import io
import os
import threading
from pathlib import Path
from typing import Optional

from .config import app_config

# ---------- 索引文件位置 ----------

INDEX_DIR = Path(
    os.environ.get(
        "KG_CLIP_INDEX_DIR",
        os.path.join(app_config.project_root, "data", "clip_index"),
    )
)
INDEX_FILE = INDEX_DIR / "artifacts.faiss"
IDS_FILE = INDEX_DIR / "artifacts.ids.txt"

CLIP_MODEL_NAME = os.environ.get(
    "KG_CLIP_MODEL", "openai/clip-vit-base-patch32"
)
EMB_DIM = 512  # ViT-B/32

# ---------- 全局单例（懒加载 + 线程安全） ----------

_lock = threading.Lock()
_model = None
_processor = None
_torch = None
_faiss = None
_index = None
_ids: list[str] = []


def is_available() -> bool:
    """探测依赖是否齐全。供路由层判断是否启用 CLIP 模式。"""
    try:
        import faiss  # noqa: F401
        import torch  # noqa: F401
        from transformers import CLIPModel, CLIPProcessor  # noqa: F401
    except Exception:
        return False
    return True


def _ensure_model():
    """懒加载 CLIP 模型与 processor。"""
    global _model, _processor, _torch
    if _model is not None:
        return
    with _lock:
        if _model is not None:
            return
        import torch
        from transformers import CLIPModel, CLIPProcessor

        _torch = torch
        _model = CLIPModel.from_pretrained(CLIP_MODEL_NAME).eval()
        _processor = CLIPProcessor.from_pretrained(CLIP_MODEL_NAME)


    def _to_tensor(features):
        # Handle different transformers outputs across versions.
        if hasattr(features, "image_embeds"):
            return features.image_embeds
        if hasattr(features, "pooler_output"):
            return features.pooler_output
        if hasattr(features, "last_hidden_state"):
            return features.last_hidden_state[:, 0, :]
        if isinstance(features, (tuple, list)) and features:
            return features[0]
        return features


def encode_image_bytes(raw: bytes) -> Optional[list[float]]:
    """把图片二进制编码为 512 维向量（已 L2 归一化）。失败返回 None。"""
    if not is_available():
        return None
    try:
        from PIL import Image
    except Exception:
        return None
    try:
        _ensure_model()
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        inputs = _processor(images=img, return_tensors="pt")
        with _torch.no_grad():
            feats = _to_tensor(_model.get_image_features(**inputs))
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats[0].cpu().numpy().tolist()
    except Exception:
        return None


def encode_text(text: str) -> Optional[list[float]]:
    """文本 → 同一语义空间的 512 维向量（用于"以文搜图"）。"""
    if not is_available() or not text.strip():
        return None
    try:
        _ensure_model()
        inputs = _processor(text=[text], return_tensors="pt", padding=True)
        with _torch.no_grad():
            feats = _to_tensor(_model.get_text_features(**inputs))
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats[0].cpu().numpy().tolist()
    except Exception:
        return None


# ---------- FAISS 索引 ----------

def _ensure_index() -> bool:
    """懒加载 FAISS 索引。索引不存在时返回 False。"""
    global _index, _ids, _faiss
    if _index is not None:
        return True
    if not INDEX_FILE.exists() or not IDS_FILE.exists():
        return False
    with _lock:
        if _index is not None:
            return True
        try:
            import faiss

            _faiss = faiss
            _index = faiss.read_index(str(INDEX_FILE))
            _ids = IDS_FILE.read_text(encoding="utf-8").splitlines()
        except Exception:
            return False
    return True


def reload_index() -> None:
    """构建器写完索引后调用，让 API 进程下次查询时重新加载。"""
    global _index, _ids
    with _lock:
        _index = None
        _ids = []


def search_vector(vec: list[float], top_k: int = 20) -> list[tuple[str, float]]:
    """用归一化向量检索，返回 [(object_id, score), ...]，按相似度降序。"""
    if not _ensure_index():
        return []
    try:
        import numpy as np

        q = np.asarray([vec], dtype="float32")
        scores, idxs = _index.search(q, top_k)
        out: list[tuple[str, float]] = []
        for s, i in zip(scores[0].tolist(), idxs[0].tolist()):
            if i < 0 or i >= len(_ids):
                continue
            out.append((_ids[i], float(s)))
        return out
    except Exception:
        return []


def index_size() -> int:
    return len(_ids) if _ensure_index() else 0
