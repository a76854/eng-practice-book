# AGENTS.md — 《算法编程与工程实践》教科书

面向"从算法与课程作业走向真实软件交付"的工程实践教材，MyST（mystmd v1）构建。
全书 = 前言 + 12 章正文 + 实验指导书（8 实验）+ 附录。

## 环境与构建

- 包管理用 **uv**（Python 3.12），依赖在 `pyproject.toml` 的 `book` / `dev` extra 里（不再有 requirements.txt，也不再有教学包）。
- 安装：`uv sync --extra book --extra dev`，然后 `source .venv/bin/activate`。
- **构建门禁（唯一验收）**：`myst build --html --execute --strict` 必须 EXIT=0 且零警告。当前 80 页，输出在 `_build/html/`。
- 执行内核 `book-venv`（新环境需先注册）：
  `python -m ipykernel install --user --name book-venv --display-name "book-venv"`。
- CI 在 `.github/workflows/book.yml`：`astral-sh/setup-uv` + `uv sync` + `echo "$PWD/.venv/bin" >> "$GITHUB_PATH"`（因为 myst 是 node CLI，靠 PATH 找 python/jupyter）。
- 要跑真实外部调用（搜索/大模型）：`set -a && source .env && set +a`（`.env` 里只填要用的 key，**其余必须留空**，占位文本会被当真值导致鉴权失败），然后 **`myst clean --execute -y` 清执行缓存**再构建：环境变量变化不会使缓存失效，不清就还是旧输出。

## 目录结构与编号（已重构定稿）

- 编号由 `myst.yml` 里 `numbering: { title: true, headings: true }` **自动生成**，不在文件名或正文里手写编号。
- **已去掉“篇”层级**：章直接挂在 toc 顶层，全局编号 1~12；节 = `X.Y`，小节 = `X.Y.Z`（三级，不再有四级）。
- 章文件夹仍在 part 目录下（`software_engineering / backend_development / frontend_collaboration / advanced_engineering`），但**只为文件管理，不进 toc**。
- 文件名、章文件夹名、篇文件夹名均无编号前缀（例：`backend_development/persistence_sql_orm/database_modeling_er.md`）。

12 章 → 文件夹映射：

| 章 | 目录路径 |
|---|---|
| 1 开发者的元技能 | `book/software_engineering/dev_meta_skills/` |
| 2 构筑代码质量的护城河 | `book/software_engineering/code_quality/` |
| 3 后端开发到底是什么 | `book/backend_development/backend_essence/` |
| 4 HTTP 与 RESTful 架构 | `book/backend_development/http_restful/` |
| 5 数据持久化 | `book/backend_development/persistence_sql_orm/` |
| 6 并发模型与性能工程 | `book/backend_development/concurrency_perf/` |
| 7 综合实战（注册接口贯穿三层） | `book/backend_development/backend_synthesis/` |
| 8 前端开发概况与工程化演进 | `book/frontend_collaboration/frontend_overview/` |
| 9 Vue3 核心机制与状态设计 | `book/frontend_collaboration/vue3_core/` |
| 10 与外部世界的集成 | `book/advanced_engineering/external_integration/` |
| 11 健壮性与安全底线 | `book/advanced_engineering/robustness_security/` |
| 12 部署、容器化与持续集成 | `book/advanced_engineering/deploy_cicd/` |

- 实验在 `book/lab_guide/` 下：“实验指导书”分组 index（`numbering: false`）+ 8 个实验文件（文件名无 `experiment0X_` 前缀），实验页 `numbering: false`，标题为“实验一 / 实验二 …”。
- 附录在 `book/appendix/`（“附录”分组，`numbering: false`，手动“附录A/B/C”标题）。

## 写作规范

- 全书写作契约见 `book/STYLE.md`（章骨架、围栏规范、构建校验清单），改书前先读它。
- 硬性红线：无 emoji、无口语化表达、无破折号“——”、无感叹号堆砌、不用直角引号「」、小节标题不用“术语：一句话定义”的公式模板（如“Node.js：前端的运行时与工具宿主”）。
- 每节骨架：`学完本节，你能回答`（3-4 问）→ 哲理引言（1 句，不出现比喻、不涉本节内容，不署名）→ 承上导言 → 概念分节（定义 + 对比表格 + 代码）→ 每 cell 做一件事（前置 1-2 句说明 + 后置观测小结）→ 小结 3-5 点。
- 可执行代码用 `{code-cell} ipython3`；Shell 用 ````bash` 围栏（仅展示）；配置文件用 ````dockerfile` / ````yaml` / ````json` 围栏（仅展示）。以声明式配置为主的小节（如第 12 章）不强制 code-cell，示例用展示围栏 + 本地校验命令。
- 正文**不出现** `meetingtotext` / `m2t` / `TaskStore`（教学包已整体删除，正文、实验脚手架与文档均已清理）。
- 图片文件名不能用空格（用连字符），.md 里引用不要写 `%20`。
- **不要用 subagent 做创作型修改**（用户反复强调：subagent 不清楚上下文、创作型工作必须主代理亲自做）。

## 当前状态（本次会话记忆）

- 分支：**`feat/restructure-drop-numbering`**（从 `main` 拉出，重构改动已做完但**尚未提交**，约 129 文件变更）。
- 本次会话依序完成：第 3/4 章三节化重写 → 第 5 章四点重写（建模/建库/SQL/ORM，加教师角色与范式例子）→ 第二篇综合实战节 → CI/依赖迁移到 uv + pyproject `[book]` extra → 全书去编号与去篇级的大重构。
- 二次修订的偏好：内容要有故事、循循善诱、先"为什么"后"怎么做"，不能罗列概念（用户多次纠正）。
- 本轮（后续会话）完成：第 11 章按新骨架重写（补密码与密钥存放、日志移到末位）→ 教学包 `m2t` 整体删除（`m2t/`、`m2t_tests/` 移除，`pyproject.toml` 改名为 `eng-practice-book` 并清理依赖，正文与实验全部去 m2t/MTT）→ 第 12 章按新骨架重写、依赖口径统一到 uv、新增"发布与回滚"、**整章不留 code-cell**（作者要求：声明式配置为主，示例用 `dockerfile`/`yaml`/`bash` 展示围栏）→ 补 `favicon.ico` 并在 `myst.yml` 声明（此前站点自检因 `/favicon.ico` 404 让构建 EXIT=1，`myst clean` 清掉遗留文件后暴露）。

## 待办（tech debt / 下一步）

1. **正文硬编码“第X章 / N.M 节”文字引用已错位**：综合实战插入成了第 7 章，前端 7→8、8→9，进阶 9→10、10→11、11→12。链接没断、是文字对不上，需清理改相对链接或交给自动编号。（第 11、12 章的引用与附录 B、前言已在本轮清理）
2. 第三篇要补“前后端通信 / 联调”的一整章（已商定：讲 fetch/axios、异步状态、契约落地、CORS 与错误处理）。
3. code-cell 标识不一致（第 3/4 章 `ipython3`，第 5/6 章 `python`），需统一到 STYLE.md 规范。
4. `labs/lab0X_*` 目录命名与实验标题不一致（如 `lab02_unit_test_static_check` vs 实验二“成绩等级评定”），属学生脚手架目录，是否统一待定。
5. 部分实验（lab03/lab07）主题仍为音频转写，与正文的文档查询案例不同源，是否统一待定。

## 安全/纪律提醒

- 只 commit 被显式要求的内容；不 `--force push`、不空提交。
- 构建出现 EXIT != 0 或警告必须修到干净再交。
- 改动后跑 `lsp_diagnostics`（对 .md 意义有限）+ 完整 `myst build --html --execute --strict` 验证。