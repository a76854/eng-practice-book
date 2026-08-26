# 认证作业：给 M2 加 Bearer Token 中间件

> 本作业为周15「健壮性与安全基础」的认证留作业。正文不实现认证，答案在 `auth_solution/`。

## 任务

给 M2 的 FastAPI 应用加一个最小可用的 **Bearer Token 中间件**（或依赖），满足以下规约：

- **规约 1**：对所有 `/api/*` 请求，若未携带 `Authorization: Bearer {token}` 或 token 错误，返回 `401 Unauthorized`，响应体为 `{"detail": "Unauthorized"}`（或等价的 401 JSON）。
- **规约 2**：携带正确 token（与服务端约定值 `test-token` 或环境变量 `MTT_API_TOKEN`）时放行，业务逻辑正常返回 `200`。
- **规约 3**：非 `/api/*`（如 `/`, `/docs`, 静态资源）不鉴权，直接放行。
- **规约 4**：实现为纯 ASGI 中间件或 FastAPI `Depends`，不依赖外部服务、不讲密码学（token 明文比对即可）。

## 提交

- 代码落在 `auth_solution/`（参考解已提供，仅作对照；你的实现可自命名）。
- 测试用 `TestClient` 进程内驱动，至少覆盖：未带 token → 401、带错误 token → 401、带正确 token → 200。

## 提示

- 参考 MeetingToText 的 `backend/app/middleware/ratelimit.py` 纯 ASGI 写法与 `backend/app/server.py` 的 `app.add_middleware` 挂载顺序。
- 401 分支若涉及 CORS，需与 `CORSMiddleware` 的挂载顺序一并考虑（否则跨源 401 会被浏览器误判为 CORS 失败）。

## 评分

- `pytest auth_solution/ -q` 绿，且包含对 401 的显式断言。
