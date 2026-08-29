# 前后端联调与流式响应集成

本实验对应理论 [第9章 与外部世界的集成](../../part4_advanced_engineering/chapter09_external_integration/index.md)。建议先通读第9章 9.1 至 9.3 节的第三方集成模式、语音识别接入与大模型流式接口，再阅读 `m2t/asr.py` 的 `normalize_result` 与 `m2t/llm.py` 的 `LLMClient` / `map_llm_error`，最后参考 `book/part4_advanced_engineering/chapter09_external_integration/demo_llm_stream.py` 的 SSE 仿真思路，再动手。你会在本实验中用 FastAPI 打通录音上传、实时转写与 AI 总结的完整链路，用 EventSource 在前端做流式渲染，并在本机用 mock 完成可演示的联调闭环。

## 实验目标

- 能用 FastAPI 声明上传与流式接口，解释 SSE 的 `text/event-stream` 与 `data:` 行格式，以及为何流式能降低首字时延。
- 能说清前端如何用 EventSource 订阅流式响应，处理增量 `delta`、拼出全量、以及在断连时重连或提示。
- 能串联录音上传、实时转写与 AI 总结的链路，解释每一跳的失败域与脱敏边界，并用 `m2t` 只读 mock 在无网络时本地复现。
- 能按 OpenAPI 契约完成前后端联调，解释接口字段、状态码与错误文案如何对齐，避免前后端各自为政。
- 能在浏览器与 curl 两侧验证流式链路，定位跨域、事件格式或前端未增量渲染等常见联调问题并修复。

## 任务步骤

### 步骤 1 阅读理论与现状

1. 阅读 [第9章 9.1 第三方服务集成模式](../../part4_advanced_engineering/chapter09_external_integration/9.1_third_party_service_integration.md) 中关于超时、重试与错误脱敏的讨论，理解为何外部调用的配置与错误映射要收敛在一处。
2. 阅读 [第9章 9.2 语音识别接入](../../part4_advanced_engineering/chapter09_external_integration/9.2_asr_integration.md) 与 [9.3 大模型接口设计](../../part4_advanced_engineering/chapter09_external_integration/9.3_llm_api_design.md)，重点关注音频格式归一、结果多形状归一、结构化输出与 SSE 增量解析。
3. 打开 `m2t/asr.py` 与 `m2t/llm.py`，阅读 `normalize_result` 对三种结果形状的归一与 `LLMClient` 的懒创建、超时与脱敏逻辑，明确本实验可只读复用这些 mock 能力，无需真实模型与密钥。

> 环境约定：本书面向 Linux，本实验的前后端命令在 Linux 上一致，路径示例统一写 `/`，`pathlib.Path` 自动适配 `\`。启动后端时默认 `http://127.0.0.1:8000`，跨域由后端 CORS 放开，前端静态页直接用 `file://` 或同源 `http://` 打开皆可。

### 步骤 2 读懂起手骨架

1. 进入 `labs/lab07_fullstack_streaming/starter`，阅读 `README.md`、`main.py`、`index.html` 与 `requirements.txt`，梳理“后端 SSE 接口、前端 EventSource 订阅、mock 数据”三层的依赖方向。
2. 运行 `python -m py_compile main.py` 与 `python main.py --help`，确认骨架可解析且帮助信息完整。执行 `python main.py` 观察终端的 SSE wire 仿真输出，理解 `data: {"delta": "..."}` 与 `data: [DONE]` 的行格式。
3. 用编辑器打开 `index.html`，找到 `new EventSource('/api/summary/stream')` 的订阅、消息拼接与完成判断，留意前端如何把增量 `delta` 逐块追加到 DOM。

### 步骤 3 实现后端流式接口

1. 以 `starter/main.py` 为起点，完善 FastAPI 的流式链路：
   - `GET /api/health` 返回 `{"status": "ok"}`，供前端与 curl 做连通性检查。
   - `POST /api/transcribe` 接收上传或 JSON 占位，内部只读调用 `m2t.asr.normalize_result` 对 mock 结果做归一，返回统一段结构 `[{speaker, text, start, end}]`，失败时用固定中文文案脱敏。
   - `GET /api/summary/stream` 为 SSE 接口，设置 `text/event-stream` 与 `Cache-Control: no-cache`，用生成器按 `chunk_size` 逐块 `yield f"data: {json.dumps({'delta': chunk}, ensure_ascii=False)}\n\n"`，最后 `yield "data: [DONE]\n\n"`，无真实 LLM 时用本地假文本或只读复用 `m2t.llm` 的 mock 生成。
2. 保持错误脱敏，任何异常不把原始堆栈或密钥透传到响应，统一经 `map_llm_error` 或固定文案返回。
3. 在 `main.py` 中保留 `fake_sse_stream` 与 `parse_sse` 的本地仿真，便于 `python main.py` 不启动服务也能演示 wire 格式。

### 步骤 4 实现前端 EventSource 流式渲染

1. 在 `starter/index.html` 中完善流式面板：
   - 顶部为录音文件名或占位上传按钮，点击触发 `POST /api/transcribe` 的 mock 调用，展示归一后的段列表。
   - 中部为总结流式区域，`EventSource` 订阅 `/api/summary/stream`，每收到 `data:` 行即解析 `delta` 并追加渲染，收到 `[DONE]` 后关闭连接并显示完成态。
   - 底部为请求日志区，展示事件条数、首字时延体感与完整拼出文本，便于演示增量可用。
2. 处理边界，前端对空消息、JSON 解析失败与连接中断做容错，断连时提示并支持手动重连。
3. 保持前端为纯静态单文件，无构建步骤，`python -m http.server` 或直接双击打开皆可演示，后续替换真实接口只需改 `EventSource` 的 URL。

### 步骤 5 全链路联调与问题定位

1. 启动后端 `python main.py --serve --port 8000`，另起终端执行 `curl -N http://127.0.0.1:8000/api/summary/stream`，观察 SSE 行是否逐块到达，最后以 `data: [DONE]` 结束。
2. 在浏览器打开 `index.html`，触发转写与总结流式，验证从上传占位到段列表到增量总结的链路可演示，首字在百毫秒到秒级内出现，而非等全量才渲染。
3. 用浏览器开发者工具的 Network 面板观察 `text/event-stream` 的持续连接，覆盖跨域、事件格式错、前端未增量拼接等联调问题，并在 `main.py` 的 CORS 与响应头中修复。
4. 验证脱敏，构造一个含敏感串的异常并确认响应中不含密钥与原始堆栈，前端仅展示固定中文文案。

### 步骤 6 自检与清理

1. 运行 `python -m py_compile starter/main.py` 确认语法通过，执行 `python starter/main.py --help` 确认帮助信息完整且退出码为 0。
2. 运行 `python starter/main.py` 确认终端输出 SSE wire 首行、行数与拼回校验，浏览器打开 `index.html` 可见 EventSource 流式追加。
3. 用 `curl -N http://127.0.0.1:8000/api/summary/stream` 在服务启动时确认流式可被非浏览器客户端消费。
4. 用 `git status` 确认无 `.venv`、`__pycache__`、`node_modules/`、`dist/`、`*.db` 等不应提交的内容，准备演示全链路与首字时延的协作。

## 验收标准

逐条自查，全部勾选即视为完成：

- [ ] `starter/main.py` 含 FastAPI 的健康检查、转写占位与 SSE 流式接口，响应头含 `text/event-stream`，事件行符合 `data:` 格式并以 `data: [DONE]` 结束。
- [ ] 转写结果经 `m2t.asr.normalize_result` 或等价 mock 归一，返回统一段结构，错误经 `map_llm_error` 或固定文案脱敏，不透传密钥与堆栈。
- [ ] `starter/index.html` 用 EventSource 订阅流式接口，增量 `delta` 逐块渲染，收到 `[DONE]` 后正确关闭并显示完成态，断连与解析失败有容错。
- [ ] 录音上传到实时转写到 AI 总结的链路在本机可演示，首字时延可体感，浏览器与 curl 两侧均能消费同一 SSE 接口。
- [ ] 跨域、事件格式与增量拼接等联调问题可定位并修复，能口头解释 SSE 与一次性 JSON 在时延与渲染上的差异。
- [ ] `python -m py_compile starter/main.py` 通过，`python starter/main.py --help` 退出码为 0，`python starter/main.py` 的终端仿真可拼回全量。
- [ ] `git status` 干净，能口头解释每一跳的失败域与观测点，以及后续如何把 mock 替换为真实 ASR 与 LLM。

## 提交要求

- 提交包含 `starter/main.py`、`starter/index.html`、`starter/requirements.txt` 或 `starter/pyproject.toml`、`starter/README.md` 与顶层 `README.md` 的目录，`README.md` 需写清安装、终端仿真与服务启动、浏览器与 curl 验证命令。
- `index.html` 为纯静态单文件，无需构建步骤，助教按文档可在 5 分钟内复现上传占位到流式总结的闭环。
- 不需要提交 `.venv`、`__pycache__`、`node_modules/`、`dist/`、`*.db`、密钥或权重等生成物与敏感信息。
- 以演示与讨论作为验收，能现场启动后端、打开前端演示流式递增，并在终端用 curl 展示同一流的 wire 格式。

## 预估用时

6 学时。

建议分配：步骤 1 至 2 约 90 分钟，步骤 3 至 4 约 180 分钟，步骤 5 至 6 约 90 分钟。剩余时间用于自检与课堂讨论。
