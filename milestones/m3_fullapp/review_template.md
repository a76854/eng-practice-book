# M3 全栈应用答辩复盘论文模板

> 文件名建议：`report.md` / `review.md` / `复盘论文.md`（置于 `student_solution/` 或仓库根）  
> 字数：800–1500 字（中文）；提交 Markdown；hermetic 声明必含「不实现 ASR 本体，走 m2t mock / fake 模型」

---

## 标题

M3 全栈应用答辩复盘 — <学号 姓名> — <日期>

## 摘要（3–5 行）

用 3–5 行概括：本项目把上传/转写/列表/生成纪要/导出串成一条最小全栈链路；后端 FastAPI + 单工人 Future + SQLite（WAL）+ `m2t`（fake ASR / fake LLM / export）；前端为内联 HTML 列表页；全 hermetic（不实现 ASR 本体，走 m2t mock），TestClient 冒烟整条链路。

## 1. 项目回顾

- 链路回顾：上传(mock) → 转写(pending→done) → 列表 → 生成纪要(mock LLM) → 导出 txt/md 的时序与状态机
- 分工与里程碑：M1 CLI → M2 Web API → M3 全栈的增量关系；各成员职责（一句话/人）
- 演示方式：`GET /` 列表页截图 + `POST /transcribe` / `POST /generate` / `GET /export` 的一次完整调用日志（粘贴关键输出）

## 2. 技术选型与权衡

- 为何选 FastAPI + SQLite（WAL + busy_timeout）+ `ThreadPoolExecutor(max_workers=1)` + mock：与 MeetingToText 只读参考对齐，单工人保证串行、hermetic 保证离线可测
- 若接入真实 ASR（FunASR SenseVoice + CAM++）/ 真实 LLM（OpenAI 兼容 API）会如何改：懒导入、超时/重试、脱敏错误映射（`m2t.llm.map_llm_error`）、模型缓存
- 权衡：串行 vs 并行、SQLite vs Postgres、内联 HTML vs 完整 Vue——各列 1 条利弊

## 3. 遇到的坑与解法（至少 1 例）

选 1–2 例，按「现象 → 根因 → 解法 → 验证」四段写，例如：

- **坑 A：pending→processing 窗口不可观测** — 测试轮询始终 `done`，加 `time.sleep(0.12)` 与 `store.update(status="processing")` 后可观测
- **坑 B：`:memory:` SQLite 跨连接不可见** — 改为 tmp 文件落盘，`_resolve_db_path` 统一处理
- **坑 C：export 时 `segments` 不在 `store`** — 另用 `_results` / `_minutes` 内存缓存 + `full_text` 回退
- 贴 1 段关键代码或日志，说明如何用测试固化该坑

## 4. 测试与质量

- 冒烟链路：如何用 `TestClient` 串起上传→转写→列表→纪要→导出（含等待 `done` 的轮询逻辑）
- 一次「先写失败测试再改代码」的例子：贴失败 → 修复 → 通过的前后 diff 或 pytest 输出
- hermetic 保障：为何测试中 `assert "funasr" not in sys.modules` 能通过，fake 模型如何注入

## 5. 下一步（若再给一周）

列 2 项改进，按「做什么 → 为什么 → 如何验证」写，例如：

1. 实时录音 WebSocket + SSE 推流进度（延伸挑战）
2. 完整 Vue 列表页（`fetch(/tasks)` → 任务卡片 → 导出/纪要按钮）与 `VITE_API_BASE_URL` 打通
3. 容器化（多阶段 Dockerfile + compose healthcheck）与 CI 冒烟

## AI 辅助声明

> 本复盘论文中，哪些段落/代码借助了 AI 辅助（工具名 + 用途），哪些为独立完成；遵循 `book/ai_policy.md` 的诚信规则。

## 引用

- MeetingToText 只读参考：`backend/app/routers/*`、`backend/app/services/{pipeline,store,llm}`（灵感，不复制）
- `m2t` 教学包：`m2t.store` / `m2t.asr` / `m2t.llm` / `m2t.export`
- 其他引用（可选）：Jupyter Book、FastAPI、SQLite WAL 等

---

### 评分关注（教师 rubric 摘录）

- 链路完整性：五步链路是否均有证据（日志/截图/测试输出）
- hermetic 自洽：是否明确「不实现 ASR 本体，走 m2t mock / fake 模型」且测试无需真实服务
- 对 trade-off 的诚实表述：是否如实写坑与权衡，而非堆砌功能
- 测试证据：是否有「先失败后通过」的 TDD 痕迹与整链冒烟
