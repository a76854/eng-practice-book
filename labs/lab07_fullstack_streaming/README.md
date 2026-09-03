# 实验七 前后端联调与流式响应集成

> 对应理论 [第9章 与外部世界的集成](../../book/advanced_engineering/external_integration/index.md) · 6 学时 · 任务说明与验收标准同 `book/lab_guide/fullstack_streaming/index.md`

## 实验目标

- 用 FastAPI 实现上传与 SSE 流式接口，理解 `text/event-stream` 与增量 `delta` 拼回全量的协作。
- 用 EventSource 在前端做流式渲染，体会首字时延从秒级降至百毫秒级的体感差异。
- 打通录音上传到实时转写到 AI 总结的链路，用 `m2t` 只读 mock 在本机复现，失败时保持脱敏与可观测。
- 按 OpenAPI 契约完成联调，能定位跨域、事件格式与增量拼接等常见问题。

## 任务步骤

### 步骤 1 阅读理论

通读第9章 9.1 至 9.3 节，关注超时重试脱敏、音频归一与流式 SSE，并浏览 `m2t/asr.py` 与 `m2t/llm.py` 的只读 mock 能力。

### 步骤 2 读懂骨架

进入 `starter/`，运行 `python main.py` 观察终端的 SSE wire 仿真，阅读 `main.py` 的接口与 `index.html` 的 EventSource 订阅。

### 步骤 3 后端流式接口

完善 `/api/health`、`/api/transcribe` 与 `/api/summary/stream`，SSE 按 `data: {"delta": "..."}` 逐块输出并以 `data: [DONE]` 结束，错误用固定文案脱敏。

### 步骤 4 前端流式渲染

在 `index.html` 中补齐转写段列表与总结流式区域，增量 `delta` 逐块追加，断连与解析失败有容错与手动重连。

### 步骤 5 联调与定位

启动后端后用 `curl -N` 与浏览器两侧验证同一 SSE 流，观察 Network 中的 `text/event-stream`，修复跨域与格式问题。

### 步骤 6 自检

运行 `python -m py_compile starter/main.py`，确认 `python starter/main.py --help` 退出码为 0，终端仿真可拼回全量，浏览器流式可演示，`git status` 干净。

## 验收标准

- [ ] 后端含健康检查、转写归一与 SSE 流式接口，wire 格式可被 curl 与 EventSource 同消费。
- [ ] 转写结果为统一段结构，错误脱敏，不含密钥与堆栈。
- [ ] 前端用 EventSource 增量渲染，收到 `[DONE]` 后关闭并显示完成，边界有容错。
- [ ] 全链路在本机可演示，首字可体感，能解释 SSE 与一次性 JSON 的差异。
- [ ] `python starter/main.py` 的仿真可拼回，`--help` 退出码为 0，仓库干净。

## 提交要求

提交 `starter/main.py`、`index.html`、`requirements.txt` 或 `pyproject.toml`、`README.md`，写清安装、终端仿真、服务启动与浏览器加 curl 验证命令。以演示与讨论验收。

## 预估用时

6 学时。

## 起手代码

见 `starter/` 目录。先运行 `python main.py` 看终端仿真，再 `python main.py --serve` 启动服务，浏览器打开 `index.html` 观察增量渲染，与 `curl -N http://127.0.0.1:8000/api/summary/stream` 对照同一 wire。
