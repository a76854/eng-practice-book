# 《算法编程与工程实践》

本仓库是《算法编程与工程实践》教科书的源文件，以 MeetingToText 为贯穿演示项目、用真实代码展示各项工程实践，基于 MyST (Jupyter Book 2 / `mystmd`) 构建，全书 16 章螺旋课纲（13 个教学单元 + 3 个里程碑）配套可执行代码与 hermetic 习题。

---

## 简介

本书以 MeetingToText 为贯穿演示项目，用真实代码串联工程实践（环境/协作/测试/HTTP/SQL/调试/并发/前端/部署等），全书 16 章螺旋进阶（13 个教学单元 + 3 个里程碑项目 M1/M2/M3），所有代码单元可执行、习题 hermetic 可测。

---

## 目录结构

```
eng-practice-book/
├── book/                          # 教材正文（MyST Markdown + {code-cell}）
│   ├── intro.md                   # 封面/简介（site root）
│   ├── chapter01_环境与项目骨架.md … chapter16 (16 章正文)
│   ├── intro.md                   # 简介（以 MeetingToText 为贯穿演示项目）
│   ├── STYLE.md                   # 全书写作契约（章骨架、代码约定、构建校验）
│   ├── ai_policy.md               # AI 工具使用政策（鼓励使用 AI，须读懂每一行）
│   ├── chapter01_环境与项目骨架.md
│   ├── chapter02_Shell与脚本自动化.md
│   ├── ...                        # chapter03..15 教学单元
│   ├── chapter06_里程碑M1_CLI转写工具.md
│   ├── chapter11_里程碑M2_WebAPI.md
│   ├── chapter16_里程碑M3_全栈应用与答辩.md
│   ├── forum_topics.md            # 每章论坛讨论题
│   └── samples/                   # 最小可运行样例（如 vue-min）
├── m2t/                           # 教学辅助包（精简实现，对应演示项目的核心能力）
│   ├── __init__.py
│   ├── asr.py                     # normalize_result / transcribe（mock/fake）
│   ├── store.py                   # TaskStore（SQLite + WAL）
│   ├── export.py                  # txt/srt/md 导出
│   ├── llm.py                     # LLMClient（timeout/max_retries + 脱敏）
│   └── audio.py
├── answers/                       # 习题参考答案（hermetic 纯函数，可 pytest）
│   ├── chapter01/
│   ├── chapter02/
│   └── ...
├── milestones/                    # 里程碑项目（黑盒评测）
│   ├── grader.py                  # 统一判分引擎 run_grader（pytest 唯一引擎）
│   ├── grader_selfcheck.sh
│   ├── m1_cli/{student_solution,tests,reference_solution}
│   ├── m2_webapi/{student_solution,tests,reference_solution}
│   └── m3_fullapp/{student_solution,tests,reference_solution}
├── pyproject.toml                 # 项目元数据（requires-python >=3.12, dev/asr 可选依赖）
└── README.md                      # 本文件（使用指南）
```

---

## 环境准备

**要求**：Python 3.12 + Node 24（前端章节与里程碑 M3 涉及；`mystmd` 需 Node 18+，CI 用 Node 24）。

```bash
# 1) 克隆
git clone {仓库URL}
cd eng-practice-book

# 2) 创建虚拟环境（任选其一）
uv venv --python 3.12 && source .venv/bin/activate
# 或
python3.12 -m venv .venv && source .venv/bin/activate

# 3) 安装教学包与开发依赖
pip install -e ".[dev]"

# 4) 验证
python -c "import m2t; print(m2t.__version__)"
pytest --version && ruff --version && mypy --version

# 5) 前端（chapter12 / M3 需要）
cd frontend 2>/dev/null && npm install && cd .. || echo "no frontend dir, skip"
```

> 说明：`pyproject.toml` 的 `[project.optional-dependencies].dev` 包含 `pytest + ruff + mypy + httpx + openai`；`pip install -e ".[dev]"` 为构建与测试的唯一入口。

---

## 构建书籍

全书可执行代码以 ````{code-cell} ipython3` 围栏标记，`myst build --html --execute` 会真实运行并校验（hermetic，失败即非零退出）。

```bash
# 1) 安装 MyST CLI（Node 24 已装好）
npm install -g mystmd
myst --version

# 2) 注册执行内核（让 myst 找到 venv 中的 fastapi/httpx）
.venv/bin/python -m ipykernel install --user --name python3 --display-name "Python 3 (book-venv)"
.venv/bin/python -m ipykernel install --user --name book-venv

# 3) 增量构建（日常写作，不重跑 code-cell）
myst build --html

# 4) 全量执行构建（CI/交稿前必跑，--execute 强制重跑所有 code-cell）
myst clean --execute && myst build --html --execute

# 5) 严格模式（执行错误即失败，CI 默认行为）
myst build --html --execute --strict
```

- 配置见 `myst.yml` (version: 1)：`project.title: 算法编程与工程实践`、`project.toc` 列 `book/intro.md` + 16 章（`chapter01..16`），`exclude` 排除 `STYLE.md`/`ai_policy.md`/`forum_topics.md` 等非正文。
- 扩展：`colon_fence` / `dollarmath` / `linkify` / `tasklist` 在 mystmd 中默认启用（`substitution` 已移除，Vue `{{ }}` 位于 code fences 内无需处理）。
- 输出在 `_build/html/`（site 数据在 `_build/site/`），执行缓存由 `myst clean --execute` 清理；CI 每轮强制重跑。

---

## 运行习题测试

习题为 hermetic 纯函数题，答案在 `answers/`，测试不依赖网络/外部服务/真实文件系统。

```bash
# 全量习题
.venv/bin/pytest answers/ -q

# 单章（如 chapter01）
.venv/bin/pytest answers/chapter01 -q
.venv/bin/pytest answers/chapter01 -v

# 某题
.venv/bin/pytest answers/chapter05/test_chapter05.py -k test_normalize -q
```

- 约定：每章 ≥5 题，`answers/chapterNN/solution.py` 为参考解，`test_*.py` 为断言；`pytest answers/ -q` 绿为门控。
- 质量门：`ruff check .` 与 `mypy` 亦在 CI 中执行，提交前建议本地同跑。

---

## 做里程碑项目

里程碑是本课程的 3 次综合交付（M1 CLI、M2 WebAPI、M3 全栈），均在 `milestones/` 下以统一结构组织：

```
milestones/m1_cli/
  README.md               # 任务说明（权威）
  student_solution/       # 学生提交（被测对象，grader 默认测此目录）
    cli.py                # 需实现 build_parser() + main(argv)
  tests/                  # 黑盒测试（唯一判分依据，只断言退出码/文件/接口）
    conftest.py
    test_cli.py
  reference_solution/     # 教师参考解（用于自检与对照）
  verify_reverse.sh       # 双反向验证脚本
```

`m2_webapi` / `m3_fullapp` 结构相同（`app.py` 为入口）。

### grader 用法

唯一判分引擎为 `pytest`，由 `milestones/grader.py:run_grader` 封装，自动将 `solution_dir` 注入 `PYTHONPATH` 首位。

```bash
# 测学生提交（默认 student_solution）
python -m milestones.grader milestones/m1_cli
python -m milestones.grader milestones/m2_webapi
python -m milestones.grader milestones/m3_fullapp

# 测参考解（自检）
python -m milestones.grader milestones/m1_cli --solution reference_solution

# 测任意目录
python -m milestones.grader milestones/m1_cli --solution-dir /tmp/my_impl

# 直接 pytest（hermetic，conftest.py 保证直接运行也能回退到 reference）
.venv/bin/pytest milestones/m1_cli/tests -q
.venv/bin/pytest milestones/m2_webapi/tests -q
.venv/bin/pytest milestones/m3_fullapp/tests -q
```

编程调用：

```python
from milestones.grader import run_grader
r = run_grader("milestones/m1_cli")
print(r.passed, r.summary)
```

### 双反向验证

为保证“测试非空心”，每个里程碑提供 `verify_reverse.sh`，执行三分支：

1. 好解 → PASS（reference_solution 绿）
2. buggy 实现 → FAIL（故意破坏的实现应被判红）
3. 学生测试 × buggy → FAIL（学生自写测试若空心则无法捕捉 bug）

```bash
bash milestones/m1_cli/verify_reverse.sh
bash milestones/m2_webapi/verify_reverse.sh
bash milestones/m3_fullapp/verify_reverse.sh
# 全量自检（与 CI 一致）
bash milestones/grader_selfcheck.sh
```

产物可重定向到 `evidence/` 用于交稿审计。

---

## 学生与教师使用路径

### 作为学生

1. **读教材**：按 `myst.yml` 的 `project.toc` 顺序阅读 `book/intro.md → chapter01..16`，每章先看动机与学习目标，再运行正文中的 `{code-cell}`。
2. **做改动并预测**：每章 ≥3 个实验，按“改什么 → 预测 → 解释”三段式手写预测再运行验证（可用 AI 辅助生成改动，但必须先读懂并先预测，见 `book/ai_policy.md`）。
3. **做习题**：在 `answers/chapterNN/` 中实现 `solution.py`，本地 `pytest answers/chapterNN -q` 绿后再对照参考解。
4. **做里程碑**：阅读 `milestones/mX/README.md`，在 `student_solution/` 中实现，通过 `python -m milestones.grader milestones/mX` 自检，最后跑 `verify_reverse.sh` 确认测试有效。
5. **构建验证**：交稿前 `myst build --html --execute` 与 `pytest answers/ -q` 双绿，`git -C /home/huiguo/tools/MeetingToText status --porcelain | wc -l` 保持 0（演示项目只读）。

### 作为教师

1. **备课**：以 `book/STYLE.md` 为写作契约，以 `book/intro.md` 的“以 MeetingToText 为贯穿演示项目”为主线串联 16 章；演示项目 MeetingToText 仅作演示背景，不以其内部路径为教材主体。
2. **出题与批改**：习题以 `answers/` 的 hermetic 测试为判分依据；里程碑以 `milestones/grader.py` 黑盒测试为唯一判分引擎，`reference_solution` 为满分对照，`verify_reverse.sh` 保障测试质量。
3. **课堂与答辩**：用 `book/forum_topics.md` 组织讨论；M3 答辩关注链路完整性、hermetic 自洽与 trade-off 诚实表述，配合 `book/ai_policy.md`（鼓励使用 AI、以读懂/能解释/能预测为底线）进行 AI 辅助声明核查。
4. **CI 门控**：`myst clean --execute && myst build --html --execute`、`pytest answers/ -q`、`ruff check`、`mypy` 与 `milestones/grader_selfcheck.sh` 构成提交门控；`_build/` 不入库。

---

## 常见命令速查

| 目的 | 命令 |
|------|------|
| 安装 | `pip install -e ".[dev]"` |
| 构建 | `myst build --html --execute` |
| 习题 | `.venv/bin/pytest answers/ -q` |
| 单章习题 | `.venv/bin/pytest answers/chapter01 -q` |
| 里程碑 | `python -m milestones.grader milestones/m1_cli` |
| 反向验证 | `bash milestones/m1_cli/verify_reverse.sh` |
| 只读检查 | `git -C /home/huiguo/tools/MeetingToText status --porcelain \| wc -l` |

---

*构建与测试均在 Python 3.12 下验证；问题请见 `book/forum_topics.md` 或提 issue。*
