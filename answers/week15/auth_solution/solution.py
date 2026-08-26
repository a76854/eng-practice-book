"""week15 认证作业参考解：Bearer Token 中间件（hermetic，TestClient）。

规约：给 M2 加 Bearer token 中间件，未带 token -> 401。
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

VALID_TOKEN = "test-token"


class BearerAuthMiddleware:
    """纯 ASGI Bearer 鉴权中间件。

    仅对 /api/* 生效；未带正确 Authorization: Bearer {VALID_TOKEN} 返回 401。
    """

    def __init__(self, app: Any, token: str = VALID_TOKEN) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")
        if not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return
        # 提取 Authorization 头
        auth: str | None = None
        for k, v in scope.get("headers") or []:
            if k.lower() == b"authorization":
                try:
                    auth = v.decode("latin-1")
                except Exception:
                    auth = None
                break
        expected = f"Bearer {self.token}"
        if auth != expected:
            body = json.dumps({"detail": "Unauthorized"}).encode("utf-8")
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)


def create_app(token: str = VALID_TOKEN) -> FastAPI:
    """创建带鉴权中间件的最小 M2 演示应用。"""
    app = FastAPI(title="m2 auth demo")

    app.add_middleware(BearerAuthMiddleware, token=token)

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/tasks")
    def list_tasks() -> dict:
        return {"tasks": []}

    @app.get("/")
    def root() -> dict:
        return {"msg": "public"}

    @app.get("/docs")
    def docs_alias() -> dict:
        return {"msg": "docs public"}

    return app


# 默认应用实例（供直接导入测试）
app = create_app()
