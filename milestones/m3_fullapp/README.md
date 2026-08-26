# 里程碑 M3：全栈应用 + 答辩复盘（周 16）

> 对应章节：`week12 Vue3 前端` / `week13 ASR+LLM 集成` / `week14 打包部署` / `week15 健壮性与安全`  
> 前置能力：M1（CLI）/ M2（Web API）已通过；FastAPI、`m2t.store`/`m2t.asr`/`m2t.llm`/`m2t.export`、单工人 Future、最小前端  
> 复用 MeetingToText 只读参考：`backend/app/routers/*` + `backend/app/services/{pipeline,store,llm}` + `frontend/src/views/*`（灵感，不复制）

## 1. 任务说明

把前序单元（上传/转写/列表/生成纪要/导出）串成**一条最小全栈链路**，交付一个可本地运行、可被 `TestClient` 冒烟的会议转写应用。前端为「可选但计分友好」的**内联 HTML 列表页**（`GET /` 返回单文件 `text/html`，内联 `<template>` / 简易 JS `fetch` 即可，不必完整 Vue 重搭）；后端复用 `m2t` 子包与单工人 Future 的并发模型。

**不实现 ASR 本体，走 m2t mock（fake 模型 / mock LLM），全 hermetic**。教学与评测环境**不安装 `funasr` / `torch` / 真实 LLM**，不访问网络/真实模型；后端通过注入**确定性 fake 模型**（实现 `generate(input, ...)` 返回固定 `sentence_info` 形状）经 `m2t.asr.transcribe(model=fake)` 归一，再以 `m2t.export` 导出；纪要生成走**确定性 fake LLM**（实现 `generate(prompt, ...)` 返回固定纪要字符串，不触 `openai`）。禁止在测试时导入 `funasr` / `torch` / 发起真实 LLM 请求。本声明满足 `grep -c "不实现 ASR 本体\|mock\|fake" milestones/m3_fullapp/README.md` 门控。

> 延伸挑战（不计分）：实时录音 WebSocket、SSE 推流、完整 Vue 前端、容器部署；感兴趣可在复盘论文中作为「下一步」阐述。

### 接口契约（最小全栈）

#### `POST /transcribe`

提交转写任务（hermetic，复用 fake 模型）。

- **请求体（JSON）**：`{ "audio_path": "path/to/audio.wav" }`
  - `audio_path` 必填非空 `str`；值为 `mock` / `mock:*` 时跳过文件存在性校验，直接走 fake 转写，保证零文件依赖；否则若文件不存在 → `400` 中文报错。
  - 缺参 / 空串 / 非 JSON → `400`。
- **成功响应**（`200`）：`{ "task_id": "<uuid>", "status": "pending" }`
- **语义**：服务端生成 `task_id`（`uuid4 hex`），以 `pending` 写入 `m2t.store`，提交至**单工人 `ThreadPoolExecutor(max_workers=1)`**；后台推进 `pending → processing → done | error`，与 `MeetingToText/backend/app/services/pipeline.py: pipeline_executor = ThreadPoolExecutor(max_workers=1)` 对齐。

#### `GET /status/{task_id}`

查询任务状态。

- **响应**（`200`）：`{ "task_id": "<id>", "status": "pending|processing|done|error", "filename": "<name>", "error": "" }`
- 任务不存在 → `404`（`detail: "Task not found"`，与 `deps.py:ensure_task_or_404` 一致）。

#### `GET /tasks`

列出任务（倒序，分页可选）。

- **查询参数**：`limit`（可选，默认 50）。
- **响应**（`200`）：`{ "tasks": [ { "task_id": "...", "filename": "...", "status": "..." }, ... ] }` 或数组形态二选一（测试兼容二者）；按 `created_at DESC`。
- 前端列表页由此接口驱动。

#### `POST /generate/{task_id}`

为已完成任务生成会议纪要（hermetic fake LLM，不触真实服务）。

- **请求体（JSON，可选）**：`{ "template": "default" }`（缺省即 `default`；非法值仍走默认，不抛错）。
- **语义**：
  - 任务不存在 → `404`。
  - 任务未完成（`status != done`）→ `400`（`任务未完成，无法生成纪要`）。
  - 已完成 → 以转写 `full_text` / `segments` 构造 prompt，调用**确定性 fake LLM**（`FakeLLM.generate(...)` 返回固定字符串），将结果写入内存 `minutes` 缓存并透出；再次调用幂等返回同一纪要。
- **成功响应**（`200`）：`{ "task_id": "<id>", "minutes": "<纪要文本>" }`（`minutes` 含固定关键词 `会议纪要` / `待办` 以便测试断言）。

#### `GET /export/{task_id}?format=txt|srt|md`

导出转写结果；若已生成纪要且 `format=md`，则 `md` 中自动拼接纪要段（复用 `m2t.export` 的 `minutes` 字段）。

- **查询参数**：`format` 必填，枚举 `txt|srt|md`；缺失或非法 → `400` 中文 `不支持的格式`。
- **语义**：
  - 任务不存在 → `404`。
  - 任务未完成 → `400`（`任务未完成`）。
  - 已完成 → 返回 `text/plain; charset=utf-8`，正文为 `m2t.export.export(task, format)` 的结果：
    - `txt`：每段一行 `[说话人] 文本`
    - `srt`：`序号 / 时间戳 --> 时间戳 / [说话人] 文本` 块，含 ` --> `
    - `md`：`# 会议转录 — <filename>` 标题 + 段落；若已生成纪要则末尾含 `# 会议纪要` 段

#### `GET /`

最小可服务 HTML 页面（内联 template，hermetic，无需打包）。

- **响应**（`200`，`text/html`）：返回单文件 HTML，含标题 `MeetingToText` / `会议转写` / `任务列表` 三者至少其一，且含 `fetch("/tasks")` 或 `fetch('/tasks')` 字样（证明前端确由该接口驱动列表）。
- 评测仅断言状态码与关键词存在，不执行浏览器 JS。

#### 路由分层与状态机

- **路由薄、服务厚**：路由仅做参数校验 / 状态流转，耗时工作下沉单工人池；
- **统一 404 出口**：`ensure_task_or_404` 是唯一 `404 "Task not found"` 抛出处；
- **状态机**：`pending → processing → done | error`，`400 / 404` 边界与 MeetingToText 对齐。

## 2. 提交结构

```
milestones/m3_fullapp/
  README.md                # 本文件（任务说明，对学生只读；含 mock 声明与门控关键词）
  review_template.md       # 答辩复盘论文模板（独立文件，满足「模板文件存在」门控）
  reference_solution/
    app.py                 # 教师参考解（FastAPI + 单工人 Future + fake 模型 + fake LLM + m2t.store + 内联 HTML）
    __init__.py
  student_solution/
    app.py                 # 学生提交（被测对象；grader 默认测此目录，需暴露 `app: FastAPI`）
  tests/
    conftest.py            # 保证直接 pytest 也能找到 app（grader 另行注入 PYTHONPATH）
    test_fullapp.py        # 黑盒 TestClient 测试（唯一判分依据，≥8 用例，hermetic）
  verify_reverse.sh        # 三分支双反向验证
```

`reference_solution/app.py` 与 `student_solution/app.py` **同接口**：

```python
from fastapi import FastAPI
app: FastAPI               # 必须暴露，tests 以 TestClient(app) 驱动

# 可选但建议：供测试隔离使用
def create_app(db_path: str | None = None) -> FastAPI: ...
def reset_state() -> None: ...
```

内部必须：

- `from m2t.store import TaskStore` 持久化任务状态（`TaskStore(db_path)`，`WAL + busy_timeout`）；
- 注入确定性 `FakeModel.generate(...) -> list[dict]` 经 `m2t.asr.transcribe(model=fake)` 归一；
- 注入确定性 `FakeLLM.generate(...) -> str`（或等价 fake，**不触 `openai`**）生成纪要；
- `m2t.export.export(task, fmt)` 导出；
- `ThreadPoolExecutor(max_workers=1)` 单工人 Future；
- `GET /` 返回内联 HTML。

## 3. 评测（黑盒端到端冒烟）

唯一判分引擎：`pytest`（`milestones/grader.py:run_grader` 封装）。测试**只断言可观测行为**：HTTP 状态码、`detail` 文案、任务状态流转、导出与纪要内容、HTML 关键词；不窥探内部变量；全 hermetic。

```bash
# 测学生提交（默认）
python -m milestones.grader milestones/m3_fullapp
# 自检参考解
python -m milestones.grader milestones/m3_fullapp --solution reference_solution
# 直接 pytest（hermetic）
.venv/bin/pytest milestones/m3_fullapp/tests -q
```

测试覆盖（≥8 用例，hermetic，无 funasr/torch/网络，含一条完整链路断言）：

1. 缺 `audio_path` 参数 → `400`
2. `GET /status/{不存在}` → `404`（`Task not found`）
3. `GET /export/{不存在}` → `404`
4. 提交后轮询 `pending → done` 状态流转（最终 `done`）
5. `GET /tasks` 列表包含已提交任务
6. `POST /generate/{task_id}`（mock LLM）→ 返回 `minutes` 含 `会议纪要` / `待办`
7. `GET /export?format=txt` → `200` 且含 `[说话人]` 的 `txt`
8. `GET /export?format=md` → 含 `# 会议转录`，且已生成纪要后含 `会议纪要`
9. `format=srt` → 含 ` --> ` 时间戳
10. 非法 `format=pdf` → `400` 中文 `不支持的格式`
11. 任务未完成时导出/生成 → `400` 中文 `任务未完成`
12. `GET /` → `200` 且含 `MeetingToText` / `任务列表` 且含 `fetch` 列表驱动

### fake 模型 / fake LLM

- **FakeModel**：`generate` 返回形状 1 `sentence_info` 带 `spk`，经 `m2t.asr.transcribe(model=fake)` 归一得到固定两段：
  - `说话人1: 大家好，我们开始开会。 [0,1200)ms`
  - `说话人2: 好的，我先汇报一下进度。 [1500,3000)ms`
- **FakeLLM**：`generate(prompt, ...)` 返回固定纪要字符串（含 `会议纪要` / `待办` / `下一步`），全程不导入 `openai` / 不访问网络；由 `POST /generate/{task_id}` 调用。

### 双反向验证

`verify_reverse.sh` 三分支（对齐 `milestones/grader_selfcheck.sh` 思想）：

- (a) 好解（`reference_solution`）→ `tests` PASS
- (b) 故意 buggy 实现（错误导出/状态不流转/纪要空）→ `tests` FAIL
- (c) 学生自带测试（此处复用教师 `tests`）× buggy → FAIL（证明测试非空心）

```bash
bash milestones/m3_fullapp/verify_reverse.sh   # 产物 capture 进 evidence/task-21-m3.txt
```

## 4. README 撰写要求（学生提交的 README.md 需包含）

学生在 `student_solution/README.md`（或仓库根 `README.md`）中需包含以下小节（中文，hermetic 说明）：

1. **项目简介**：一句话说明本全栈应用的定位与链路（上传→转写→列表→纪要→导出）。
2. **架构图（文字版即可）**：前端 `GET /` / `fetch(/tasks)` ↔ 后端 FastAPI（单工人 Future）↔ `m2t.store`（SQLite WAL）↔ `m2t.asr`（fake）/ `m2t.llm`（fake）↔ `m2t.export`。
3. **接口清单**：`POST /transcribe` / `GET /status/{id}` / `GET /tasks` / `POST /generate/{id}` / `GET /export/{id}?format=` / `GET /` 的方法、路径、参数、状态码。
4. **本地运行**：`pip install -r requirements.txt` + `uvicorn app:app --reload` 或 `python -m app` 的启动命令与访问 `http://localhost:8000/` 的说明。
5. **hermetic 声明**：明确写出「**不实现 ASR 本体，走 m2t mock / fake 模型**」，说明测试无需真实音频/模型/网络。

未包含上述小节或缺失 hermetic 声明的提交，视为文档不完整。

## 5. 复盘论文模板（答辩复盘）

独立模板见 [`review_template.md`](./review_template.md)，亦在本 README 末尾摘录要点。学生需提交一篇 800–1500 字复盘论文（Markdown），结构如下：

- **1. 项目回顾**：链路回顾（上传/转写/列表/纪要/导出）与分工
- **2. 技术选型与权衡**：为何选 FastAPI + SQLite + 单工人 Future + mock；若用真实 ASR/LLM 会如何改
- **3. 遇到的坑与解法**：并发（单工人串行）、状态机（pending→done）、hermetic（fake）、导出格式等至少 1 例
- **4. 测试与质量**：如何用 TestClient 冒烟整条链路；一次「先写失败测试再改代码」的例子
- **5. 下一步**：若再给一周，会做哪 2 项改进（可含实时录音 WS / SSE 推流 / 完整 Vue / 容器部署等延伸挑战）

评分关注：**链路完整性**、**hermetic 自洽**、**对 trade-off 的诚实表述**，而非功能堆砌。

---

### 复盘论文模板要点摘录（完整版见 review_template.md）

> 标题：M3 全栈应用答辩复盘 — <学号 姓名>
> 正文按第 5 节五段展开，每段配 1–2 个证据（截图/日志/测试输出）；末尾附「AI 辅助声明」与「引用」。

## 6. 实现提示

- 思路对齐 `MeetingToText/backend/app/routers/{transcribe,upload,generate}.py` 与 `deps.py` 的**路由分层 + `ensure_task_or_404` + 状态机**，但**不引入 SSE/WS**（延伸挑战）；
- `POST /transcribe` 校验：`audio_path` 必填非空；`mock*` 跳过文件检查，其余校验 `os.path.exists`；
- 后台：`store.create(task_id, filename, status="pending")` → `store.update(status="processing")` → `m2t.asr.transcribe` → `store.update(status="done", full_text=...)`，异常则 `status="error"`；
- `GET /tasks` 直接 `store.list_tasks(limit)` 并映射为 `{task_id, filename, status}`；
- `POST /generate` 需先 `store.get` 判 `404`，再 `status != done` 判 `400`，再调用 fake LLM 并缓存 `minutes`；
- 导出：先 `store.get` 判 `404`，再 `format` 判 `400`，再 `status != done` 判 `400`，最后构造 `m2t.export.export(task_dict, fmt)` 任务形态（`md` 需带 `minutes`）；
- `GET /` 返回内联 HTML（`HTMLResponse`），含 `fetch("/tasks")` 驱动列表；
- 保持 `import m2t` 可成功且永不触发 `funasr` / `torch` / `openai` 真实导入；
- 满足 `grep -c "不实现 ASR 本体\|mock\|fake" milestones/m3_fullapp/README.md` ≥1。

## 7. 常见问题

- **需要真实音频/模型/LLM Key 吗？** 不需要。`audio_path="mock"` + fake LLM 即可 hermetic 完成整条链路；`m2t.asr` / `m2t.llm` 默认走 fake。
- **如何本地自测？** `.venv/bin/pytest milestones/m3_fullapp/tests -q` 或 `python -m milestones.grader milestones/m3_fullapp --solution reference_solution`。
- **并发安全？** 单工人 + `TaskStore`（WAL + busy_timeout）+ `threading.Lock` 保护内存 `_results` / `_minutes`；`verify_reverse.sh` 的 buggy 夹具在 `/tmp` 隔离；测试以 `tmp sqlite` 或 `:memory:` 隔离状态。
- **前端必须用 Vue 吗？** 不必。本里程碑仅要求 `GET /` 返回「最小可服务 HTML」（内联 template 列表页）；完整 Vue 重搭为加分项，不计入必过用例。
