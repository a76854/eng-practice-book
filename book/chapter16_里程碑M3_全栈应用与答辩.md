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

# 第16章 里程碑 M3：全栈应用与答辩复盘

> 从 API 到可用产品——本章把上传/转写/列表/纪要/导出串成一条最小全栈链路，完成可本地运行、可被 `TestClient` 冒烟的会议转写应用，并以复盘论文完成答辩。本里程碑仍全 hermetic（不实现 ASR 本体，走 m2t mock/fake），并与 `review_template.md` 的论文模板对齐。

## 学习目标

完成本里程碑后，你将能够：

1. 能描述 `POST /transcribe → GET /status → GET /tasks → POST /generate → GET /export → GET /` 的端到端时序与状态机，并用 `TestClient` 冒烟整条链路。
2. 能复用 `m2t.store.TaskStore` + `m2t.asr.transcribe(model=fake)` + `FakeLLM.generate(...)` + `m2t.export.export(task, fmt)` + `ThreadPoolExecutor(max_workers=1)` 的全栈拼装，并解释 `GET /` 内联 HTML 以 `fetch("/tasks")` 驱动列表的设计。
3. 能按 `milestones/m3_fullapp/README.md` 的提交结构组织 `student_solution/app.py`、`tests/`、`reference_solution/` 与 `review_template.md`，并用 `milestones/grader.py:run_grader` 自检。
4. 能按 [`milestones/m3_fullapp/review_template.md`](../milestones/m3_fullapp/review_template.md) 的复盘模板撰写 800–1500 字论文，覆盖项目回顾、选型权衡、坑与解法、测试证据与下一步。
5. 能在答辩中 5 分钟演示全链路并回答 hermetic、并发与安全权衡的提问。

## 先修要求

- 已通过 M1（CLI）与 M2（Web API），掌握 FastAPI、`m2t.store`/`m2t.asr`/`m2t.llm`/`m2t.export`、单工人 Future 与最小前端。
- 会执行 `.venv/bin/pytest milestones/m3_fullapp/tests -q` 与 `jupyter-book build --execute`。
- 已阅读 `milestones/m3_fullapp/README.md` 与 `review_template.md`，对 `MeetingToText/backend/app/routers/*` 与 `backend/app/services/{pipeline,store,llm}` 仅作只读参考（不复制）。

## 1. 里程碑目标

M3 的交付物是一条**最小全栈链路**：上传（mock）→转写（`pending→done`）→列表→生成纪要（mock LLM）→导出 `txt/srt/md`，并以 `GET /` 返回内联 HTML 列表页（`fetch("/tasks")` 驱动，无需完整 Vue 重搭）。后端复用 `m2t` 子包与单工人 Future 的并发模型，前端为可选但计分友好的单文件 HTML。**不实现 ASR 本体，走 m2t mock（fake 模型 / mock LLM），全 hermetic**——不安装 `funasr/torch/真实 LLM`，不访问网络/真实模型；`FakeModel.generate` 经 `m2t.asr.transcribe(model=fake)` 归一，`FakeLLM.generate` 返回固定纪要，不触 `openai`，满足 `grep -c "不实现 ASR 本体\|mock\|fake"` 门控。

权威定义见 [`milestones/m3_fullapp/README.md`](../milestones/m3_fullapp/README.md) 与 [`review_template.md`](../milestones/m3_fullapp/review_template.md)，本文为摘要与教学导读。

## 2. 任务说明（摘要）

### `POST /transcribe`

- 请求体 `{ "audio_path": "path/to/audio.wav" }` 必填非空；`mock`/`mock:*` 跳过文件存在性校验直接走 fake；缺参/空串/非 JSON→`400`；成功 `200` 返回 `{task_id, status:"pending"}`，后台 `pending→processing→done|error`，与 `pipeline_executor = ThreadPoolExecutor(max_workers=1)` 对齐。

### `GET /status/{task_id}`

- 响应 `200`：`{task_id,status,filename,error}`；不存在→`404 Task not found`（`ensure_task_or_404` 唯一出口）。

### `GET /tasks`

- 查询参数 `limit` 可选默认 50；响应 `200` 为 `{tasks:[{task_id,filename,status},...]}` 或数组二选一（测试兼容二者），按 `created_at DESC`；由 `store.list_tasks(limit)` 驱动，`GET /` 的内联 HTML 以此接口渲染列表。

### `POST /generate/{task_id}`

- 请求体可选 `{template:"default"}`；语义：不存在→`404`；未完成→`400 任务未完成，无法生成纪要`；已完成则以 `full_text/segments` 构造 prompt 调用**确定性 fake LLM**（`FakeLLM.generate(...)` 返回含 `会议纪要/待办` 的固定字符串），写入内存 `minutes` 缓存并幂等透出；成功 `200` 返回 `{task_id, minutes}`。

### `GET /export/{task_id}?format=txt|srt|md`

- `format` 必填枚举；缺失/非法→`400 不支持的格式`；不存在→`404`；未完成→`400 任务未完成`；已完成则 `text/plain` 返回 `m2t.export.export(task, format)` 的对应渲染（`srt` 含 ` --> `、`md` 含 `# 会议转录`，若已生成纪要则 `md` 末尾含 `# 会议纪要` 段）。

### `GET /`

- 返回 `200 text/html` 的单文件内联 HTML，含 `MeetingToText/会议转写/任务列表` 三者至少其一，且含 `fetch("/tasks")` 或 `fetch('/tasks')` 字样（评测据此断言前端确由该接口驱动列表，不执行浏览器 JS）。

### 路由分层与状态机

路由薄、服务厚；统一 `404` 出口；状态机 `pending→processing→done|error`；`400/404` 边界与 MeetingToText 对齐。

## 3. 提交结构

```
milestones/m3_fullapp/
  README.md                # 任务说明（只读，含 mock 声明）
  review_template.md       # 答辩复盘论文模板（独立文件，满足模板存在门控）
  reference_solution/
    app.py                 # 教师参考解（FastAPI + 单工人 + fake 模型 + fake LLM + m2t.store + 内联 HTML）
    __init__.py
  student_solution/
    app.py                 # 学生提交（需暴露 app: FastAPI）
  tests/
    conftest.py
    test_fullapp.py        # 黑盒 TestClient（唯一判分依据，≥8 用例，含整链冒烟）
  verify_reverse.sh
```

同接口 `app: FastAPI` + 可选 `create_app(db_path)` / `reset_state()`；内部必须 `TaskStore`（WAL + busy_timeout）、`FakeModel`/`FakeLLM`、`m2t.export.export`、单工人 Future、`GET /` 内联 HTML。学生另需在 `student_solution/README.md` 中按 README 第 4 节撰写项目简介、架构图、接口清单、本地运行与 hermetic 声明。

## 4. 复盘论文模板指引

独立模板见 [`milestones/m3_fullapp/review_template.md`](../milestones/m3_fullapp/review_template.md)，亦在本章与该 README 第 5 节摘录要点。学生需提交 800–1500 字 Markdown 复盘论文，结构如下（与模板五段对应）：

- **摘要（3–5 行）**：一句话链路 + 后端 FastAPI + 单工人 + SQLite WAL + `m2t`（fake ASR/fake LLM/export）+ 前端内联 HTML + 全 hermetic 与 TestClient 冒烟。
- **1. 项目回顾**：链路时序与状态机、分工（M1→M2→M3 增量）、演示方式（`GET /` 截图 + `POST /transcribe`/`POST /generate`/`GET /export` 关键日志）。
- **2. 技术选型与权衡**：为何选 FastAPI + SQLite + 单工人 + mock；若接入真实 ASR（FunASR SenseVoice + CAM++）/ 真实 LLM（OpenAI 兼容）会如何改（懒导入、超时/重试、脱敏 `map_llm_error`）；串行 vs 并行、SQLite vs Postgres、内联 HTML vs 完整 Vue 各 1 条利弊。
- **3. 遇到的坑与解法（≥1 例，现象→根因→解法→验证）**：如 `pending→processing` 窗口不可观测、`:memory:` 跨连接不可见、`segments` 与 `minutes` 的内存缓存分工等，附 1 段关键代码或 pytest 输出。
- **4. 测试与质量**：如何用 `TestClient` 串起整链（含轮询 `done`），一次“先写失败测试再改代码”的 TDD 例子，`assert "funasr" not in sys.modules` 的 hermetic 证明。
- **5. 下一步（2 项，做什么→为什么→如何验证）**：如实时录音 WebSocket + SSE 推流、完整 Vue 列表页与 `VITE_API_BASE_URL` 打通、容器化与 CI 冒烟等延伸挑战。

末尾含 **AI 辅助声明**（工具名 + 用途，遵循 `book/ai_policy.md`）与 **引用**（`backend/app/routers/*`、`m2t` 等，只作引用不搬运）。评分关注链路完整性、hermetic 自洽与对 trade-off 的诚实表述。

## 5. 评测（黑盒端到端冒烟 + grader 约定）

唯一判分引擎为 `pytest`，由 [`milestones/grader.py`](../milestones/grader.py) 封装：

```bash
python -m milestones.grader milestones/m3_fullapp
python -m milestones.grader milestones/m3_fullapp --solution reference_solution
.venv/bin/pytest milestones/m3_fullapp/tests -q
```

测试 ≥8 用例（实际 15）：缺 `audio_path`→400、未知 id 的 status/export/generate→404、提交后轮询 `pending→done`、`GET /tasks` 包含已提交、`POST /generate` 返回 `minutes` 含 `会议纪要/待办`、导出 `txt/srt/md` 与 `md` 含纪要、非法 `format=pdf`→400、未完成导出/生成→400、`GET /` 含 `MeetingToText` 且含 `fetch("/tasks")`、以及 `funasr/torch` 未加载。含一条完整链路断言 `transcribe→tasks→generate→export(txt/md)`。`run_grader` 将 `solution_dir` 注入 `PYTHONPATH`，`conftest.py` 保证直接 `pytest` 可回退。

### 双反向验证

`milestones/m3_fullapp/verify_reverse.sh` 三分支：(a) 好解→PASS (b) buggy（导出错/状态不流转/纪要空）→FAIL (c) 复用教师 tests× buggy →FAIL，产物入 `evidence/task-21-m3.txt`。

## 6. 答辩复盘提示

- 演示脚本：`POST /transcribe {"audio_path":"mock"}`→轮询 `GET /status` 至 `done`→`GET /tasks`→`POST /generate/{id}`→`GET /export?format=md`（含纪要）→打开 `GET /` 列表页，5 分钟内走完全链路。
- 必答问题准备：为何 `GET /` 选内联 HTML 而非完整 Vue？`FakeLLM` 如何保证不触 `openai` 且幂等？`from m2t.store import TaskStore` 的 WAL 如何支撑并发读？
- 论文证据：贴 1 张 `GET /` 截图 + 1 段 `pytest -q` 全绿输出 + 1 次 TDD 失败→修复的 diff，满足“每段 1–2 个证据”的模板要求。

## 自测实验（改动并预测）

#### 实验 1：把 `GET /` 的 `fetch("/tasks")` 改为 `fetch("/api/tasks")` → 预测列表页空

- **改什么**：将内联 HTML 中的 `fetch("/tasks")` 字符串改为 `/api/tasks`。
- **预测**：`test_index_html_contains_tasks_fetch` 因断言 `fetch("/tasks")` 而失败，即使后端仍有 `/tasks`，前端显示空列表。
- **解释**：评测以字符串存在性证明前端确由该接口驱动，路径必须对齐契约。

#### 实验 2：让 `POST /generate` 不做 `status != done` 校验 → 预测未完成生成通过

- **改什么**：注释掉 `if status != "done": raise 400` 一行。
- **预测**：`test_export_and_generate_before_done_returns_400` 中对未完成任务的 `POST /generate` 预期 `400 任务未完成`，实际 `200` 且 `minutes` 为空或异常，测试失败。
- **解释**：状态机保证纪要仅对已完成任务生成，绕过校验破坏链路语义。

#### 实验 3：在 `app.py` 顶层 `import openai` → 预测 hermetic 语义虽未显式断言但集成风险

- **改什么**：加 `import openai`。
- **预测**：`test_no_real_asr_import_at_runtime` 仍 PASS（仅查 `funasr/torch`），但后续 `POST /generate` 需真实 Key 时测试在离线环境挂起或鉴权失败，暴露隐式依赖。
- **解释**：全 hermetic 要求 fake LLM 不触 `openai`，顶层导入即引入外部依赖风险。

```{code-cell} ipython3
# M3 自检：全栈链路的 hermetic 冒烟（不触真实 ASR/LLM）
from m2t.export import export
task = {
    "filename": "mock.wav",
    "segments": [
        {"speaker": "说话人1", "text": "大家好，我们开始开会。", "start": 0.0, "end": 1.2},
        {"speaker": "说话人2", "text": "好的，我先汇报一下进度。", "start": 1.5, "end": 3.0},
    ],
    "full_text": "大家好，我们开始开会。\n好的，我先汇报一下进度。",
    "minutes": "# 会议纪要\n\n## 待办\n- 下一章完成原型",
}
md = export(task, "md")
assert "# 会议转录" in md and "会议纪要" in md and "待办" in md
print("M3 hermetic 冒烟通过 — transcribe→generate→export(md 含纪要) 全链就绪，GET / 以 fetch 驱动列表")
```

## 习题

1. 为 `GET /tasks` 补一个 `limit` 边界测试：`limit=0` 与 `limit=200` 时是否返回空或截断，且 `created_at` 仍倒序？
2. 写一个幂等性测试：对同一 `task_id` 连续两次 `POST /generate` 是否返回同一 `minutes` 且第二次不重算？
3. 用 `@pytest.mark.parametrize` 把 `GET /export` 的三格式断言参数化，并在 `md` 用例中额外断言已生成纪要后含 `会议纪要`。
4. 为 `GET /` 写一个负向测试：若后端把 `GET /` 改为重定向 `302` 到 `/tasks`，你的 `TestClient` 测试应如何以 `follow_redirects=False` 捕捉回归？
5. 复盘论文自检：你的论文是否在摘要中明确写出“不实现 ASR 本体，走 m2t mock / fake 模型”且在 `grep -c` 门控下可被命中？若缺失，按 10% 文档分会如何影响复盘评分？

## 延伸挑战

1. 实时录音 WebSocket + SSE 推流进度条，让 `GET /status` 的轮询改为推送。
2. 完整 Vue 列表页（`fetch(/tasks)`→任务卡片→导出/纪要按钮）与 `VITE_API_BASE_URL` 打通，保持 `GET /` 的 hermetic 回退。
3. 容器化（多阶段 Dockerfile + `compose` healthcheck）与 CI 冒烟（`pytest` + `linkcheck` + `ruff` 全绿）的一键演示。
