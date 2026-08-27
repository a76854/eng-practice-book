# Lab07 starter 说明

本目录是实验七的起点骨架，对应 `book/part5_lab_guide/experiment07_fullstack_streaming/index.md`，打通录音上传到实时转写到 AI 总结的链路，并用 EventSource 做流式渲染。

## 包含内容

- `main.py`：FastAPI 后端骨架，含 `GET /api/health`、`POST /api/transcribe` 与 `GET /api/summary/stream` 的 SSE 实现，支持终端仿真与服务启动两态。
- `index.html`：纯静态前端，EventSource 订阅 `/api/summary/stream`，增量 `delta` 逐块追加，收到 `[DONE]` 后关闭并显示完成。
- `requirements.txt`：FastAPI 与 uvicorn 的最小依赖。

骨架保持“契约对齐、流式增量、脱敏可观测”的分层，后端统一段结构与固定中文错误文案，前端只做增量拼接与重连提示，便于把 `m2t.asr` 与 `m2t.llm` 的只读 mock 替换为真实模型。

## 运行命令

```bash
# 安装依赖
pip install -r requirements.txt

# 终端 SSE 仿真，不启动服务，可直接校验 wire 格式与拼回
python main.py
# 输出含 wire 首行、行数、rebuilt 拼回校验与脱敏提示

# 帮助信息
python main.py --help

# 启动后端服务（CORS 已放开）
python main.py --serve --port 8000
# 健康检查
curl http://127.0.0.1:8000/api/health
# 流式 wire 对照（逐行到达）
curl -N http://127.0.0.1:8000/api/summary/stream

# 语法校验
python -m py_compile main.py
```

前端为纯静态单文件，无需 `npm` 构建：

```bash
# 方式一，浏览器直接打开
# 双击 index.html 或用浏览器打开文件路径

# 方式二，同目录起静态服务（可选）
python -m http.server 5173
# 打开 http://127.0.0.1:5173/index.html

# 前端联调步骤
# 1 启动后端 python main.py --serve --port 8000
# 2 浏览器打开 index.html，点触发转写 mock，观察段列表
# 3 点开始流式总结，观察增量追加与完成提示
# 4 Network 面板确认 text/event-stream 持续连接
```

## 接口与流式提示

- `POST /api/transcribe` 接收 `{"filename": "sample.wav"}` 占位，内部只读调用 `m2t.asr.normalize_result` 的 mock 归一，返回 `{"segments": [{speaker, text, start, end}]}`。
- `GET /api/summary/stream` 为 SSE，响应头 `text/event-stream` 与 `Cache-Control: no-cache`，生成器按 chunk 逐块 `data: {"delta": "..."}`，最后 `data: [DONE]`。
- 错误不透传原始堆栈与密钥，经 `m2t.llm.map_llm_error` 或固定文案脱敏，前端仅展示可读提示。
- 跨域由后端 `CORSMiddleware` 放开，前端可用 `http://127.0.0.1:8000` 的显式 URL，静态文件亦可同源部署。

## 环境说明

- 路径示例统一写 `/`，`pathlib.Path` 处理路径，`curl -N` 在 Linux 上验证。

## 下一步

按实验文档步骤 3 至 5 补齐上下游替换点，在 `main.py` 中把 `demo_transcribe_result` 与 `demo_summary_text` 替换为真实 `m2t.audio` 加 `m2t.asr.transcribe` 与 `m2t.llm.LLMClient` 调用，在前端验证首字时延与断连重连的完整闭环。
