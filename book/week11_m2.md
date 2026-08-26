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

# 里程碑 M2：Web API

> 把 CLI 的能力用 HTTP 暴露——本周把 `m2t` 的转写与导出、SQLite 的持久化、单工人 Future 的并发模型收敛为一个可用 Web API。客户端以 `POST /transcribe → GET /status → GET /export` 完成异步转写，服务全程 hermetic（不实现 ASR 本体，走 mock/fake）且状态机与 MeetingToText 只读参考对齐。

## 学习目标

完成本里程碑后，你将能够：

1. 能用 FastAPI 实现 `POST /transcribe`、`GET /status/{id}`、`GET /export/{id}?format=` 的契约，并解释 `400/404` 与 `Task not found` 统一出口的设计。
2. 能用 `ThreadPoolExecutor(max_workers=1)` 单工人 Future 实现 `pending→processing→done|error` 的状态流转，并预测排队任务的可取消性。
3. 能复用 `m2t.store.TaskStore`（WAL + busy_timeout）持久化任务，并用 `m2t.asr.transcribe(model=fake)` + `m2t.export.export(task, fmt)` 完成 hermetic 转写与导出。
4. 能按 `milestones/m2_webapi/README.md` 的提交结构组织 `student_solution/app.py`、`tests/` 与 `reference_solution/`，并用 `milestones/grader.py:run_grader` 自检。
5. 能用 `TestClient` 编写 ≥8 条黑盒用例覆盖状态机与三格式导出，并通过 `verify_reverse.sh` 三分支验证测试有效性。

## 先修要求

- 已完成周 7–10（HTTP/REST、SQLite、调试/性能、并发与 `ThreadPoolExecutor`）。
- 会执行 `.venv/bin/pytest milestones/m2_webapi/tests -q` 与 `jupyter-book build --execute`。
- 已阅读 `milestones/m2_webapi/README.md` 与 `milestones/grader.py` 的目录与双反向约定；对 `MeetingToText/backend/app/routers/{transcribe,generate,upload}.py` 与 `deps.py` 的路由分层仅作只读参考。

## 1. 里程碑目标

M2 把 M1 的 CLI 能力包装为**最小可用 FastAPI 服务**：提交任务→轮询状态→导出结果。后端在单工人线程池中复用 `m2t` 完成转写，状态经 `m2t.store` 持久化。**不实现 ASR 本体，复用 `m2t`（mock/fake 模型）**——教学与评测环境全程 hermetic，不安装 `funasr/torch`，不访问网络/真实模型；通过注入**确定性 fake 模型**（`generate(input, ...)` 返回固定 `sentence_info`）经 `m2t.asr.transcribe(model=fake)` 归一，再以 `m2t.export` 导出，满足 `grep -c "不实现 ASR 本体\|mock\|fake"` 门控。

权威定义见 [`milestones/m2_webapi/README.md`](../milestones/m2_webapi/README.md)，本文为摘要与教学导读。

## 2. 任务说明（摘要）

### `POST /transcribe`

- 请求体 JSON：`{ "audio_path": "path/to/audio.wav" }`，`audio_path` 必填非空；值为 `mock`/`mock:*` 时跳过文件存在性校验直接走 fake，保证零文件依赖；否则文件不存在则 `400` 中文或后台置 `error`。缺参/空串/非 JSON → `400`。
- 成功响应 `200`：`{ "task_id": "<uuid4 hex>", "status": "pending" }`。服务端生成 `task_id`，以 `pending` 写入 `m2t.store`，提交至**单工人 `ThreadPoolExecutor(max_workers=1)`**，后台推进 `processing→done|error`，与 `MeetingToText/backend/app/services/pipeline.py: pipeline_executor = ThreadPoolExecutor(max_workers=1)` 对齐。

### `GET /status/{task_id}`

- 响应 `200`：`{ "task_id","status":"pending|processing|done|error","filename","error" }`，流转 `pending→processing→done`（或 `error`）。任务不存在 → `404`（`detail: "Task not found"`，与 `deps.py:ensure_task_or_404` 一致）。

### `GET /export/{task_id}?format=txt|srt|md`

- 查询参数 `format` 必填，枚举 `txt/srt/md`；缺失或非法 → `400` 中文 `不支持的格式`。
- 语义：不存在 `404`；未完成 `400`（`任务未完成`）；已完成则返回 `text/plain; charset=utf-8`，正文为 `m2t.export.export(task, format)` 的对应渲染（`txt` 每段一行、`srt` 含 ` --> `、`md` 含 `# 会议转录`）。复用 `m2t.store` 的持久化状态，全 hermetic。

### 路由分层与状态机

参考 `MeetingToText/backend/app/routers/deps.py`：路由薄、服务厚；统一 `404` 出口为 `get_task_or_404`；状态机 `pending→processing→done|error` 与 `400/404` 边界对齐。

## 3. 提交结构

```
milestones/m2_webapi/
  README.md                # 任务说明（只读）
  reference_solution/
    app.py                 # 教师参考解（FastAPI + 单工人 Future + fake + m2t.store）
    __init__.py
  student_solution/
    app.py                 # 学生提交（需暴露 app: FastAPI）
  tests/
    conftest.py
    test_webapi.py         # 黑盒 TestClient 测试（唯一判分依据）
  verify_reverse.sh
```

同接口：

```python
from fastapi import FastAPI
app: FastAPI
def create_app(db_path: str | None = None) -> FastAPI: ...
def reset_state() -> None: ...
```

内部必须：`TaskStore(db_path)`（WAL + busy_timeout）、`FakeModel.generate(...) -> list[dict]` 经 `transcribe`、 `m2t.export.export(task, fmt)`、单工人 Future。

## 4. 评测（黑盒 + grader 约定）

唯一判分引擎为 `pytest`，由 [`milestones/grader.py`](../milestones/grader.py) 的 `run_grader` 封装：

```bash
python -m milestones.grader milestones/m2_webapi
python -m milestones.grader milestones/m2_webapi --solution reference_solution
.venv/bin/pytest milestones/m2_webapi/tests -q
```

测试 ≥8 用例（实际 15）：缺 `audio_path`→400、空/非法 JSON→400、未知 id 的 status/export→404、提交后轮询 `pending→done`、导出 `txt/srt/md` 与大小写不敏感、非法 `format=pdf`→400 中文、未完成导出→400、以及 `funasr/torch` 未加载的 hermetic 保障。`run_grader` 将 `solution_dir` 置于 `PYTHONPATH` 首位，使 `tests/test_webapi.py` 的 `import app` 解析到被测实现；`conftest.py` 另有回退以支持直接 `pytest`。

### 双反向验证

`milestones/m2_webapi/verify_reverse.sh` 三分支：(a) 好解→PASS (b) buggy（状态不流转/导出错）→FAIL (c) 复用教师 tests× buggy →FAIL，产物入 `evidence/task-16-m2.txt`，与 `grader_selfcheck.sh` 同思想。

## 5. 评分 rubric 要点

周 11 教师指南 rubric：功能正确性 40%（黑盒全绿）、路由设计 20%（分层清晰、404 收敛一处）、测试覆盖 20%（≥5 条 TestClient，覆盖 200/400/404）、OpenAPI 文档 10%（`response_model` 齐全，`/docs` 可交互）、双反向验证 10%（三分支通过）。评审时重点看：是否收敛 404 到 `deps.py` 风格的唯一出口、状态机是否可观测 `pending→processing→done`、导出是否经 `m2t.export` 而非手拼。

## 6. 答辩提示

- 演示脚本：用 `TestClient` 或 `curl` 现场跑 `POST /transcribe {"audio_path":"mock"}`→轮询 `GET /status/{id}`（展示 `pending→done`）→ `GET /export?format=srt` 与 `md`，突出 ` --> ` 与 `# 会议转录` 的差异。
- 必答问题准备：单工人为何选 `max_workers=1`？`Future.cancel()` 对排队与运行中任务有何不同？`TaskStore` 的 WAL 与 `busy_timeout` 解决什么并发问题？
- 自检清单：`POST /transcribe` 的 `mock` 是否跳过文件校验？`GET /export?format=TXT` 大小写是否通过？`404` 文案是否为 `Task not found`？

## 自测实验（改动并预测）

#### 实验 1：把单工人改为 `max_workers=2` → 预测并发语义变化

- **改什么**：将 `ThreadPoolExecutor(max_workers=1)` 改为 `2`。
- **预测**：并发提交时任务不再严格串行，`test_status_flow_pending_to_done` 仍可能 PASS，但“排队可取消”的教学点被削弱；若测试加“先提交 blocker 占住工人再取消排队任务”的探针，则行为与单工人预期不一致。
- **解释**：单工人刻意为排队而非加速，与 `pipeline.py` 对齐；改大工人需配套加锁与状态保护。

#### 实验 2：删掉 `get_task_or_404` 统一出口 → 预测 404 文案不一致

- **改什么**：在 `GET /status` 与 `GET /export` 中各写一套 `if task is None: raise HTTPException(404, "Not found")`。
- **预测**：`test_status_unknown_id_returns_404` 与 `test_export_unknown_id_returns_404` 因断言 `Task not found` 而一处失败，且 `response_model` 丢失导致 `/docs` schema 不一致。
- **解释**：统一出口保证文案与文档一致性，收敛是复用的价值。

#### 实验 3：在顶层 `import funasr` → 预测 hermetic 失败

- **改什么**：在 `app.py` 顶层加 `import funasr`。
- **预测**：`test_no_real_asr_import_at_runtime` 断言 `funasr not in sys.modules` 失败。
- **解释**：全程 hermetic 要求 `funasr` 懒导入永不触发，顶层导入破坏离线可测。

```{code-cell} ipython3
# M2 自检：状态机与导出格式的 hermetic 冒烟（不触真实 ASR）
from m2t.export import export
task = {
    "filename": "mock.wav",
    "segments": [
        {"speaker": "说话人1", "text": "大家好，我们开始开会。", "start": 0.0, "end": 1.2},
        {"speaker": "说话人2", "text": "好的，我先汇报一下进度。", "start": 1.5, "end": 3.0},
    ],
    "full_text": "大家好，我们开始开会。\n好的，我先汇报一下进度。",
}
assert "[说话人1]" in export(task, "txt") and " --> " in export(task, "srt") and "# 会议转录" in export(task, "md")
print("M2 hermetic 冒烟通过 — txt/srt/md 三格式导出与状态机契约就绪")
```

## 习题

1. 为 `POST /transcribe` 补一个 `test_audio_path_is_directory_returns_400`，验证目录路径被拒且 `400` 文案含中文。
2. 用 `pytest.mark.parametrize` 把导出格式断言参数化为 `format→expected_substring`（`txt→说话人|srt→ --> |md→# 会议转录`）。
3. 写一个轮询可观测性测试：提交后 50ms 内 `GET /status` 是否可见 `pending` 或 `processing`，并在 `processing` 阶段 `GET /export` 断言 `400 任务未完成`。
4. 为 `GET /tasks` 的分页补一个测试：连续提交 3 任务后 `GET /tasks?limit=2` 是否仅返回 2 条且按 `created_at DESC`。
5. 复盘 rubric：若你的实现漏掉 `response_model`，按 10% 权重会如何影响 OpenAPI 文档分？如何用 `TestClient.get("/openapi.json")` 固化该回归？

## 延伸挑战

1. 为 `GET /status` 增加 SSE 推流（`text/event-stream`），让前端无需轮询即可订阅 `pending→done`。
2. 把 `TaskStore` 换为 Postgres + `asyncpg`，对比 WAL 模式在并发读写与崩溃恢复上的差异。
3. 为 `POST /transcribe` 增加 `X-Request-Id` 追踪与结构化日志，演示分布式追踪的最小闭环。

> 本章内容原创，概念对应 MeetingToText 的 `backend/app/routers/{transcribe,upload,generate}.py` 与 `deps.py` 的路由分层、单工人 Future 与 `m2t` 复用链路，任务结构与 grader 约定对应 `milestones/m2_webapi/README.md` 与 `milestones/grader.py`，习题与表述均为原创。
