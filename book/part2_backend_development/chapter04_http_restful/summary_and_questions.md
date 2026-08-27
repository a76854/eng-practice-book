---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

## 本章小结

- **HTTP 是语义契约，而非传输管道**：方法（GET/POST/PUT/PATCH/DELETE）承载安全性与幂等性，状态码（200/201/204/400/404/409/422/500）划分责任，Header 承载内容协商、缓存与追踪。幂等性直接决定重试与网关策略，状态码让调用方“按码决策”而非猜测。
- **RESTful 成熟度是约束的叠加**：Level 0（单一入口）到 Level 1（资源）解决可寻址，到 Level 2（动词+状态码）让基础设施可理解语义，到 Level 3（Hypermedia）提供运行时自发现。本书以 MeetingToText 的 `backend/app/routers` 为例，选择 Level 2 为默认水位，Level 3 按“是否需向第三方提供可发现 API”按需取舍。
- **FastAPI 路由是声明式契约**：路径参数定位资源、查询参数修饰集合、请求体承载载荷，三者在函数签名与 `BaseModel` 中以类型标注声明，`Field` 约束在边界自动校验并以 `422` 暴露，`Depends` 让分页、鉴权与存在性检查可复用、可测试。
- **统一信封让协作可收敛**：`code/data/msg` 的成功/失败信封叠加 `@app.exception_handler` 对 `HTTPException / RequestValidationError / Exception` 的三类收敛，使校验错误、业务冲突与未捕获异常在同一形状下被前端可靠消费，日志与监控亦可按 `code` 聚合。
- **OpenAPI 让文档即真相**：`openapi.json` 由 Pydantic 与路由签名自动生成，`TestClient` 对该契约的路径、方法、请求体与响应形状做本地断言即是契约测试，文档漂移在 CI 中即被捕获，前端可据此生成类型与客户端，实现契约驱动的并行开发。
- **贯穿启示**：本章的“HTTP 语义—成熟度—路由校验—统一响应—契约测试”五步，把 [第3章的分层思想](../chapter03_backend_essence/3.5_layered_architecture.md) 落到可执行的协作闭环——契约在代码中可验证，在文档中不漂移，在联调中不猜测。

## 思考题

1. **幂等性设计**：`POST /tasks` 重复创建返回 `409`，若改为“重复创建直接返回已有任务的 `200`”是否也算幂等？两种设计对前端重试与去重的语义有何不同？在什么场景下你会选择后者？
2. **状态码的取舍**：`400` 与 `422` 都可表示“客户端错”，团队若统一只用 `400` 会失去什么信息？网关按状态码做限流与监控时，`422` 相比 `400` 能带来哪些可观测性收益？
3. **成熟度的代价**：在前后端同团队、由 `openapi.json` 生成客户端的闭环中，Level 3 的 `links` 自发现还能带来多少边际收益？若 API 需向第三方开放，`links` 的设计会如何影响版本演进与客户端兼容性？
4. **参数分工**：`GET /tasks?ids=t1,t2,t3` 与 `POST /tasks/batch {ids: [...]}` 在语义与基础设施（缓存、URL 长度、幂等性）上有何 trade-off？MeetingToText 的批量查询若由你设计，会选哪一种？
5. **校验的边界**：`Field(ge/le/pattern)` 能拦截形状错误，但“任务标题不能与已有任务重复”是否应放在 Pydantic 层？结合分层思想，讨论形状校验与业务规则校验的分工与测试策略。
6. **信封与 HTTP 状态码**：本书采用“HTTP 状态码 + Body 的 `code` 双轨”——HTTP 供网关与监控聚合，Body 供前端业务分支。若改为“HTTP 始终 200，靠 Body 的 `code` 区分”，会对网关重试、CDN 缓存与错误监控带来哪些影响？
7. **契约演进**：后端为 `TaskOut` 新增一个必填字段而前端尚未更新，契约测试会在哪一环失败？应如何通过“新增字段设为可选/默认值 + 版本协商”降低协作成本？`openapi.json` 的 `required` 变更在代码生成器中会如何体现？

示例（本章贯通校验：HTTP 语义 + 路由校验 + 信封 + 契约的最小闭环）：

```{code-cell} ipython3
import tempfile, pathlib
from typing import Any, Annotated

from fastapi import FastAPI, HTTPException, Request, Query, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from m2t.store import TaskStore

tmpdir = tempfile.TemporaryDirectory()
db_path = pathlib.Path(tmpdir.name) / "summary.db"
store = TaskStore(db_path)

class TaskCreateIn(BaseModel):
    task_id: str = Field(min_length=1, max_length=64)
    filename: str = Field(min_length=1)

class TaskOut(BaseModel):
    id: str
    filename: str
    status: str

class Envelope(BaseModel):
    code: int
    data: Any | None = None
    msg: str

def ok(data: Any, msg: str = "ok") -> dict:
    return Envelope(code=0, data=data, msg=msg).model_dump()

app = FastAPI(title="Chapter04 Summary", version="0.1.0")

@app.exception_handler(HTTPException)
async def http_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content=Envelope(code=exc.status_code, data=None, msg=str(exc.detail)).model_dump())

@app.exception_handler(RequestValidationError)
async def val_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {"msg": "validation error"}
    loc = ".".join(str(x) for x in first.get("loc", []))
    return JSONResponse(status_code=422, content=Envelope(code=422, data=None, msg=f"validation failed at {loc}").model_dump())

@app.exception_handler(Exception)
async def catch_all(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content=Envelope(code=500, data=None, msg="internal error").model_dump())

@app.post("/tasks", status_code=status.HTTP_201_CREATED)
def create(payload: TaskCreateIn):
    if store.get(payload.task_id) is not None:
        raise HTTPException(status_code=409, detail="already exists")
    store.create(payload.task_id, payload.filename)
    row = store.get(payload.task_id)
    assert row is not None
    return ok({"id": row["id"], "filename": row["filename"], "status": row["status"]}, msg="created")

@app.get("/tasks/{task_id}")
def get_one(task_id: str):
    row = store.get(task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="not found")
    return ok({"id": row["id"], "filename": row["filename"], "status": row["status"]})

@app.get("/tasks")
def list_tasks(limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0):
    rows = store.list_tasks(limit=100)
    sliced = rows[offset:offset+limit]
    return ok([{"id": r["id"], "filename": r["filename"], "status": r["status"]} for r in sliced])

client = TestClient(app, raise_server_exceptions=False)

# 1) 创建 → 201 + 信封 code=0
r1 = client.post("/tasks", json={"task_id": "sum1", "filename": "meeting.wav"})
print("create sum1:", r1.status_code, r1.json()["code"])
assert r1.status_code == 201
assert r1.json()["code"] == 0

# 2) 查询 → 200 + 信封
r2 = client.get("/tasks/sum1")
print("get sum1:", r2.json()["data"]["filename"])
assert r2.json()["data"]["filename"] == "meeting.wav"

# 3) 校验 → 422 信封（Pydantic 边界）
r3 = client.post("/tasks", json={"task_id": "", "filename": "x.wav"})
print("validation:", r3.status_code, r3.json()["code"])
assert r3.status_code == 422

# 4) 冲突 → 409 信封（业务规则）
r4 = client.post("/tasks", json={"task_id": "sum1", "filename": "dup.wav"})
print("conflict:", r4.status_code, r4.json()["code"])
assert r4.status_code == 409

# 5) 分页查询参数（Query 校验 + 信封）
r5 = client.get("/tasks?limit=1&offset=0")
print("list:", r5.json()["code"], len(r5.json()["data"]))
assert r5.json()["code"] == 0

# 6) 契约：openapi.json 包含关键路径
openapi = client.get("/openapi.json").json()
assert "/tasks" in openapi["paths"]
assert "/tasks/{task_id}" in openapi["paths"]
print("openapi paths:", sorted(openapi["paths"].keys())[:3])

# 7) 统一性：所有响应均含 code/data/msg
for r in [r1, r2, r3, r4, r5]:
    assert "code" in r.json() and "data" in r.json() and "msg" in r.json()
print("贯通校验通过：HTTP/路由/信封/契约在同一闭环中可回归")
tmpdir.cleanup()
# 预期输出:
# create sum1: 201 0
# get sum1: meeting.wav
# validation: 422 422
# conflict: 409 409
# list: 0 1
# openapi paths: ['/tasks', '/tasks/{task_id}', ...]
# 贯通校验通过：HTTP/路由/信封/契约在同一闭环中可回归
```

```bash
# 贯通验证
.venv/bin/python -c "from m2t.store import TaskStore; print('summary demo ok')"
```
