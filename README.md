# 《算法编程与工程实践》

本仓库是《算法编程与工程实践》教科书的源文件，以MeetingtoText案例串联工程实践，基于 MyST (`mystmd` v1) 构建。全书采用五篇结构，正文 11 章 + 实验 8 个，配套 8 个 `labs/` 动手实验（README + starter 脚手架，无标准答案、无自动判分）。

## 目录结构

```
eng-practice-book/
├── book/                                    # 教材正文（MyST Markdown + {code-cell}）
│   ├── preface.md                              # 前言
│   ├── STYLE.md                             # 全书写作契约（章骨架、围栏规范、构建校验）
│   ├── ai_policy.md                         # AI 工具使用政策
│   ├── part1_software_engineering/                  # 第一篇：开发者元技能 + 代码质量护城河
│   │   ├── chapter01_dev_meta_skills/
│   │   └── chapter02_code_quality/
│   ├── part2_backend_development/         # 第二篇：后端全景、HTTP/RESTful、持久化、并发
│   │   ├── chapter03_backend_essence/
│   │   ├── chapter04_http_restful/
│   │   ├── chapter05_persistence_sql_orm/
│   │   └── chapter06_concurrency_perf/
│   ├── part3_frontend_collaboration/         # 第三篇：前端协作、Vue 3 核心
│   │   ├── chapter07_frontend_overview/
│   │   └── chapter08_vue3_core/
│   ├── part4_advanced_engineering/             # 第四篇：外部集成、健壮性安全、部署CI/CD
│   │   ├── chapter09_external_integration/
│   │   ├── chapter10_robustness_security/
│   │   └── chapter11_deploy_cicd/
│   ├── part5_lab_guide/                    # 第五篇：8 个实验（理论配套动手）
│   │   ├── experiment01_project_init_automation/
│   │   ├── experiment02_unit_test_static_check/
│   │   ├── experiment03_milestone_a_cli/
│   │   ├── experiment04_restful_api_db_migration/
│   │   ├── experiment05_async_refactor_load_test/
│   │   ├── experiment06_frontend_routing_state/
│   │   ├── experiment07_fullstack_streaming/
│   │   └── experiment08_milestone_bc_container/
│   ├── appendix/                            # 附录
│   │   └── appendix_a_course_design.md
│   └── samples/                             # 最小可运行样例（如 vue-min）
├── labs/                                    # 实验脚手架（README + starter，无参考解/测试/判分）
│   ├── lab01_project_init/starter/
│   ├── lab02_unit_test_static_check/starter/
│   ├── lab03_milestone_a_cli/starter/
│   ├── lab04_restful_api_db/starter/
│   ├── lab05_async_refactor_load_test/starter/
│   ├── lab06_frontend_routing_state/starter/
│   ├── lab07_fullstack_streaming/starter/
│   └── lab08_fullstack_container/starter/
├── m2t/                                     # 教学辅助包（精简实现，对应演示项目核心能力）
├── deploy-demo/                             # 部署演示（Dockerfile.backend / docker-compose.yml）
├── myst.yml                                 # MyST 项目配置（toc 列前言 + part1..5 + 附录）
└── pyproject.toml                           # m2t 包元数据 + [book] 构建执行依赖 + [dev] 开发依赖
```

> `myst.yml` 的 `project.toc` 即全书目录权威来源；`m2t/`、`labs/`、`deploy-demo/`、`book/samples/` 均为可复用资产，不参与正文编号。

## 环境准备

要求：Node 24（`mystmd` 需 Node 18+，CI 固定 Node 24.3.0）；Python 由 uv 按 `requires-python` 自动准备。

```bash
# 1) 克隆
git clone {仓库URL}
cd eng-practice-book

# 2) 同步依赖（uv 自动创建 .venv、生成 uv.lock，装好教学包与 book/dev 依赖）
uv sync --extra book --extra dev

# 3) 激活环境（后续命令直接使用 python/jupyter/pytest，也让 myst 能找到执行内核）
source .venv/bin/activate

# 4) 验证
python -c "import m2t; print(m2t.__version__)"
pytest --version && ruff --version && mypy --version
```

## 构建书籍

全书可执行代码以 ````{code-cell} ipython3` 围栏标记，`myst build --html --execute --strict` 会真实运行并校验——执行失败即非零退出，此为唯一构建门控。

```bash
# 1) 安装 MyST CLI
npm i -g mystmd
myst --version  # 期望 v1.10.1

# 2) 注册执行内核（让 myst 找到已激活环境中的 fastapi/m2t）
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

## 实验

第五篇为实验指导书（`book/part5_lab_guide/`），`labs/lab01..08` 为配套动手脚手架。每个实验仅含 `README.md`（任务说明）+ `starter/`（起始代码），不含参考解、测试或自动判分——以课堂讲解与动手完成度为准。

```bash
# 查看实验说明
cat book/part5_lab_guide/experiment01_project_init_automation/index.md
cat labs/lab01_project_init/README.md 2>/dev/null || echo "详见 book/part5"

# starter 为空脚手架，按实验 README 自行实现
ls labs/lab01_project_init/starter/
```

## 可复用资产

- `m2t/`：教学辅助包，精简实现音频处理、任务存储、导出等最小能力（`asr` / `store` / `export` / `llm` / `audio`），`uv sync --extra dev` 后可 `import m2t`。
- `deploy-demo/`：部署演示资产（`Dockerfile.backend`、`docker-compose.yml`、`ci.yml`），供第 11 章与实验 08 参考。
- `book/samples/vue-min`：前端最小可运行样例。
- `pyproject.toml` 的 `[book]` extra：MyST 执行链依赖（`nbclient`/`ipykernel`/`jupyter-server`/`fastapi`/`sqlalchemy`）；`myst.yml` 的 `project.exclude` 已排除 `labs/**`、`m2t/**` 等非正文路径。

## 常见命令速查

| 目的 | 命令 |
|------|------|
| 安装依赖 | `uv sync --extra book --extra dev` |
| 全量执行构建 | `myst clean --execute -y && myst build --html --execute --strict` |
| 增量构建 | `myst build --html` |
| 查看内核 | `jupyter kernelspec list` |
| 构建检查 | `myst build --html --execute --strict 2>&1 | tail -n 20` |

---

*构建在 Python 3.12 + Node 24 + mystmd v1.10.1 下验证；写作规范见 `book/STYLE.md`。*
