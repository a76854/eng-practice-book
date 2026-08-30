---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 静态检查、类型检查与代码风格

学完本节，你能回答：

- 为什么代码风格不是"审美问题"，而是"协作成本问题"？
- Flake8 / Black / isort 三件套解决了什么问题，又带来了什么新的痛点？
- Ruff 如何用"一站式"方案统一检查、修复与格式化？
- `mypy` 和 Ruff 的职责分别是什么？它们在提交前与 CI 中如何协作？
- 如何把静态检查与类型检查配置为自动化的质量门禁？

> 如果把代码质量比作一栋建筑，Ruff 是施工监理，检查砖缝齐不齐、钢筋有没有露头；mypy 是结构工程师，审核承重墙够不够厚、梁柱的尺寸对不对。监理不管承重，工程师不管贴砖——但少了任何一个，大楼都迟早出问题。

代码风格检查关注的是形式的统一性，而非逻辑的正确性。逻辑正确由测试和类型系统保障，风格一致则是为了降低阅读者的认知摩擦——当所有代码遵循同一套缩进、命名、换行规则时，读者的注意力才能从“这句为什么这样写”转移到“这句在做什么”。在一个多人协作的项目中，风格不统一带来的成本是隐性的：每次切换模块都要重新适应一套新的表达习惯，每一次不必要的纠结都在消耗本该用于理解业务的心智。风格检查的意义不在于审美偏好，而在于把“怎么写”这件事从团队的日常讨论中彻底移除，让代码审查的对话回归逻辑和设计本身。

## 为什么需要自动化风格检查

代码风格上的争议——"单引号还是双引号"、"行长该不该超过 79"、"导入该不该按字母排序"——本身没有绝对的对错。但这些争议在团队协作中构成了**无意义的认知税**：每次 Code Review 都会有人花时间指出"这里少了个空格"、"那里引号不一致"，而真正需要讨论的逻辑反而被淹没。

更重要的是，**风格不一致会让 `git diff` 充满噪声**。当你格式化了一个文件，所有行都变了，`git blame` 被重置，真实改动被淹没在空格和换行里。这不是技术问题，是协作成本问题。

静态检查工具的目标，就是把"审排版"从 Code Review 中剥离出来，交给机器自动化执行。

## Ruff：风格检查与自动修复的一站式方案

### 从三件套到一站式

传统 Python 工程常需三件套：

- **Flake8**：发现未使用变量、未定义名称、圈复杂度等"逻辑异味"
- **Black**：以确定性规则格式化代码，终结"引号该用单还是双"的争论
- **isort**：统一 `import` 排序，避免导入顺序的无意义 diff

**三件套的痛点**在于规则分散、配置多处、速度各异。一个新成员加入团队，需要分别配置 Flake8、Black 和 isort，理解三套配置规则；CI 上要依次跑三个工具，每一个都是独立进程，累加时间可感知。

**Ruff 的出现把三件事合成一件**：它用 Rust 实现，同一工具覆盖 `E` / `F` / `W`（pycodestyle / pyflakes）、`I`（isort）、`B`（flake8-bugbear）、`UP`（pyupgrade）、`SIM`（simplify）等规则，比 Flake8 快 10–100 倍，且大量规则支持 `--fix` 自动修复。

> **说明**：Flake8 / Black / isort 仍是成熟方案，存量项目无需为迁移而迁移。新项目或教学项目选用 Ruff 的收益在于"单一配置、统一入口、更快反馈"；若团队已深度绑定 Black，也可让 Ruff 的 `format` 与 Black 保持兼容（`ruff format` 即 Black 兼容实现）。

### 规则与自动修复的思路

Ruff 的每条规则都有**编码、说明与是否可自动修复**。工程化落地的关键不是"开启所有规则"，而是"选一套能讲清原因的规则，并让修复自动化"。

| 规则集 | 编码前缀 | 作用 | 常用规则示例 |
|--------|----------|------|-------------|
| pyflakes | F | 逻辑错误 | `F401` 未使用导入、`F841` 未使用变量 |
| pycodestyle | E / W | 风格问题 | `E501` 行太长、`W292` 文件末尾缺少换行 |
| isort | I | 导入排序 | `I001` 导入顺序不正确 |
| flake8-bugbear | B | 常见隐患 | `B006` 可变默认参数、`B007` 未使用的循环变量 |
| pyupgrade | UP | 新语法提示 | `UP006` 可用 `list[int]` 替代 `List[int]` |
| simplify | SIM | 可读性简化 | `SIM102` 可合并嵌套 if |

**工作流**：`ruff check` 产出诊断 → `--fix` 自动修复可修复项 → `ruff format` 统一排版。

```python
# 以下代码包含多个需要 Ruff 介入的问题
import os, sys            # I001 导入未排序，E401 多个导入同行
import pathlib

x = 1
y = 2                     # F841 未使用变量

def foo(a, b, c):         
    if a:
        if b:             # SIM102 可合并为 if a and b
            print(a)
    return c              
# 运行 ruff check 会报告：
# - I001 导入未排序
# - F841 未使用变量 y
# - SIM102 可合并嵌套 if
```

### 格式化的一致性

`ruff format` 与 `ruff check` 职责分离：检查管"逻辑是否正确"，格式化管"排版是否统一"。二者共用 `line-length` 等配置，避免"格式化后行变短了，但检查认为行太长"这类冲突。

```python
# 一段未格式化的代码
def export(task, fmt):
    if fmt=="txt": return task["text"]
    return ""

# 运行 ruff format 后变为：
def export(task, fmt):
    if fmt == "txt":
        return task["text"]
    return ""
```

`ruff format` 的规则与 Black 兼容，因此不需要争论"该用哪种格式化风格"——Ruff 会告诉你标准答案。

## `mypy`：类型检查的守门人

如果说 Ruff 检查的是"代码写得规范吗"，那 `mypy` 检查的是"类型写得对吗"。

在上一节《类型系统与防御性编程》中，我们在代码里写满了类型标注——`def load(name: str, n: int) -> str:`、`str | None`、`Literal["txt", "srt", "md"]`。这些标注本身只是"注释"，并不会在运行时强制执行。写了 `name: str`，调用时传 `123` 进去，程序照常运行——类型标注不会主动拦住你。

`mypy` 的作用就是让这些标注变成**可执行的契约**。它在提交前扫描所有代码，检查类型标注是否与实际使用一致：

```python
# 以下代码在 mypy 检查时会报错
def greet(name: str) -> str:
    return f"Hello, {name}"

# 调用方传了 int，mypy 会报错
greet(42)  # error: Argument 1 to "greet" has incompatible type "int"; expected "str"
```

### 典型报错场景

`mypy` 能拦截的典型错误包括：

**1. 类型不匹配**

```python
def get_user(id: int) -> dict[str, str]:
    return {"id": id}  # error: dict value expects str, got int
```

**2. 空值未处理**

```python
def find_title(meta: dict[str, str]) -> str | None:
    return meta.get("title")

title = find_title({})
print(title.upper())  # error: Item "None" of "str | None" has no attribute "upper"
```

**3. 泛型容器使用不一致**

```python
def process(items: list[str]) -> None:
    for item in items:
        print(item)

process([1, 2, 3])  # error: list item has incompatible type "int"; expected "str"
```

## Ruff 与 mypy：两道防线的分工

| 维度 | Ruff | mypy |
|------|------|------|
| 检查对象 | 代码风格、未使用变量、导入排序、逻辑异味 | 类型形状是否一致 |
| 典型报错 | "变量没用到"、"导入没排序" | "传了 int 但期望 str"、"None 上没有 upper" |
| 自动修复 | 支持 `--fix` | 不能自动修复，需人工修正 |
| 与类型标注的关系 | 不关心类型标注 | 核心职责：验证类型标注是否正确 |

实际使用中，二者在提交前依次执行：

```bash
ruff check src/           # 风格 + 逻辑异味
mypy src/                 # 类型形状
ruff format --check src/  # 格式化是否一致
```

Ruff 负责"你写得规范吗"，mypy 负责"你写得对吗"。前者不保证逻辑正确，后者不保证排版统一。两者合起来，才是"最小可审查"的基线。

## 工程化配置：`pyproject.toml`

延续第一章"单一事实源"的理念，Ruff 与 mypy 的配置都统一写入 `pyproject.toml`：

```toml
# Ruff 配置
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "SIM"]

[tool.ruff.format]
# ruff format 兼容 Black 风格

# mypy 配置
[tool.mypy]
python_version = "3.12"
strict = false
warn_return_any = true
ignore_missing_imports = true
exclude = ['^tests/']
```

**关键配置解读**：

- `line-length = 100`：`ruff check` 与 `ruff format` 共用，避免"检查与格式化打架"
- `target-version = "py312"`：让 Ruff 识别 3.12 语法（如 `str | None`）
- `select`：按需开启规则集，每条规则都可追溯编码
- `strict = false`：新项目可开启 `true`，存量项目逐步收紧
- `ignore_missing_imports = true`：项目初期建议开启，避免第三方库缺类型 stub 导致大量误报

## 三道防线，层层递进

将类型系统、风格检查、类型检查三者串联，形成完整的代码质量防线：

```mermaid
graph LR
    A[编码] --> C[Ruff 风格检查]
    C --> D[mypy 类型检查]
    D --> E[测试]
    E --> F[合入主线]
```

三者不是替换关系，是叠加关系：

| 防线 | 工具 | 检查内容 | 拦截时机 |
|------|------|----------|----------|
| 第1道 | 类型标注 + 编辑器 | 形状一致性、空值处理 | 书写时 |
| 第2道 | Ruff | 风格、未使用变量、导入排序 | 提交前 / CI |
| 第3道 | mypy | 类型标注是否与实际使用一致 | 提交前 / CI |
| 第4道 | 测试 | 运行时行为是否正确 | 提交前 / CI |

## 集成到提交前与 CI

静态检查与类型检查的价值在于**自动化**，而非"想起来才跑一次"。

**提交前（本地）**：

在 `.git/hooks/pre-commit` 中配置：

```bash
#!/bin/bash
ruff check --fix src/
ruff format src/
mypy src/
```

或用 `pre-commit` 框架统一管理（见第 5 章）。

**CI 门禁**：

```bash
ruff check src/           # 必须通过（退出码 0）
ruff format --check src/  # 检查格式化是否一致
mypy src/                 # 必须通过（退出码 0）
```