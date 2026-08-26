---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: '0.13'
    jupytext_version: 1.16.4
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 代码质量：类型与静态检查

> 为什么这一章值得单列一章？前三章你已经能把项目跑起来、会用脚本批量处理、用 Git 协作。接下来最容易踩的坑是「代码看着能跑，一改就崩」——参数传错、返回值为 `None`、重构时漏改一处调用。类型注解与静态检查就是在「运行之前」把这类错误拦住的防线。本章用 Python 的渐进类型与 TypeScript 的 `strict` 模式作对比，带你读懂真实项目的 `ruff` / `mypy` / `eslint` 配置，并动手给 `m2t` 的一个模块补全类型，体会「无类型 → 加类型 → 工具变绿」的完整闭环。学完后，你能在任何 Python/TS 项目中自信地加类型、读报错、配检查。

## 学习目标

完成本章后，你将能够：

1. 能解释 Python 渐进类型（gradual typing）的含义，能为已有函数补全参数与返回值注解，并用 `mypy` 验证通过。
2. 能阅读 MeetingToText 真实项目的 `[tool.ruff]` / `[tool.mypy]` / `frontend/eslint.config.js` / `tsconfig.json` 配置，说明每项检查在防什么问题。
3. 能在本地运行 `ruff check` 与 `mypy`，读懂其错误码（如 `F401`、`arg-type`、`no-untyped-def`）并修复。
4. 能对比 Python（运行期不管类型、靠工具检查）与 TypeScript `strict`（编译期必检）的差异，为新项目选择合适的严格度。
5. 能按「先加类型 → 再跑检查 → 修到 0 告警」的流程，给 `m2t` 的任意纯函数模块加类型并保持测试通过。

## 先修要求

- 完成 [第1章 环境与项目骨架](chapter01_环境与项目骨架.md)，能在本地 `pip install -e ".[dev]"` 并运行 `pytest`。
- 会读 `pyproject.toml` 的基本段落（`project` / `tool.ruff` / `tool.mypy`），会用命令行运行 `ruff` / `mypy`。
- 无需 TypeScript 基础，本章从零对比。

## 正文

### 渐进类型：不改运行，只加信息

Python 是动态语言——同一个变量本轮是 `int`、下轮可以是 `str`，解释器运行前不检查类型。**渐进类型**的意思是：你可以「渐进地」给部分代码加注解，不加的地方保持动态，已加的地方由 `mypy` 等工具在运行前检查。注解不影响运行时行为（`python` 照样跑），只影响「人读代码」与「工具查错」。

```python
# 无注解：人要猜 a/b 是什么，工具也无法检查
def add(a, b):
    return a + b
```

```python
# 有注解：意图一目了然，mypy 能在调用处检查
def add(a: int, b: int) -> int:
    return a + b
```

第二版在运行时与第一版完全等价，但当你误写 `add("hi", 3)` 时，`mypy` 会在提交前报错，而不是等问题在线上才暴露。这就是「类型是给人和工具看的文档」。

TypeScript 走得更远：`tsconfig.json` 的 `strict: true` 会在编译时强制检查所有文件，未加类型就是错误。Python 允许你逐文件、逐函数渐进；TS 要求你一次性严格。二者在团队协作中互补：Python 适合存量项目逐步加固，TS 适合前端从第一天就守住质量。

### 真实项目的配置长这样（只读参考）

教学的目的是让你「会读真实配置」，而不是背默认参数。以下两段分别来自 MeetingToText 的 `pyproject.toml` 与 `frontend/eslint.config.js`，以 HEAD 为准，只读讲解。

**Python 侧：`pyproject.toml`**

```toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "SIM"]
# B008 与 FastAPI 的 Depends()/Path() 写法冲突，E402 是 server.py 的 sys.path 引导需要
per-file-ignores = { "backend/app/routers/deps.py" = ["B008"], "backend/app/server.py" = ["E402"] }

[tool.mypy]
python_version = "3.12"
warn_unused_ignores = true

[[tool.mypy.overrides]]
module = ["funasr.*", "torch.*", "torchaudio.*", "onnxruntime.*", "modelscope.*", "librosa.*", "soundfile.*", "numpy.*"]
ignore_missing_imports = true
```

逐项含义：

- `select = ["E","F","W","I","B","UP","SIM"]`：启用的 ruff 规则集。`E/W` 是 pycodestyle 风格与警告，`F` 是 pyflakes 逻辑错误（如未用导入 `F401`），`I` 是 import 排序，`B` 是 flake8-bugbear 可疑写法，`UP` 是 pyupgrade 语法升级，`SIM` 是简化重构建议。本书仓库 `m2t` 的配置与此一致，MeetingToText 仅多两行 `per-file-ignores` 处理框架必需的例外。
- `per-file-ignores`：对特定文件关闭特定规则。`B008` 在 `deps.py` 中关闭是因为 FastAPI 要求 `Depends()` 写在默认值位置，这恰好触发 `B008`，属于框架惯用法的必要豁免；`E402`（import 不在文件顶部）在 `server.py` 中关闭是因为该文件需先改 `sys.path` 再导入。
- `[tool.mypy]`：`python_version = "3.12"` 告诉 mypy 按 3.12 语法检查；`warn_unused_ignores` 提醒你删掉无用的 `# type: ignore`；`overrides` 对 `funasr`/`torch` 等含大量动态代码或缺失存根（stub）的第三方库关闭缺失导入检查，避免误报淹没真实错误。

**前端侧：`frontend/eslint.config.js` + `tsconfig.json`**

```js
// frontend/eslint.config.js（节选）
export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...pluginVue.configs['flat/recommended'],
  {
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',  // 存量渐进，允许 any
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      'no-empty': ['error', { allowEmptyCatch: true }],
    },
  },
)
```

```json
// frontend/tsconfig.json（节选）
{
  "compilerOptions": {
    "strict": true,
    "noFallthroughCasesInSwitch": true,
    "noUnusedLocals": false
  }
}
```

- `strict: true`：TS 的总开关，等价于同时开启 `strictNullChecks`、`noImplicitAny` 等 7 项子检查，未注明的变量会被判 `implicitly has an 'any' type`。
- `noFallthroughCasesInSwitch`：`switch` 漏 `break` 直接报错，与 Python `match` 的穷尽检查思路一致。
- `eslint` 的 `no-unused-vars` 对应 ruff 的 `F401`/`F841`，`no-explicit-any: off` 说明该项目对 `any` 仍宽松（渐进策略），与 mypy 的 `ignore_missing_imports` 呼应——都是「先让工具可用，再逐步收紧」。

`prettier`（`frontend/package.json` 的 `format` 脚本）只管格式（缩进、引号、换行），与 `eslint`/`ruff` 的「逻辑检查」正交：格式问题交给 prettier 自动修，逻辑问题交给 eslint/ruff 人工修，二者不互相替代。

### 演示：无类型 → 加类型 → ruff/mypy 前后对比

以 `m2t` 的导出模块为原型，构造一个最小可复现例子。先看无类型的版本（保存为 `demo_untyped.py`）：

```python
# demo_untyped.py — 无类型，ruff/mypy 均有告警
import os

def format_duration(seconds):
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}"

def pick_export(fmt):
    if fmt == "txt":
        return "text"
    elif fmt == "srt":
        return "srt"
    return None
```

用本书仓库的工具链检查（`ruff` 与 `mypy` 来自 `pyproject.toml` 的 `[project.optional-dependencies].dev`）：

```bash
$ ruff check demo_untyped.py
F401 [*] `os` imported but unused
F401 demo_untyped.py:1:8

$ mypy demo_untyped.py
demo_untyped.py:3: error: Function is missing a type annotation  [no-untyped-def]
demo_untyped.py:3: error: Need type annotation for "seconds"  [no-untyped-def]
demo_untyped.py:8: error: Function is missing a type annotation  [no-untyped-def]
demo_untyped.py:8: error: Need type annotation for "fmt"  [no-untyped-def]
demo_untyped.py:13: error: Incompatible return value type (got "None", expected "str")  [return-value]
Found 5 errors in 1 file (checked 1 source file)
```

解读：`F401` 是 ruff 发现 `import os` 未被使用；`no-untyped-def` 是 mypy 发现函数缺注解；`return-value` 是 `pick_export` 可能返回 `None` 却未在签名中声明。

加类型后的版本（`demo_typed.py`）：

```python
# demo_typed.py — 补全类型，工具变绿
def format_duration(seconds: int) -> str:
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}"

def pick_export(fmt: str) -> str | None:
    if fmt == "txt":
        return "text"
    elif fmt == "srt":
        return "srt"
    return None

def annotated_add(a: int, b: int) -> int:
    return a + b
```

再次检查：

```bash
$ ruff check demo_typed.py
All checks passed!

$ mypy demo_typed.py
Success: no issues found in 1 source file
```

关键改动：删掉未用 `import os`（消 `F401`）、为每个参数与返回值补注解、`pick_export` 的返回类型写成 `str | None`（Python 3.10+ 的联合语法，等价于 `Optional[str]`）以诚实反映「可能返回 None」的事实。两步之后，工具从 6 条告警降为 0，且后续任何误传（如 `format_duration("hi")`）都会被 `arg-type` 拦住。

> 小结：`ruff` 负责「代码表面问题」（未用导入、风格、可疑写法），`mypy` 负责「类型一致性」（参数/返回值是否对得上）。二者互补，CI 中常同时跑 `ruff check` 与 `mypy`，任一非 0 即阻断合并。

### 应用：给 `m2t` 某模块加类型

以 `m2t/export.py` 的 `_format_timestamp_srt` 为例，展示在真实模块上加类型的三步：

**第 1 步：选一个纯函数**

纯函数输入输出明确、最易加类型。`_format_timestamp_srt(seconds: float) -> str` 将秒数转为 `HH:MM:SS,mmm` 字幕时间戳，无 I/O、无全局状态，是理想起点。

**第 2 步：补注解并运行测试**

```python
# 加类型前（示意）
def _format_timestamp_srt(seconds):
    if seconds < 0:
        seconds = 0
    ms = int(round(seconds * 1000))
    ...
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
```

```python
# 加类型后
def _format_timestamp_srt(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
```

**第 3 步：跑检查并收紧**

```bash
$ ruff check m2t/export.py
All checks passed!

$ mypy m2t/export.py
Success: no issues found in 1 source file
```

若 `mypy` 仍报 `no-untyped-def`，说明还有未注解的辅助函数（如 `_seg_text`），继续补 `def _seg_text(seg: Any) -> str:` 直至全绿。收尾时可考虑在 `pyproject.toml` 中将 `strict = false` 逐步改为更严格的分组（如 `disallow_untyped_defs = true`），但本书教学保持 `strict = false` 的宽松起点，强调「渐进收紧」而非「一次到位」。

可运行的类型演示（`{code-cell}` 真实执行）：

```{code-cell} ipython3
from typing import get_type_hints

def annotated_add(a: int, b: int) -> int:
    """带类型注解的加法，mypy 视角等价于 reveal_type 演示。"""
    return a + b

def io_channels(flag: str) -> bool:
    """flag 为 'stereo' 返回 True，'mono' 返回 False，其余抛错。"""
    if flag == "stereo":
        return True
    if flag == "mono":
        return False
    raise ValueError(f"unknown flag: {flag}")

print("annotated_add(2, 3) =", annotated_add(2, 3))
print("type hints:", get_type_hints(annotated_add))
print("io_channels('stereo'):", io_channels("stereo"))
print("io_channels('mono'):", io_channels("mono"))
```

```{code-cell} ipython3
# 等价于 mypy 的 reveal_type：运行时用 get_type_hints 观察类型信息
import m2t
print("m2t version:", m2t.__version__)

def greet(name: str) -> str:
    return f"Hello, {name}"

# 运行时可观察到注解已被保留
print(greet.__annotations__)
# mypy 视角：reveal_type(greet)  # Revealed type is "def (name: str) -> str"
# 若去掉 name: str，mypy 会报: error: Need type annotation for "name"  [no-untyped-def]
print("mypy --version 概念验证：注解在运行时可被 get_type_hints 读取，静态时被 mypy 检查")
```

### 检查工具的分工与常见错误码

| 工具 | 管什么 | 典型错误码 | 遇到时做什么 |
|---|---|---|---|
| `ruff` (`E`/`W`) | 风格与格式 | `E501 line too long` | 换行或加 `# noqa: E501`（如 `presets.py` 的长行） |
| `ruff` (`F`) | 逻辑错误 | `F401 imported but unused`、`F841 unused variable` | 删掉未用导入/变量 |
| `ruff` (`I`) | import 排序 | `I001 unsorted imports` | `ruff check --fix` 自动排序 |
| `ruff` (`B`/`SIM`/`UP`) | 可疑写法与简化 | `B008 do not perform function call in argument defaults`、`SIM102` | 按建议重构，或在框架必需处 `per-file-ignores` |
| `mypy` | 类型一致性 | `no-untyped-def`、`arg-type`、`return-value`、`assignment` | 补注解或修正调用 |
| `eslint` | TS/JS 逻辑 | `no-unused-vars`、`no-explicit-any` | 对应 ruff 的 `F401`/`F841`，删未用或显式 `_` 前缀 |
| `prettier` | 格式 | —（自动重写） | `prettier --write .` 一键格式化，不与 eslint 争职责 |

记住一条规则：**格式问题自动修（`ruff --fix` / `prettier --write`），类型问题人工修（补注解、改调用）**。二者不要混为一谈。

### 改动并预测

以下 4 个实验均可在本地复现，每个实验按「改什么 → 预测 → 解释」三段式书写。建议先写预测，再运行验证。

#### 实验：去掉一个参数注解 → 预测 mypy 错误码

- **改什么**：把 `demo_typed.py` 中 `def annotated_add(a: int, b: int) -> int:` 的 `b: int` 改为无注解 `b`，即 `def annotated_add(a: int, b) -> int:`。
- **预测**：`ruff check` 仍通过（`ruff` 不检查类型），`mypy` 报 `error: Need type annotation for "b"  [no-untyped-def]`，若同时删掉返回值 `-> int` 则额外报 `Function is missing a type annotation  [no-untyped-def]`。
- **解释**：`mypy` 的 `no-untyped-def` 在「函数有部分注解但不完整」时触发，目的是防止「半注解」造成调用处误判。补回 `b: int` 后恢复 `Success`。这验证了「渐进类型要求要么全不注、要么全注」的检查策略。

```bash
$ mypy demo_typed.py
demo_typed.py:4: error: Need type annotation for "b"  [no-untyped-def]
Found 1 error in 1 file (checked 1 source file)
```

#### 实验：引入未用 import → 预测 ruff F401

- **改什么**：在 `demo_typed.py` 顶部加一行 `import os` 但不使用它。
- **预测**：`mypy` 仍 `Success`（未用导入不影响类型），`ruff check` 报 `F401 [*] 'os' imported but unused`，且 `ruff check --fix` 会自动删掉该行。
- **解释**：`F401` 来自 `pyflakes` 规则集（`select` 中的 `F`），专门捕捉「导入未用」。MeetingToText 的 `select` 包含 `F`，因此该问题在 CI 中必被拦。修复方式是删导入或在确需保留时加 `# noqa: F401`。

```bash
$ ruff check demo_typed.py
F401 [*] `os` imported but unused
Found 1 error.
```

#### 实验：把返回值 `str | None` 改为 `str` → 预测 mypy return-value

- **改什么**：把 `def pick_export(fmt: str) -> str | None:` 改为 `def pick_export(fmt: str) -> str:`，但保留 `return None` 分支。
- **预测**：`ruff` 仍通过，`mypy` 报 `error: Incompatible return value type (got "None", expected "str")  [return-value]`。
- **解释**：`return-value` 检查「实际返回类型是否可赋值给声明的返回类型」。`None` 不可赋值给 `str`，故报错。修复要么改回 `str | None`（诚实声明），要么去掉 `return None` 分支并在调用处保证 `fmt` 仅为 `"txt"`/`"srt"`。这演示了「用联合类型诚实表达可能失败」的实践。

```bash
$ mypy demo_typed.py
demo_typed.py:9: error: Incompatible return value type (got "None", expected "str")  [return-value]
Found 1 error in 1 file (checked 1 source file)
```

#### 实验：把 TS 的 `strict` 关掉 → 预测未用变量的检查变化

- **改什么**：在 `frontend/tsconfig.json` 中把 `"strict": true` 改为 `"strict": false`，或在 `eslint.config.js` 中把 `no-unused-vars` 从 `error` 改为 `off`，然后在某 `.ts` 文件中写 `const unused = 42;` 且不使用它。
- **预测**：`strict: true` 时 `tsc --noEmit` 会对隐式 `any` 与未用局部变量（若 `noUnusedLocals: true`）报错；改为 `false` 后 `tsc` 放过 `any` 相关错误。`eslint` 侧，`no-unused-vars: error` 时 `npm run lint` 报 `'_unused' is defined but never used`，改为 `off` 后静默。
- **解释**：`strict` 是 TS 的「一揽子严格度」开关，`eslint` 的 `no-unused-vars` 是独立的逻辑检查。二者正交：`tsc` 管类型严格度，`eslint` 管代码质量。MeetingToText 前端保留 `strict: true` 但将 `no-explicit-any` 设为 `off`，体现「类型严格、但对存量 `any` 宽松」的渐进策略，与 Python 侧 `ignore_missing_imports` 思路一致。

## 习题

> 参考答案与测试在 `answers/chapter04/`，运行 `.venv/bin/pytest answers/chapter04/ -q` 验证。题目均为 hermetic 纯函数，不依赖网络或外部服务。工具版本可用 `ruff --version` / `mypy --version` 验证（本章 `pyproject.toml` 中 `ruff>=0.9` / `mypy>=1.10`）。

1. **带类型的加法**：实现 `annotated_add(a: int, b: int) -> int`，返回 `a + b`。
2. **声道标志判别**：实现 `io_channels(flag: str) -> bool`，当 `flag == "stereo"` 返回 `True`，`flag == "mono"` 返回 `False`，其余抛 `ValueError`。
3. **时长格式化**：实现 `format_duration(seconds: int) -> str`，将秒数转为 `H:MM:SS`（如 `3661 -> "1:01:01"`，`61 -> "0:01:01"`）。
4. **导出格式校验**：实现 `pick_export_format(fmt: str) -> str`，若 `fmt` 在 `{"txt","srt","md"}` 中返回其小写去空格后的值，否则抛 `ValueError`。
5. **为给定函数补类型使 mypy 通过**：给定未注解函数 `def greet(name): return f"Hello, {name}"`，请在 `answers/chapter04/solution.py` 中提供已补全注解的版本 `def greet_typed(name: str) -> str`（用注释约定：原函数上方写 `# TODO: 补类型使 mypy 通过，原签名 def greet(name)`，答案需使 `mypy --ignore-missing-imports solution.py` 无 `no-untyped-def` 报错，且 `__annotations__` 包含 `name` 与 `return`）。
6. *（附加）* 实现 `describe_channels(n: int) -> str`，`1 -> "mono"`，`2 -> "stereo"`，其余抛 `ValueError`，并确保 `mypy` 对错误传参如 `describe_channels("2")` 报 `arg-type`。

## 延伸挑战

1. 选 `m2t` 中任意一个未完全注解的模块（如 `m2t/store.py` 的 `TaskStore`），为其所有公共方法补类型，使 `mypy m2t/store.py` 变绿，记录你补了几个 `Any` 与几个 `| None`。
2. 在 `frontend/src` 中故意写一个 `const x: any = 1;` 与一个未用变量 `const unused = 2;`，分别观察 `tsc --noEmit` 与 `npm run lint` 的输出差异，思考「类型检查 vs 风格检查」的分工。
3. 尝试把 `pyproject.toml` 的 `[tool.ruff.lint] select` 去掉 `"F"`，再跑 `ruff check` 观察 `F401` 是否消失；还原后思考「为什么 CI 要显式声明 select 而非用默认」。
