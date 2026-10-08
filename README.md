# 《python编程工程实践》

本仓库是《python编程工程实践》教科书的源文件，以文档查询案例串联工程实践，基于 MyST (`mystmd` v1) 构建。全书包含前言、正文 13 章、实验指导书 6 个实验与附录。实验任务写在 `book/lab_guide/`，`labs/` 仅保留实验一、二的数据生成脚本。

## 目录结构

```
eng-practice-book/
├── book/                                    # 教材正文（MyST Markdown + {code-cell}）
│   ├── preface.md                           # 前言
│   ├── STYLE.md                             # 全书写作契约（章骨架、围栏规范、构建校验）
│   ├── software_engineering/                # 第 1 至 2 章：开发者元技能 + 代码质量护城河
│   │   ├── dev_meta_skills/
│   │   └── code_quality/
│   ├── backend_development/                 # 第 3 至 7 章：后端全景、HTTP/RESTful、持久化、并发、综合实战
│   │   ├── backend_essence/
│   │   ├── http_restful/
│   │   ├── persistence_sql_orm/
│   │   ├── concurrency_perf/
│   │   └── backend_synthesis/
│   ├── frontend_collaboration/              # 第 8 至 10 章：前端工程化、Vue 3、通信联调
│   │   ├── frontend_overview/
│   │   ├── vue3_core/
│   │   └── communication_debugging/
│   ├── advanced_engineering/                # 第 11 至 13 章：外部集成、健壮性安全、部署 CI/CD
│   │   ├── external_integration/
│   │   ├── robustness_security/
│   │   └── deploy_cicd/
│   ├── lab_guide/                           # 实验指导书（index.md + 6 个实验 .md）
│   ├── appendix/                            # 附录
│   │   ├── appendix_a_course_design.md
│   │   ├── appendix_b_references.md
│   │   └── appendix_c_usage_of__init__.py.md
├── labs/                                    # 实验一、二的数据生成脚本
│   ├── lab01/generate_roster.py
│   └── lab02/generate_grades.py
├── myst.yml                                 # MyST 项目配置（toc 列前言 + 13 章 + 实验指导书 + 附录）
└── pyproject.toml                           # [book] 构建执行依赖 + [dev] 开发依赖
```

> `myst.yml` 的 `project.toc` 即全书目录权威来源；`labs/` 等可复用资产不参与正文编号。

## 环境准备

要求：Node 24（`mystmd` 需 Node 18+，CI 固定 Node 24.3.0）；Python 由 uv 按 `requires-python` 自动准备。

```bash
# 1) 克隆
git clone {仓库URL}
cd eng-practice-book

# 2) 同步依赖（uv 自动创建 .venv、生成 uv.lock，装好 book/dev 依赖）
uv sync --extra book --extra dev

# 3) 激活环境（后续命令直接使用 python/jupyter/pytest，也让 myst 能找到执行内核）
source .venv/bin/activate

# 4) 验证
python -c "import fastapi, jwt, yaml; print(fastapi.__version__, yaml.__version__)"
pytest --version && ruff --version && mypy --version
```

## 构建书籍

全书可执行代码以 ````{code-cell} ipython3` 围栏标记，`myst build --html --execute --strict` 会真实运行并校验，执行失败即非零退出，此为唯一构建门控。

```bash
# 1) 安装 MyST CLI
npm i -g mystmd
myst --version  # 本次验证使用 v1.11.0

# 2) 注册执行内核（让 myst 找到已激活环境中的 fastapi 等依赖）
python -m ipykernel install --user --name python3 --display-name "Python 3 (book)"
python -m ipykernel install --user --name book-venv --display-name "book-venv"
jupyter kernelspec list

# 3) 增量构建（日常写作，不重跑 code-cell）
myst build --html

# 4) 全量执行构建（CI/交稿前必跑，--strict 遇错即失败）
myst clean --execute -y && myst build --html --execute --strict
```

- 输出在 `_build/html/`，执行缓存由 `myst clean --execute -y` 清理；CI 每轮强制重跑。
- 写作契约见 `book/STYLE.md`：章骨架 `index.md`、围栏仅 `{code-cell} ipython3` / `bash`、章末 `summary_and_questions.md`。
- 部分 `code-cell` 需要外部服务的密钥（搜索、大模型），未配置时走优雅降级分支；密钥统一从环境变量读取，本地放进 `.env`（已在 `.gitignore`），CI 由 `secrets` 注入。
- 本地要跑真实调用：`set -a && source .env && set +a`，再 `myst clean --execute -y && myst build --html --execute --strict`。执行缓存按源码哈希复用，**改动环境变量后必须清缓存**，否则页面里仍是上一次的输出。
- `.env` 里只填你要用的 key，其余留空；占位文本会被当成真值，导致真实调用报鉴权失败（留空则走降级分支）。

## 实验

实验指导书在 `book/lab_guide/`，包含 6 个按领域组织的实验。实验三至六由读者自行创建项目和代码；实验一、二可使用 `labs/` 中的数据生成脚本。实验不提供起始代码、参考解或自动判分，验收以课堂演示和任务要求为准。

```bash
# 查看实验说明与数据生成脚本
cat book/lab_guide/index.md
ls labs/lab01/ labs/lab02/
```

## 可复用资产

- `pyproject.toml` 的 `[book]` extra：MyST 执行链依赖（`nbclient`/`ipykernel`/`jupyter-server`/`fastapi`/`PyJWT`/`sqlalchemy`/`httpx` 等）与示例所需的第三方客户端（`tavily-python`/`boto3`/`moto`/`fakeredis`）。
- `labs/`：实验一、二的数据生成脚本。
- `myst.yml` 的 `project.exclude` 已排除 `labs/**`、`evidence/**` 等非正文路径。

## 常见命令速查

| 目的 | 命令 |
|------|------|
| 安装依赖 | `uv sync --extra book --extra dev` |
| 全量执行构建 | `myst clean --execute -y && myst build --html --execute --strict` |
| 增量构建 | `myst build --html` |
| 查看内核 | `jupyter kernelspec list` |
| 构建检查 | `myst build --html --execute --strict 2>&1 \| tail -n 20` |

---

*构建在 Python 3.12 + Node 24 + mystmd v1.11.0 下验证；写作规范见 `book/STYLE.md`。*
