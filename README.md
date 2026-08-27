# 《算法编程与工程实践》

本仓库是《算法编程与工程实践》教科书的源文件，以 MeetingToText 为贯穿演示项目，用真实代码串联工程实践，基于 MyST (`mystmd` v1) 构建。全书采用五篇结构，正文 11 章 + 实验 8 个，配套 8 个 `labs/` 动手实验（README + starter 脚手架，无标准答案、无自动判分）。

## 目录结构

```
eng-practice-book/
├── book/                                    # 教材正文（MyST Markdown + {code-cell}）
│   ├── 前言.md                              # 前言
│   ├── STYLE.md                             # 全书写作契约（章骨架、围栏规范、构建校验）
│   ├── ai_policy.md                         # AI 工具使用政策
│   ├── part1_软件工程筑基/                  # 第一篇：开发者元技能 + 代码质量护城河
│   │   ├── chapter01_开发者的元技能/
│   │   └── chapter02_构筑代码质量的护城河/
│   ├── part2_后端开发全景与核心基石/         # 第二篇：后端全景、HTTP/RESTful、持久化、并发
│   │   ├── chapter03_后端开发到底是什么/
│   │   ├── chapter04_HTTP与RESTful架构/
│   │   ├── chapter05_数据持久化从SQL到ORM/
│   │   └── chapter06_并发模型与性能工程/
│   ├── part3_前端协作与现代前端基础/         # 第三篇：前端协作、Vue 3 核心
│   │   ├── chapter07_前端开发概况与工程化演进/
│   │   └── chapter08_Vue3核心机制与状态设计/
│   ├── part4_现代工程进阶与交付/             # 第四篇：外部集成、健壮性安全、部署CI/CD
│   │   ├── chapter09_与外部世界的集成/
│   │   ├── chapter10_健壮性与安全底线/
│   │   └── chapter11_部署容器化与持续集成/
│   ├── part5_实验指导书/                    # 第五篇：8 个实验（理论配套动手）
│   │   ├── experiment01_工程初始化与自动化脚本/
│   │   ├── experiment02_单元测试与静态检查实战/
│   │   ├── experiment03_里程碑A_CLI转写工具/
│   │   ├── experiment04_RESTful_API与数据库迁移/
│   │   ├── experiment05_异步改造与压力测试/
│   │   ├── experiment06_前端页面与路由状态管理/
│   │   ├── experiment07_前后端联调与流式响应/
│   │   └── experiment08_里程碑BC_全栈容器化与答辩/
│   ├── appendix/                            # 附录
│   │   └── 附录A_课程设计大作业选题.md
│   └── samples/                             # 最小可运行样例（如 vue-min）
├── labs/                                    # 实验脚手架（README + starter，无参考解/测试/判分）
│   ├── lab01_工程初始化/starter/
│   ├── lab02_单元测试与静态检查/starter/
│   ├── lab03_里程碑A_CLI转写/starter/
│   ├── lab04_RESTful_API与数据库/starter/
│   ├── lab05_异步改造与压测/starter/
│   ├── lab06_前端页面与路由状态/starter/
│   ├── lab07_前后端联调与流式/starter/
│   └── lab08_全栈容器化与答辩/starter/
├── m2t/                                     # 教学辅助包（精简实现，对应演示项目核心能力）
├── deploy-demo/                             # 部署演示（Dockerfile.backend / docker-compose.yml）
├── myst.yml                                 # MyST 项目配置（toc 列前言 + part1..5 + 附录）
├── requirements.txt                         # 构建执行依赖（nbclient/ipykernel/jupyter-server/fastapi）
└── pyproject.toml                           # m2t 包元数据（requires-python >=3.12, [dev] 含 pytest/ruff/mypy）
```

> `myst.yml` 的 `project.toc` 即全书目录权威来源；`m2t/`、`labs/`、`deploy-demo/`、`book/samples/` 均为可复用资产，不参与正文编号。

## 环境准备

要求：Python 3.12 + Node 24（`mystmd` 需 Node 18+，CI 固定 Node 24.3.0）。

```bash
# 1) 克隆
git clone {仓库URL}
cd eng-practice-book

# 2) 创建虚拟环境
uv venv --python 3.12 && source .venv/bin/activate
# 或
python3.12 -m venv .venv && source .venv/bin/activate

# 3) 安装教学包与开发依赖
pip install -e ".[dev]"

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

# 2) 注册执行内核（让 myst 找到 .venv 中的 fastapi/m2t）
.venv/bin/python -m ipykernel install --user --name python3 --display-name "Python 3 (book)"
.venv/bin/python -m ipykernel install --user --name book-venv --display-name "book-venv"
jupyter kernelspec list

# 3) 增量构建（日常写作，不重跑 code-cell）
myst build --html

# 4) 全量执行构建（CI/交稿前必跑，--strict 遇错即失败）
myst clean --execute -y && myst build --html --execute --strict
```

- 输出在 `_build/html/`，执行缓存由 `myst clean --execute -y` 清理；CI 每轮强制重跑。
- 写作契约见 `book/STYLE.md`：章骨架 `index.md`、围栏仅 `{code-cell} ipython3` / `bash`、章末 `小结与思考题.md`。

## 实验

第五篇为实验指导书（`book/part5_实验指导书/`），`labs/lab01..08` 为配套动手脚手架。每个实验仅含 `README.md`（任务说明）+ `starter/`（起始代码），不含参考解、测试或自动判分——以课堂讲解与动手完成度为准。

```bash
# 查看实验说明
cat book/part5_实验指导书/experiment01_工程初始化与自动化脚本/index.md
cat labs/lab01_工程初始化/README.md 2>/dev/null || echo "详见 book/part5"

# starter 为空脚手架，按实验 README 自行实现
ls labs/lab01_工程初始化/starter/
```

## 可复用资产

- `m2t/`：教学辅助包，精简实现 MeetingToText 核心能力（`asr` / `store` / `export` / `llm` / `audio`），`pip install -e ".[dev]"` 后可 `import m2t`。
- `deploy-demo/`：部署演示资产（`Dockerfile.backend`、`docker-compose.yml`、`ci.yml`），供第 11 章与实验 08 参考。
- `book/samples/vue-min`：前端最小可运行样例。
- `requirements.txt`：MyST 执行链依赖（`nbclient`/`ipykernel`/`jupyter-server`/`fastapi`）；`myst.yml` 的 `project.exclude` 已排除 `labs/**`、`m2t/**` 等非正文路径。

## 常见命令速查

| 目的 | 命令 |
|------|------|
| 安装依赖 | `pip install -e ".[dev]"` |
| 全量执行构建 | `myst clean --execute -y && myst build --html --execute --strict` |
| 增量构建 | `myst build --html` |
| 查看内核 | `jupyter kernelspec list` |
| 只读检查（演示项目） | `git -C /home/huiguo/tools/MeetingToText status --porcelain \| wc -l` |

---

*构建在 Python 3.12 + Node 24 + mystmd v1.10.1 下验证；写作规范见 `book/STYLE.md`。*
