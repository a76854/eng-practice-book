# 里程碑 M2：可用 Web API（周 11）

> 对应章节：`week07 HTTP 与 REST` / `week08 数据持久化` / `week09 调试与性能` / `week10 并发与异步`  
> 前置能力：FastAPI 基础、`m2t.store` / `m2t.export` 基础、并发与状态机思维  
> 复用 MeetingToText 只读参考：`backend/app/routers/{transcribe.py,generate.py,upload.py}` + `deps.py`（路由分层 + `get_task_or_404` + 状态机）

## 1. 任务说明

把 M1 的 CLI 转写能力包装为一个**最小可用的 FastAPI 服务**：客户端提交任务 → 轮询状态 → 导出结果。服务在后端单工人线程池中复用 `m2t` 完成转写，状态经 `m2t.store` 持久化。

**不实现 ASR 本体，复用 `m2t`（mock / fake 模型）**。教学与评测环境**全程 hermetic**：不安装 `funasr` / `torch`，不访问网络/真实模型；后端通过注入**确定性 fake 模型**（实现 `generate(input, ...)` 返回固定 `sentence_info` 形状）经 `m2t.asr.transcribe(model=fake)` 归一，再以 `m2t.export` 导出。禁止在测试时导入 `funasr` / `torch`。本声明满足 `grep -c "不实现 ASR 本体\|mock\|fake"` 门控。

### 接口契约

#### `POST /transcribe`

提交一个转写任务（hermetic，复用 fake 模型，无需真实音频内容）。

- **请求体（JSON）**：

  ```json
  { "audio_path": "path/to/audio.wav" }
  ```

  - `audio_path`（必填，`str` 非空）：音频路径或 **mock 输入**。当值为 `mock` / `mock:*` 时跳过文件存在性校验，直接走 fake 转写，保证测试零文件依赖；否则若文件不存在，返回 `400`（中文报错）或在后台将任务置为 `error`。
  - 缺少 `audio_path` / 空字符串 / 非 JSON → `400`（`detail` 含中文或明确错误信息）。

- **成功响应**（`200`）：

  ```json
  { "task_id": "<uuid>", "status": "pending" }
  ```

- **语义**：服务端生成 `task_id`（`uuid4 hex`），以 `pending` 写入 `m2t.store`，提交至**单工人 `ThreadPoolExecutor(max_workers=1)`** 的 Future；后台将状态推进为 `processing → done | error`。单工人保证并发提交串行执行，与 `MeetingToText/backend/app/services/pipeline.py: pipeline_executor = ThreadPoolExecutor(max_workers=1)` 对齐。

#### `GET /status/{task_id}`

查询任务状态。

- **路径参数**：`task_id`（`str`）。
- **响应**（`200`）：

  ```json
  { "task_id": "<id>", "status": "pending|processing|done|error", "filename": "<name>", "error": "" }
  ```

  - `status` 流转：`pending → processing → done`（成功）或 `→ error`（失败）。提交后立即可见 `pending`，后台短暂延时后进入 `processing`，最后落 `done`。
  - 任务不存在 → `404`（`detail: "Task not found"`，与 `deps.py:ensure_task_or_404` 一致）。

#### `GET /export/{task_id}?format=txt|srt|md`

导出已完成任务的转写结果。

- **查询参数**：`format`（必填，枚举 `txt|srt|md`；缺失或非法值 → `400` 中文报错 `不支持的格式`）。
- **语义**：
  - 任务不存在 → `404`。
  - 任务未完成（`status != done`） → `400`（`任务未完成`）。
  - 任务已完成 → 返回纯文本 `content`（`text/plain; charset=utf-8`），正文为 `m2t.export.export(task, format)` 的结果：
    - `txt`：每段一行 `[说话人] 文本`，`\n` 连接
    - `srt`：`序号 / 时间戳 --> 时间戳 / [说话人] 文本` 块，块间空行，含 ` --> `
    - `md`：`# 会议转录 — <filename>` 标题 + 段落
  - 复用 `m2t.store` 露出持久化状态，`hermetic（fake 模型）`，不觸真實 ASR。

#### 路由分层与状态机

参考 `MeetingToText/backend/app/routers/deps.py` 的分层：

- **路由薄、服务厚**：路由仅做参数校验 / 状态流转，耗时工作下沉 `ThreadPoolExecutor`；
- **统一 404 出口**：`ensure_task_or_404` / `get_task_or_404` 是全服务唯一抛出 `404 "Task not found"` 的位置，语义与 MeetingToText 一致；
- **状态机**：`pending → processing → done | error`，`404 / 400` 边界与 MeetingToText `TaskStatus` 对齐。

## 2. 提交结构

```
milestones/m2_webapi/
  README.md                # 本文件（任务说明，对学生只读）
  reference_solution/
    app.py                 # 教师参考解（FastAPI app + 单工人 Future + fake 模型 + m2t.store）
    __init__.py
  student_solution/
    app.py                 # 学生提交（被测对象；grader 默认测此目录，需暴露 `app: FastAPI`）
  tests/
    conftest.py            # 保证直接 pytest 也能找到 app（grader 另行注入 PYTHONPATH）
    test_webapi.py         # 黑盒 TestClient 测试（唯一判分依据）
  verify_reverse.sh        # 三分支双反向验证
```

`reference_solution/app.py` 与 `student_solution/app.py` **同接口**：

```python
from fastapi import FastAPI
app: FastAPI               # 必须暴露，tests 以 TestClient(app) 驱动

# 可选但建议：供测试隔离使用的工厂/重置
def create_app(db_path: str | None = None) -> FastAPI: ...
def reset_state() -> None: ...
```

内部必须：

- `from m2t.store import TaskStore` 持久化任务状态（`TaskStore(db_path)`，`WAL + busy_timeout`）；
- 注入确定性 `FakeModel.generate(...) -> list[dict]` 经 `m2t.asr.transcribe(model=fake)` 归一；
- `m2t.export.export(task, fmt)` 导出；
- `ThreadPoolExecutor(max_workers=1)` 单工人 Future。

## 3. 评测（黑盒）

唯一判分引擎：`pytest`（`milestones/grader.py:run_grader` 封装）。测试**只断言可观测行为**：HTTP 状态码、`detail` 文案、任务状态流转、导出内容；不窥探内部变量；全 hermetic。

```bash
# 测学生提交（默认）
python -m milestones.grader milestones/m2_webapi
# 自检参考解
python -m milestones.grader milestones/m2_webapi --solution reference_solution
# 直接 pytest（hermetic）
.venv/bin/pytest milestones/m2_webapi/tests -q
```

测试覆盖（≥8 用例，hermetic，无 funasr/torch/网络）：

1. 缺 `audio_path` 参数 → `400`
2. 非法 JSON / 空 `audio_path` → `400`
3. `GET /status/{不存在}` → `404`（`Task not found`）
4. `GET /export/{不存在}` → `404`
5. 提交后轮询 `pending → done` 状态流转（最终 `done`，误差内 `processing` 可观测）
6. `GET /export?format=txt` → 含 `[说话人]` 的 `txt` 且状态码 `200`
7. `format=srt` → 含 ` --> ` 时间戳
8. `format=md` → 含 `# 会议转录`
9. 非法 `format=pdf` → `400` 中文 `不支持的格式`
10. 任务未完成时导出 → `400` 或未完成提示

### fake 模型

参考解注入**确定性 fake 模型**（`generate` 返回形状 1 `sentence_info` 带 `spk`），经 `m2t.asr.transcribe(model=fake)` 归一得到固定两段：

- `说话人1: 大家好，我们开始开会。 [0,1200)ms`
- `说话人2: 好的，我先汇报一下进度。 [1500,3000)ms`

再由 `m2t.export` 按 `fmt` 渲染。固定形状覆盖 `m2t.asr.normalize_result` 的三形状之至少一种。

### 双反向验证

`verify_reverse.sh` 三分支（对齐 `milestones/grader_selfcheck.sh` 思想）：

- (a) 好解（`reference_solution`）→ `tests` PASS
- (b) 故意 buggy 实现（错误导出/状态不流转）→ `tests` FAIL
- (c) 学生自带测试（此处复用教师 `tests`）× buggy → FAIL（证明测试非空心）

```bash
bash milestones/m2_webapi/verify_reverse.sh   # 产物 capture 进 evidence/task-16-m2.txt
```

## 4. 实现提示

- 思路对齐 `MeetingToText/backend/app/routers/{transcribe,upload}.py` 与 `deps.py` 的**路由分层 + `ensure_task_or_404` + 状态机**，但**不引入 SSE/WS**（延伸挑战）；
- `POST /transcribe` 校验：`audio_path` 必填非空；`mock*` 跳过文件检查，其余校验 `os.path.exists`；
- 后台：`store.create(task_id, filename, status="pending")` → `store.update(status="processing")` → `m2t.asr.transcribe` → `store.update(status="done", full_text=...)`，异常则 `status="error"`；
- 导出：先 `store.get(task_id)` 判 `404`，再 `format` 判 `400`，再 `status != done` 判 `400`，最后构造 `m2t.export.export(task_dict, fmt)` 任务形态；
- 保持 `import m2t` 可成功且永不触发 `funasr` 懒导入；
- 满足 `grep -c "不实现 ASR 本体\|mock\|fake" milestones/m2_webapi/README.md` ≥1。

## 5. 常见问题

- **需要真实音频/模型吗？** 不需要。`audio_path="mock"` 即可 hermetic 完成；`m2t.asr` 默认走 fake。
- **如何本地自测？** `.venv/bin/pytest milestones/m2_webapi/tests -q` 或 `python -m milestones.grader milestones/m2_webapi --solution reference_solution`。
- **并发安全？** 单工人 + `TaskStore`（WAL + busy_timeout）+ `threading.Lock` 保护 `_task_results`；`verify_reverse.sh` 的 buggy 夹具在 `/tmp` 隔离；测试以 `tmp sqlite` 或 `:memory:` 隔离状态。
