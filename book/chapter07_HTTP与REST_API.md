---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: '0.13'
    jupytext_version: 1.16.4
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 第7章 HTTP 与 REST API

> 为什么这一章要放在后端篇的起点？前几章你已经会用 `m2t` 在本地把音频转成文字、导出为 `txt`/`srt`/`md`。但这些能力还锁在「命令行里」——别人要调用，必须在同一台机器上 `import m2t`。HTTP（HyperText Transfer Protocol，超文本传输协议）是把「本地函数」变成「网络服务」的通用约定；REST（Representational State Transfer，表述性状态转移）是在 HTTP 之上组织资源与动词的一套设计风格。学会它，你就能把「转写一段音频」暴露为 `GET /transcribe/{task_id}?fmt=txt` 这样的网络接口，让前端、脚本、其他服务都能通过 URL 调用。本章以 FastAPI（Python 的现代 Web 框架）为载体，完成从「函数」到「服务」的跨越；真实项目中的路由分层与 `get_task_or_404` 模式将在 7.6 节对照讲解。

## 学习目标

完成本章后，你将能够：

1. 能解释 HTTP 请求/响应的基本结构（方法、路径、查询参数、状态码、请求体/响应体），并用 `curl` 或 `TestClient` 发起请求。
2. 能用 FastAPI 定义路由（route）、声明路径参数与查询参数校验（`Query`/`Path`/`BaseModel`），并区分 200/400/404/422 的语义。
3. 能编写一个最小的 `/transcribe` 端点：复用 `m2t.export` 返回 `txt`/`srt`/`md`，对非法格式返回 400，对不存在的任务返回 404，并用 `TestClient` 在不启动服务器的情况下测试它。
4. 能解释 `response_model` 对 OpenAPI（OpenAPI Specification，开放接口规范）文档的作用，并通过 `/docs` 与 `/openapi.json` 验证接口文档是「代码生成」而非手写。

## 先修要求

- 完成 [第1章 环境与项目骨架](chapter01_环境与项目骨架.md)与 [第5章 测试的思维与工程](chapter05_测试的思维与工程.md)（会用 `pytest` 与虚拟环境）。
- 会 `import m2t.export` 并调用 `export(task, fmt)`（见 `m2t/export.py`）。
- 无需前端基础；本章所有验证均用 `fastapi.testclient.TestClient` 在进程内完成，不依赖浏览器。

## 正文

### 7.1 HTTP 快速回顾：请求、响应与状态码

HTTP 是「请求-响应」协议：客户端发一个请求（request），服务端回一个响应（response）。一个请求由四部分组成：

- **方法（method）**：`GET`（读取）、`POST`（创建/触发）、`PUT`（更新）、`DELETE`（删除）等。
- **路径（path）**：如 `/transcribe/demo123`，标识资源。
- **查询参数（query）**：`?fmt=txt&limit=10`，路径后的键值对。
- **头部（headers）与体（body）**：头部携带元信息（如 `Content-Type: application/json`），体携带 JSON 或文件。

响应则包含：

- **状态码（status code）**：三位数，首位决定类别——`2xx` 成功、`4xx` 客户端错误、`5xx` 服务端错误。常用：`200 OK`（成功）、`400 Bad Request`（参数错误）、`404 Not Found`（资源不存在）、`422 Unprocessable Entity`（校验失败，FastAPI 自动返回）。
- **头部与体**：与请求对称，体通常是 JSON。

REST 把「资源」映射到 URL，把「操作」映射到方法：`GET /tasks` 列任务，`GET /transcribe/{task_id}` 取某任务的转写结果。查询参数用于修饰返回（如 `?fmt=srt` 选格式），路径参数用于定位资源（如 `{task_id}`）。

### 7.2 FastAPI 最小应用：路由与 TestClient

FastAPI 的核心是「用装饰器把函数变成路由」。最小可运行示例——一个 `GET /ping`：

```{code-cell} ipython3
from fastapi import FastAPI
from fastapi.testclient import TestClient

app_hello = FastAPI(title="hello demo")

@app_hello.get("/ping")
def ping():
    return {"msg": "pong"}

# TestClient 在进程内“假装”发 HTTP 请求，无需启动 uvicorn
client_hello = TestClient(app_hello)
resp = client_hello.get("/ping")
print(resp.status_code)  # 200
print(resp.json())       # {'msg': 'pong'}
print(resp.headers.get("content-type"))
```

关键点：

- `FastAPI()` 创建应用对象，是所有路由的容器。
- `@app.get("/ping")` 把 `ping()` 注册为 `GET /ping` 的处理器，返回的 `dict` 自动序列化为 JSON。
- `TestClient(app)` 劫持应用的 ASGI 调用，不占端口、不起子进程，适合单测与教材演示（正文所有代码均用此方式，不调用 `uvicorn.run` 长驻）。

### 7.3 校验（validation）：Query 参数与 Pydantic 模型

「校验」指在处理器执行前拒绝非法输入。FastAPI 用两类声明式校验：

- **查询/路径参数**：`Query` / `Path`（本质是 `Annotated` 类型提示）。
- **请求体/响应体**：`pydantic.BaseModel` 子类，字段可带类型、约束与描述。

校验失败时，FastAPI 自动返回 `422`，并在响应体中列出错误位置；业务层面的「参数不合法」（如 `fmt` 不在允许列表）则应手动抛 `HTTPException(status_code=400)`，以区分「格式错误（422）」与「业务拒绝（400）」。

### 7.4 应用：暴露 `/transcribe`（复用 `m2t.export`，mock 转写）

本节把 `m2t.export` 包装为 HTTP 接口。`m2t.export(task, fmt)` 签名 `(task)->str`，支持 `txt`/`srt`/`md` 三种格式；这里用内存字典 `FAKE_DB` 模拟已完成的任务（真实项目中由 `store.get(task_id)` 查库），处理器只做三件事：查任务→校验格式→调 `export`。

```{code-cell} ipython3
from fastapi import FastAPI, Query, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from m2t.export import export

# --- mock 数据：与 m2t.export 兼容的最小任务形状 ---
def _mock_segments():
    return [
        {"speaker": "说话人1", "text": "大家好，今天讨论排期", "start": 0.0, "end": 3.2},
        {"speaker": "说话人2", "text": "我这边星期三可以", "start": 3.2, "end": 5.8},
    ]

FAKE_DB = {
    "demo123": {
        "id": "demo123",
        "filename": "meeting.wav",
        "result": {"segments": _mock_segments(), "duration": 5.8, "full_text": ""},
        "minutes": "",
    },
}

class TranscribeResponse(BaseModel):
    task_id: str
    status: str
    format: str
    content: str

app = FastAPI(title="m2t transcribe demo")


@app.get("/transcribe/{task_id}", response_model=TranscribeResponse)
def get_transcribe(
    task_id: str,
    fmt: str = Query(default="txt", description="导出格式：txt/srt/md"),
):
    # 404：任务不存在（对应 deps.py 的 get_task_or_404 语义）
    task = FAKE_DB.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    # 400：业务层校验（fmt 非法）
    if fmt not in ("txt", "srt", "md"):
        raise HTTPException(status_code=400, detail="不支持的导出格式，可选: txt/srt/md")
    content = export(task, fmt)
    return {"task_id": task_id, "status": "done", "format": fmt, "content": content}


client = TestClient(app)

# 200：合法请求，fmt=txt
r1 = client.get("/transcribe/demo123?fmt=txt")
print("200 txt:", r1.status_code, r1.json()["content"][:20])

# 200：fmt=srt，观察字幕格式
r2 = client.get("/transcribe/demo123?fmt=srt")
print("200 srt 首行:", r2.json()["content"].splitlines()[0])

# 200：fmt=md，含 Markdown 标题
r3 = client.get("/transcribe/demo123?fmt=md")
print("200 md 首行:", r3.json()["content"].splitlines()[0])

# 400：非法 fmt
r4 = client.get("/transcribe/demo123?fmt=pdf")
print("400 非法格式:", r4.status_code, r4.json()["detail"])

# 404：不存在的任务
r5 = client.get("/transcribe/notfound?fmt=txt")
print("404 不存在:", r5.status_code, r5.json()["detail"])

# 默认值：不传 fmt 时走 default="txt"
r6 = client.get("/transcribe/demo123")
print("默认值 fmt:", r6.json()["format"])
```

要点：

- `response_model=TranscribeResponse` 同时做两件事：运行时过滤返回值（只保留模型字段）、在 OpenAPI 中生成可引用的 schema（见 7.7）。
- `Query(default="txt", description=...)` 让 `fmt` 成为可选查询参数，默认值 `txt`；描述会出现在 `/docs` 文档中。
- 400 与 404 由 `HTTPException` 显式抛出，语义分别为「参数不合法」与「资源不存在」，与自动的 422 区分。

### 7.5 状态码的语义与客户端行为

| 状态码 | 含义 | 客户端应如何处理 |
|---|---|---|
| 200 | 成功，响应体为业务数据 | 解析 `response.json()` |
| 400 | 业务参数错误（如 `fmt=pdf`） | 提示用户修正输入，不重试 |
| 404 | 资源不存在（如 `task_id` 错） | 提示「任务不存在」，可引导重新上传 |
| 422 | 校验失败（FastAPI 自动，如缺必填字段） | 展示 `detail` 中的字段级错误 |

把不同错误映射到不同状态码，是为了让客户端能用 `if resp.status_code == 404` 分支处理，而非解析字符串。

### 7.6 真实项目的路由分层与 `get_task_or_404`

MeetingToText 的后端并非把所有路由写在一个文件，而是按资源拆分：`backend/app/routers/transcribe.py`（转写流程）、`backend/app/routers/upload.py`（上传与任务列表）、`backend/app/routers/deps.py`（共享依赖）。只读参考其设计（以 HEAD 为准）：

- `transcribe.py` 定义 `APIRouter(prefix="/api", tags=["transcribe"])`，路由形如 `POST /api/transcribe/{task_id}`、`GET /api/transcript/{task_id}`；早期各路由各自写 `if task is None: raise HTTPException(404)`，后收敛为复用 `deps.ensure_task_or_404`。
- `upload.py` 定义 `APIRouter(prefix="/api", tags=["upload"])`，`POST /api/upload` 负责文件校验（扩展名、魔数、大小），`GET /api/tasks` 列任务。
- `deps.py` 是全仓库唯一抛出 `404 "Task not found"` 的位置：

  ```python
  def ensure_task_or_404(task: TaskInfo | None) -> TaskInfo:
      if task is None:
          raise HTTPException(status_code=404, detail="Task not found")
      return task

  def get_task_or_404(task_id: str = Path(..., description="任务 ID")) -> TaskInfo:
      return ensure_task_or_404(get_task(task_id))

  TaskDep = Annotated[TaskInfo, Depends(get_task_or_404)]
  ```

  路由处理器只需声明 `task: TaskDep`，即可「注入即 404」——不存在时框架在进入处理器前就返回 404，处理器拿到的 `task` 必为 `TaskInfo`，无需再判空。`transcribe.py` 因测试补丁需晚绑定，包了一层 `_task_or_404` 再调 `ensure_task_or_404`，语义相同。

这种「一处定义 404 文案与状态码，多处复用」的收敛，避免了复制粘贴导致的文案不一致与遗漏检查（漏判空会把 `None` 当任务用，导致 500）。

### 7.7 OpenAPI 自动文档：`/docs` 与 `response_model`

FastAPI 在启动时扫描所有路由，生成符合 OpenAPI 规范的 JSON（`/openapi.json`），并据此渲染交互式文档 `/docs`（Swagger UI）与 `/redoc`。`response_model` 的作用在 `/openapi.json` 中最直观：

```{code-cell} ipython3
# 观察有 response_model 时的 OpenAPI 片段
openapi = client.get("/openapi.json").json()
op = openapi["paths"]["/transcribe/{task_id}"]["get"]
print("responses:", list(op["responses"].keys()))
# 200 的 schema 应引用 TranscribeResponse
schema_ref = op["responses"]["200"]["content"]["application/json"]["schema"]
print("200 schema ref:", schema_ref)
# 参数描述是否来自 Query(description=...)
params = op["parameters"]
for p in params:
    if p["name"] == "fmt":
        print("fmt param:", p["description"], "required:", p["required"])

# 对比：去掉 response_model 的路由，其 schema 退化为通用 object
from fastapi import FastAPI
from fastapi.testclient import TestClient as TC2

app_naked = FastAPI()

@app_naked.get("/naked/{task_id}")
def naked(task_id: str, fmt: str = "txt"):
    return {"task_id": task_id, "fmt": fmt}

c2 = TC2(app_naked)
naked_schema = c2.get("/openapi.json").json()["paths"]["/naked/{task_id}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
print("无 response_model 的 schema:", naked_schema)
```

你会看到：有 `response_model` 时，`200` 的 `schema` 为 `{"$ref": "#/components/schemas/TranscribeResponse"}`，且 `components/schemas/TranscribeResponse` 中列出四个字段的类型与约束；无 `response_model` 时，`schema` 退化为 `{"type": "object"}` 或无字段描述，前端无法据此生成类型。对业务而言，前者是「契约」，后者只是「黑盒」。

浏览器中访问 `http://{host}:{port}/docs` 即可交互式试调：填 `task_id` 与 `fmt`，点 Execute，直接看到请求与响应。

### 改动并预测

以下实验均可在本章 `{code-cell}` 或本地 `pytest` 中复现。按「改什么 → 预测 → 解释」三段式书写。

#### 改动并预测 实验 1：去掉 `response_model` → 预测 OpenAPI schema 的变化

- **改什么**：把 `@app.get("/transcribe/{task_id}", response_model=TranscribeResponse)` 改为 `@app.get("/transcribe/{task_id}")`（删掉 `response_model` 参数），重启（或重建 `TestClient`）后再次 `GET /openapi.json`，观察 `paths./transcribe/{task_id}.get.responses.200.content.application/json.schema`。
- **预测**：原先的 `{"$ref": "#/components/schemas/TranscribeResponse"}` 会变为 `{"type": "object"}` 或含 `additionalProperties` 的泛化描述，`components/schemas` 中不再出现 `TranscribeResponse`；`/docs` 页面中该接口的 Example Value 从结构化字段（`task_id`/`status`/`format`/`content`）退化为「空对象」或无字段说明。
- **解释**：`response_model` 是 FastAPI 生成 OpenAPI 的唯一依据；没有它，框架无法知道处理器返回的 `dict` 有哪些键、类型是什么，只能按「任意 JSON 对象」描述。文档即契约，去掉模型等于去掉契约，前端无法据此生成类型与校验。

#### 改动并预测 实验 2：去掉 `Query` 校验（改 `fmt: str = Query(...)` 为 `fmt: str = "txt"`）→ 预测能否传入空值与文档变化

- **改什么**：把 `fmt: str = Query(default="txt", description="导出格式：txt/srt/md")` 改为 `fmt: str = "txt"`（普通默认值，无 `Query`），然后分别 `GET /transcribe/demo123?fmt=`（空字符串）与 `GET /transcribe/demo123`（缺省），并查看 `/openapi.json` 中 `fmt` 参数的 `description`。
- **预测**：`?fmt=` 时，`fmt` 会以空字符串 `""` 进入处理器，原先 `if fmt not in ("txt","srt","md")` 仍会判 400，但若删掉该业务检查则空字符串会被当作合法值传给 `export`，后者抛 `ValueError` 导致 500；`/openapi.json` 中 `fmt` 的 `description` 消失，`required` 仍为 `false` 但文档不再提示可选值。
- **解释**：`Query` 不仅提供默认值，还把「参数元信息（描述、是否必填、约束）」注册到 OpenAPI；裸默认值虽能运行，但丢失了「文档即校验」的声明式信息。空字符串是「传了但无值」，与「未传走默认值」语义不同，`Query` 的声明让这一区别在文档与校验层可见。

#### 改动并预测 实验 3：把 404 改为 200+错误体 → 预测客户端行为

- **改什么**：把 `raise HTTPException(status_code=404, detail="Task not found")` 改为 `return {"error": "Task not found", "task_id": task_id}`（状态码 200，错误藏在体里），然后让 `TestClient` 分别检查 `resp.status_code` 与 `resp.json()`。
- **预测**：原先 `client.get("/transcribe/notfound?fmt=txt").status_code == 404` 的断言失败，变为 `200`；客户端若按 `if resp.status_code == 404` 分支处理「任务不存在」，该分支永远不进，错误被当成成功数据继续处理（如 `resp.json()["content"]` 报 `KeyError`）。
- **解释**：状态码是 HTTP 层的「元信号」，客户端（前端、脚本、网关）优先按状态码路由；把错误藏在 200 体里，等于让所有中间件与通用错误处理失效。REST 要求「用状态码表达结果类别」，体只承载细节。

#### 改动并预测 实验 4：把 `fmt` 的 400 改为 422（抛 `HTTPException(422)`）→ 预测与自动校验 422 的混淆

- **改什么**：把 `raise HTTPException(status_code=400, detail="不支持的导出格式...")` 改为 `raise HTTPException(status_code=422, detail="不支持的导出格式...")`，然后对比「缺必填字段」与「fmt 非法」两种 422 的响应体。
- **预测**：两者状态码同为 422，但自动校验的 422 体为 `{"detail": [{"loc": ["query", "fmt"], "msg": ..., "type": ...}]}`（结构化字段错误），手动抛的 422 体为 `{"detail": "不支持的导出格式..."}`（字符串）；客户端若按 `detail` 是否为列表来区分，切分逻辑会出错。
- **解释**：422 在 FastAPI 中保留给「校验层（validation）」的自动错误，400 保留给「业务层（business）」的拒绝；混用会让客户端无法区分「请求写错了」与「业务不接受」，违背「状态码即语义」的约定。保持 400/422 分层，客户端才能分别提示「请检查输入」与「请换个格式」。

## 习题

> 参考答案与测试在 `answers/chapter07/`，运行 `.venv/bin/pytest answers/chapter07/ -q` 验证。题目均为 hermetic 纯函数/进程内 TestClient，不依赖网络或外部服务。

1. **最小 ping 端点**：实现 `make_ping_app() -> FastAPI`，返回一个含 `GET /ping -> {"msg": "pong"}` 的应用。测试用 `TestClient` 断言 200。
2. **fmt 校验 400**：在 `GET /transcribe/{task_id}?fmt={fmt}` 中，对非法 `fmt` 返回 400，且 `detail` 包含「支持」或「可选」字样；合法 `txt/srt/md` 返回 200。
3. **404 语义**：对不存在的 `task_id` 返回 404，且 `detail` 为 `"Task not found"`（与 `deps.py` 的 `ensure_task_or_404` 文案一致）。
4. **导出格式切换**：对同一 `task_id` 分别 `?fmt=txt`/`srt`/`md`，断言三者 `content` 互不相同，且 `srt` 含 `-->`, `md` 含 `#`。
5. **response_model 契约**：`GET /openapi.json` 中 `GET /transcribe/{task_id}` 的 200 `schema` 必须为 `{"$ref": "#/components/schemas/TranscribeResponse"}`，且 `components/schemas/TranscribeResponse` 含 `task_id/status/format/content` 四字段。
6. *（附加）* **默认值**：`GET /transcribe/{task_id}` 不带 `fmt` 时等价于 `?fmt=txt`，返回 200 且 `format=="txt"`。

## 延伸挑战

1. 给 `/transcribe` 增加 `limit: int = Query(default=50, ge=1, le=100)` 分页参数，观察 `/docs` 中自动出现的数值约束与 `TestClient` 对 `?limit=0` 的 422 响应。
2. 将内存 `FAKE_DB` 替换为 `m2t.store.TaskStore` 的临时库（`tempfile.mkstemp` + `TaskStore`），实现「创建→查询→导出」的端到端链路，体会「存储层与 HTTP 层解耦」。
3. 为 `POST /transcribe` 设计请求体 `class CreateReq(BaseModel): filename: str; fmt: str`，对比「查询参数 vs 请求体」在语义与 OpenAPI 呈现上的差异。
4. （预告）实时转写进度推送（SSE/WS）将放在后续章节的延伸挑战中实现，本章聚焦「请求-响应」式 REST，不引入长连接。

