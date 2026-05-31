"""图片代理：原图 / 缩略图。本地缺图回退到内嵌 SVG 占位图。"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, Response

from ..utils import DEFAULT_SVG, resolve_image_path

router = APIRouter(prefix="/api/images", tags=["MVP"])

_CACHE_HEADERS = {"Cache-Control": "public, max-age=86400"}


@router.get("/{object_id}/original", summary="原始图片")
def get_image_original(object_id: str):
    """获取原始图片（二进制流）。"""
    image_path = resolve_image_path(object_id)
    if image_path:
        return FileResponse(image_path, headers=_CACHE_HEADERS)
    return Response(
        content=DEFAULT_SVG, media_type="image/svg+xml", headers=_CACHE_HEADERS
    )


@router.get("/{object_id}/thumbnail", summary="缩略图")
def get_image_thumbnail(object_id: str, size: str = Query("200x200")):
    """获取缩略图（MVP 与原图同源，size 仅作客户端标记）。"""
    image_path = resolve_image_path(object_id)
    if image_path:
        return FileResponse(image_path, headers=_CACHE_HEADERS)
    return Response(
        content=DEFAULT_SVG, media_type="image/svg+xml", headers=_CACHE_HEADERS
    )
