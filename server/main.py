"""FastAPI 应用入口：创建 app、注册全局异常、CORS、挂载路由、收尾资源。"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from .auth import verify_token
from .config import app_config
from .db import close_neo4j_driver
from .routers import (
    admin,
    artifacts,
    graph,
    image_search,
    images,
    qa,
    recommend,
    search,
    stats,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title=app_config.title,
        description=app_config.description,
        version=app_config.version,
    )

    # 跨域：Web 子系统 / 掌上博物馆 App / 后台管理子系统 通常部署在不同域
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") and path != "/api/health":
            try:
                verify_token(
                    request.headers.get("Authorization"),
                    request.headers.get("X-Token"),
                    allowed_user_types=["ADMIN", "PLATFORM_USER"],
                )
            except FastAPIHTTPException as exc:
                detail = exc.detail
                if isinstance(detail, dict) and "code" in detail and "message" in detail:
                    return JSONResponse(status_code=exc.status_code, content=detail)
                return JSONResponse(
                    status_code=exc.status_code,
                    content={"code": exc.status_code, "message": str(detail)},
                )
        return await call_next(request)

    @app.exception_handler(FastAPIHTTPException)
    async def http_exception_handler(
        request: Request, exc: FastAPIHTTPException
    ) -> JSONResponse:
        if (
            isinstance(exc.detail, dict)
            and "code" in exc.detail
            and "message" in exc.detail
        ):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.status_code, "message": str(exc.detail)},
        )

    # 基础功能接口（基础检索 + 详情）
    app.include_router(artifacts.router)
    app.include_router(search.router)
    app.include_router(images.router)
    app.include_router(stats.router)
    # 扩展（供其它 4 个子系统）
    app.include_router(image_search.router)   # 以图搜图（移动端 + Web）
    app.include_router(recommend.router)      # 相关推荐 + 文物对比（Web + 移动端）
    app.include_router(graph.router)          # 力导向图 / 时间轴 / 地理（Web 可视化）
    app.include_router(qa.router)             # 模板 Cypher + RAG 上下文（问答）
    app.include_router(admin.router)          # CRUD + 一致性检查（后台管理）

    @app.get("/api/health", tags=["Meta"])
    def health():
        return {"status": "ok", "version": app_config.version}

    # 让 /docs 显示 Authorize 按钮，方便联调时把 admin 签发的 JWT 粘进去
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        schema.setdefault("components", {})["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "在 Value 中粘贴 admin 登录返回的 token（无需带 'Bearer ' 前缀）",
            }
        }
        for path, methods in schema.get("paths", {}).items():
            if path == "/api/health":
                continue
            for op in methods.values():
                if isinstance(op, dict):
                    op.setdefault("security", [{"BearerAuth": []}])
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi

    @app.on_event("shutdown")
    def _on_shutdown() -> None:
        close_neo4j_driver()

    return app


app = create_app()