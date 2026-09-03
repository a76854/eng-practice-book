---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 前端在架构中的角色

> 学完本节，你能回答：前端在“三层架构”中守什么边界？后端模板渲染与前后端分离的本质差异是什么？URL 与职责如何在这两种形态下划分？MeetingToText 为何更适合前后端分离？

## 为什么要先厘清“谁来渲染 HTML”

对后端开发者而言，前端的第一个困惑往往不是语法，而是“HTML 到底在哪里拼出来”。答案决定了整条链路的职责与协作方式：

- **如果 HTML 在后端拼**：浏览器每次访问 URL，服务端用模板把数据填入 HTML 并一次性返回，浏览器直接展示。前端是“模板 + 少量脚本”，后端是“路由 + 渲染”。
- **如果 HTML 在前端拼**：后端只返回 JSON 数据，前端在浏览器中用 JavaScript 把数据渲染为 DOM。前端是“应用”，后端是“API”。

两种形态都能交付 MeetingToText 的“任务列表页”，但“谁对页面负责”“URL 归谁管”“数据在哪里转换”的答案完全不同。先把这条边界讲清，后续的接口设计与联调才有共同语言。

## 两种形态的对比

### 后端模板渲染（Server-Rendered Template）

典型技术：Django Template / Jinja2 + Flask / FastAPI + Jinja2。请求流程：

```
浏览器 GET /tasks
  → 后端路由查库（TaskStore.list_tasks）
  → 后端用模板把 tasks 填入 HTML
  → 返回完整 HTML，浏览器直接呈现
```

优点：首屏直出、SEO 友好、前端复杂度低；适合内容型页面。代价：每次交互都可能整页刷新，前后端耦合在同一代码仓与模板中，难以独立部署与演进。

类比：如同“中央厨房做好整桌菜再上桌”——后端一次把菜与摆盘都完成，前端只负责端盘子。

### 前后端分离（Decoupled SPA + API）

典型技术：Vue / React 前端应用 + FastAPI / Express 后端 API。请求流程：

```
浏览器加载 index.html + app.js（静态资源）
  → 前端 JS 调用 GET /api/tasks（JSON）
  → 后端返回 [{id, filename, status}]
  → 前端把 JSON 渲染为 <ul><li>…</li></ul>
```

优点：前后端可独立开发与部署，交互流畅（局部更新，无需整页刷新），接口可同时服务 Web / App / 小程序。代价：首屏需额外一次 API 调用，SEO 需额外处理（SSR/预渲染），需要明确的接口契约。

类比：如同“后厨只出菜品（JSON），前厅按客人需求摆盘（View）”——后厨与前厅通过菜单（API 契约）协作，摆盘可在不改后厨的情况下独立调整。

> **选型启示**：没有银弹。内容型、SEO 强依赖的官网适合模板直出；交互密集、需多端复用接口的 MeetingToText 更适合前后端分离——让后端聚焦“任务与转写”的业务与存储，让前端聚焦“列表、搜索、播放与纪要”的交互与状态。

### URL 与职责划分

- **后端模板**：URL 既是“页面地址”又是“数据查询”。`GET /tasks` 返回 HTML，`GET /tasks/123` 返回详情页 HTML；接口与页面混在同一路由表。
- **前后端分离**：URL 分两类——**页面路由**归前端（如 `/tasks`、`/tasks/123` 由前端路由控制），**数据接口**归后端（如 `GET /api/tasks`、`GET /api/tasks/{id}` 返回 JSON）。二者通过统一前缀（如 `/api`）区分，避免歧义。

这种划分让协作更清晰：后端在 OpenAPI 中定义“输入/输出形状与状态码”，前端据此做“加载/空态/错误”三态渲染；任何一方改动都先回到契约，而非直接改对方代码。

## 后端模板 vs 前后端分离的代码对照

后端模板（Jinja2 风格，仅示意，不执行）：

```javascript
// 示意：后端模板 tasks.html（Jinja2，后端渲染示意）
// 后端路由返回已填好数据的 HTML，浏览器直接展示
// 路由：GET /tasks → render_template("tasks.html", tasks=tasks)
<ul>
  {% for t in tasks %}
    <li>{{ t.filename }} — {{ t.status }}</li>
  {% endfor %}
</ul>
```

前后端分离（Vue 风格，仅示意，不执行）：

```javascript
// 示意：前端 App.vue（节选，前后端分离示意）
// 前端加载后通过 fetch 获取 JSON，再用 v-for 渲染
// fetch('/mock.json') → { tasks: [...] } → v-for 渲染
const tasks = ref([])
async function load() {
  const res = await fetch('/api/tasks')
  const data = await res.json()
  tasks.value = data.tasks
}
// 模板：<li v-for="t in tasks" :key="t.id">{{ t.filename }} — {{ t.status }}</li>
```

```bash
# 两形态的产物对照（示意，非执行）
# 后端模板：curl 返回的是 HTML
curl http://localhost:8000/tasks | head
# 前后端分离：curl 返回的是 JSON，前端另行渲染
curl http://localhost:8000/api/tasks | head
```

## 可运行示例：用 Python 数据模型对照两种形态的职责与 URL

示例（用 dataclass 模拟两种形态：后端模板在服务端拼接 HTML，前后端分离在服务端返回 JSON、客户端拼接，本地可复现，无网络）：

```{code-cell} ipython3
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlencode
import json

@dataclass
class Task:
    id: str
    filename: str
    status: str  # pending | processing | done

tasks = [
    Task("1", "meeting.wav", "done"),
    Task("2", "interview.mp3", "processing"),
    Task("3", "demo.wav", "pending"),
]

BASE = "http://localhost:8000"

def api_url(path: str, **query) -> str:
    """前后端分离：后端接口 URL，统一 /api 前缀，返回 JSON"""
    base = urljoin(BASE, path)
    if query:
        return base + "?" + urlencode(query)
    return base

def page_url(path: str) -> str:
    """后端模板：页面 URL，直接对应 HTML"""
    return urljoin(BASE, path)

# 1) 后端模板：服务端直接生成 HTML（职责：后端拼 HTML）
def render_html_template(items: list[Task]) -> str:
    lis = "\n".join(f'  <li>{t.filename} — {t.status}</li>' for t in items)
    return f"<ul>\n{lis}\n</ul>"

# 2) 前后端分离：服务端返回 JSON，客户端负责渲染（职责：后端给数据）
def api_response(items: list[Task]) -> str:
    payload = {"tasks": [asdict(t) for t in items]}
    return json.dumps(payload, ensure_ascii=False, indent=2)

def client_render(json_text: str) -> str:
    """模拟前端把 JSON 渲染为 HTML（对应 Vue 的 v-for）"""
    data = json.loads(json_text)
    lis = "\n".join(f'  <li>{t["filename"]} — {t["status"]}</li>' for t in data["tasks"])
    return f"<ul>\n{lis}\n</ul>"

# --- URL 职责对照 ---
print("后端模板 URL（页面即数据）:", page_url("/tasks"))
print("前后端分离 URL（页面）:", page_url("/tasks"))
print("前后端分离 URL（接口）:", api_url("/api/tasks"))
print("带筛选的接口 URL:", api_url("/api/tasks", status="done", keyword="meeting"))
print()

# --- 产物对照 ---
html_direct = render_html_template(tasks)
json_payload = api_response(tasks)
html_via_json = client_render(json_payload)

print("后端模板产物（HTML）：")
print(html_direct)
print()
print("前后端分离产物（JSON）：")
print(json_payload)
print()
print("前端由 JSON 渲染的 HTML：")
print(html_via_json)
print()

# 核心校验：两种形态最终呈现一致，但职责与 URL 已分离
assert html_direct == html_via_json
assert "/api/tasks" in api_url("/api/tasks")
assert "meeting.wav" in html_direct
print("职责对照通过：模板直出与 JSON 渲染在展示上等价，差异在‘谁来拼 HTML’与 URL 分层")
# 预期输出:
# 后端模板 URL（页面即数据）: http://localhost:8000/tasks
# 前后端分离 URL（页面）: http://localhost:8000/tasks
# 前后端分离 URL（接口）: http://localhost:8000/api/tasks
# 带筛选的接口 URL: http://localhost:8000/api/tasks?status=done&keyword=meeting
# 后端模板产物（HTML）：
# <ul>
#   <li>meeting.wav — done</li>
#   ...
# </ul>
# 前后端分离产物（JSON）：
# {
#   "tasks": [...]
# }
# 前端由 JSON 渲染的 HTML：
# <ul>
#   <li>meeting.wav — done</li>
#   ...
# </ul>
# 职责对照通过：...
```

> **与后续章节的衔接**：本节的“接口契约”将在 [第4章 HTTP 与 RESTful](../../backend_development/http_restful/index.md) 的 OpenAPI 与 [第8章 路由与状态](../../frontend_collaboration/vue3_core/index.md) 的前端路由中进一步展开；MeetingToText 的任务列表页即采用“前端路由 + `/api/tasks` 接口”的分离形态，前端仅负责把 JSON 渲染为视图。

```bash
# 本地验证 URL 拼接与 JSON 产物的确定性
.venv/bin/python -c "from urllib.parse import urljoin; print(urljoin('http://localhost:8000','/api/tasks'))"
```
