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

# 第5章 测试的思维与工程

> 写代码只花一天，修 Bug 却花一章——差距往往不在编码速度，而在是否有测试把行为钉住。测试不是「写完代码后的检查表」，而是一种思维方式：先把期望说清楚，再让代码去满足它。本章以 `m2t.asr` 的结果归一化（把 FunASR 不稳定的原始回包收敛为统一的 `[{speaker, text, start, end}]`）为贯穿例子，学习 pytest 的核心用法、参数化（parametrize）、固件（fixture）、四层测试划分与测试先行（test-first），并在 hermetic（隔离）单测中把三种结果形状与空结果一次性覆盖。

## 学习目标

完成本章后，你将能够：

1. 能解释四层测试划分（单元/集成/系统/端到端）的适用边界，并为 `normalize_result` 这类纯函数选择单元层。
2. 能用 pytest 编写 hermetic 单测，覆盖 `m2t.asr.normalize_result` 的三种输入形状与空结果。
3. 能使用 `@pytest.mark.parametrize` 消除重复用例，并预测用例数量随参数表的变化。
4. 能使用 `fixture` 复用测试数据与隔离状态，并解释其作用域（scope）对性能与隔离的影响。
5. 能实践测试先行：为一个已知 buggy 的 `normalize` 实现编写「杀死 bug 的测试」，并用测试驱动修复。

## 先修要求

- 已完成第1章「环境与项目骨架」——能在 `.venv` 中 `pip install -e ".[dev]"` 并 `pytest -q`。
- 会阅读 `m2t/asr.py` 的 `normalize_result` 签名与 docstring（`result: list[Any] -> list[dict]`，时间单位毫秒转秒）。
- 无需 Web/数据库知识，本章所有例子均为纯函数 hermetic 测试，不依赖网络、文件系统或外部服务。

## 正文

### 5.1 测试的思维：为什么先把期望写清楚

工程直觉：Bug 的修复成本随发现阶段指数上升——在编码时用断言发现，成本几乎为零；到联调或线上才发现，成本则是定位、复现、回归与用户影响的总和。测试的思维就是把「期望行为」提前用可执行的代码表达出来，让机器替你日夜守门。

两条原则：

- **hermetic（隔离）**：单元测试不碰网络、文件、外部服务。`m2t.asr.normalize_result` 只做内存中的数据变换，天然适合 hermetic 测试——输入一个 `list`，断言输出的 `speaker/text/start/end`，不启动 FunASR 模型。
- **测试先行（test-first）**：先写失败的测试，再写最少代码使其通过。下一节会用一个 buggy 实现演示：先让测试杀死 bug，再修复。

与之对应的是四层划分：

| 层 | 测什么 | 典型例子 | 速度 |
|---|---|---|---|
| 单元（unit） | 单个纯函数/类 | `normalize_result` 的分支覆盖 | 毫秒级 |
| 集成（integration） | 模块与真实依赖协作 | `transcribe` 调 fake model 再归一化 | 秒级 |
| 系统（system） | 子系统端到端 | CLI `m2t transcribe {音频}` 输出文件校验 | 秒到十秒 |
| 端到端（e2e） | 用户视角完整链路 | 上传→转写→导出 浏览器操作 | 十秒以上 |

本章聚焦单元层，其余层在后续章（第7章 后端、第14章 部署）逐步展开。MeetingToText 的 `tests/{unit,integration,system}` 目录与 `pyproject.toml` 中的 `addopts = "-m 'not system'"` 即是这一划分的实践参考，本书仅借其分层思路。

### 5.2 pytest 基础：一个测试即一个断言

pytest 约定：文件名 `test_*.py`、函数名 `test_*`、用 `assert` 断言。示意如下（仅示意，不被执行）：

```python
from m2t.asr import normalize_result

def test_sentence_info_shape_single_speaker():
    # Given: 带 sentence_info 的 FunASR 回包（毫秒）
    result = [{"sentence_info": [{"text": "你好", "start": 1000, "end": 2500, "spk": 0}]}]
    # When: 归一化
    segments = normalize_result(result)
    # Then: 说话人 1 基、时间转秒
    assert segments == [{"speaker": "说话人1", "text": "你好", "start": 1.0, "end": 2.5}]
```

执行：

```bash
.venv/bin/pytest answers/chapter05/ -q
# 或只跑本章
.venv/bin/pytest answers/chapter05/test_chapter05.py -q -v
```

关键点：一个测试只验证一件事；失败信息即文档。若 `normalize_result` 忘记把毫秒除以 `MS_PER_S`，断言会直接告诉你 `1.0 != 1000.0`。

### 5.3 参数化：用一张表覆盖多条分支

三种形状若各写一个函数，断言逻辑会大量重复。`@pytest.mark.parametrize` 把「输入表」与「期望表」解耦：

```python
import pytest
from m2t.asr import normalize_result

@pytest.mark.parametrize("raw, expected", [
    # 空结果
    ([], []),
    # sentence_info 形状
    (
        [{"sentence_info": [{"text": "你好", "start": 0, "end": 1000, "spk": 1}]}],
        [{"speaker": "说话人2", "text": "你好", "start": 0.0, "end": 1.0}],
    ),
    # raw_text + timestamp 回退
    (
        [{"text": "整体文本", "timestamp": [[0, 1000]]}],
        [{"speaker": "", "text": "整体文本", "start": 0.0, "end": 1.0}],
    ),
])
def test_normalize_parametrized(raw, expected):
    assert normalize_result(raw) == expected
```

表中有几行，pytest 就生成几条用例（上例为 3 条）。新增一行即新增一条用例，无需复制函数。

### 5.4 fixture：复用与隔离

fixture（固件）是 pytest 的依赖注入机制，用于复用构造逻辑并保证隔离。对比直接在函数内构造，fixture 的优势是作用域可控与 teardown 统一管理。

```python
import pytest
from m2t.asr import normalize_result

@pytest.fixture
def sentence_info_result():
    return [{"sentence_info": [
        {"text": "你好", "start": 1000, "end": 2500, "spk": 0},
        {"text": "好的", "start": 3000, "end": 4000, "spk": 1},
    ]}]

def test_with_fixture(sentence_info_result):
    segs = normalize_result(sentence_info_result)
    assert len(segs) == 2
    assert segs[0]["speaker"] == "说话人1"
```

常用 `scope`：`function`（每测试一次，默认，隔离最好）、`module`/`session`（跨测试复用，适合重型资源如临时数据库）。本章习题会要求你为 `normalize_result` 的三种形状各写一个 fixture，体会「复用而不共享可变状态」。

### 5.5 测试先行：先让测试杀死 bug

测试先行的反向练习：给你一个已知的 buggy 实现，任务是写一条测试使其失败——测试是「猎手」，bug 是「猎物」。修复前测试红，修复后测试绿。

以 `m2t.asr` 为例，假设 buggy 版本忘记把时间除以 1000：

```python
# buggy_normalize.py（示意）
def normalize_result_buggy(result):
    # ... 省略其他分支 ...
    # Bug: 忘记 / MS_PER_S
    return [{"speaker": "说话人1", "text": "你好", "start": 1000, "end": 2500}]
```

对应的捕猎测试：

```python
def test_kills_ms_bug():
    result = [{"sentence_info": [{"text": "你好", "start": 1000, "end": 2500, "spk": 0}]}]
    segs = normalize_result_buggy(result)
    # 期望是秒，若实现仍是毫秒，必失败
    assert segs[0]["start"] == 1.0
    assert segs[0]["end"] == 2.5
```

这条测试在 buggy 上失败、在正确实现上通过——即「测试杀死了 bug」。`answers/chapter05/buggy_impl.py` 提供了一份故意带 bug 的实现，`test_buggy_demo.py` 中的演示测试在正常 `pytest` 运行时被跳过，避免污染绿条；去掉 `@pytest.mark.skip` 即可亲眼看到失败。

### 5.6 应用：为 m2t.asr.normalize_result 写 hermetic 单测

`m2t.asr.normalize_result` 的签名（以本书仓库 `m2t/asr.py` HEAD 为准，归一化为 `normalize_result(result: list[Any]) -> list[dict[str, Any]]`，时间毫秒转秒，`SPEAKER_LABEL_TEMPLATE = "说话人{}"` 1 基渲染）与 `backend/app/services/asr_parse.py` 的 `parse_result` 同源，已在第1章 引入。本节把它作为单元测试的完整示例。

覆盖矩阵：

- **形状 1 sentence_info**：含 `text`/`sentence`、`spk` 缺失、`start/end` 缺失、含标签 `<|zh|>` 与句首标点需清洗、空字符串跳过。
- **形状 2 raw_text + timestamp**：`text` 为 `str` 与 `list` 两种、多个 timestamp 对齐、`timestamp` 非法项跳过。
- **形状 3 空结果**：`[]`、`[{}]`、`None`/`str` 非 list、`sentence_info` 与 `timestamp` 皆空时返回 `[]`。

下面是一段可在本章直接运行的最小演示：三种形状 + 空结果，用内联函数模拟 pytest 风格断言。

```{code-cell} ipython3
from m2t.asr import normalize_result, MS_PER_S, SPEAKER_LABEL_TEMPLATE

def _mini_test():
    # 形状1：sentence_info
    r1 = [{"sentence_info": [{"text": "你好", "start": 1000, "end": 2500, "spk": 0}]}]
    s1 = normalize_result(r1)
    assert s1 == [{"speaker": "说话人1", "text": "你好", "start": 1.0, "end": 2.5}], f"shape1 failed: {s1}"
    assert s1[0]["start"] == 1000 / MS_PER_S
    assert s1[0]["speaker"] == SPEAKER_LABEL_TEMPLATE.format(1)

    # 形状2：raw_text + timestamp
    r2 = [{"text": ["第一句", "第二句"], "timestamp": [[0, 500], [500, 1000]]}]
    s2 = normalize_result(r2)
    assert s2 == [
        {"speaker": "", "text": "第一句", "start": 0.0, "end": 0.5},
        {"speaker": "", "text": "第二句", "start": 0.5, "end": 1.0},
    ], f"shape2 failed: {s2}"

    # 形状3：空结果
    assert normalize_result([]) == []
    assert normalize_result([{}]) == []
    assert normalize_result(None) == []

    # 清洗：标签与句首标点
    r3 = [{"sentence_info": [{"text": "<|zh|>。，你好", "start": 0, "end": 1000, "spk": 0}]}]
    assert normalize_result(r3)[0]["text"] == "你好"

    print("全部 mini 断言通过 — 三种形状 + 空结果 + 清洗")

_mini_test()
```

这段 `{code-cell}` 在 `jupyter-book build --execute` 时会被真实执行；若任一断言失败，构建即失败。把它视作「嵌入正文的单测」——正文不再只是文字，而是可运行的规格。

pytest 中的完整写法（示意，`answers/chapter05/test_chapter05.py` 为可执行版本）：

```python
@pytest.mark.parametrize("case", ["sentence_info", "fallback", "empty"])
def test_shapes(case, sample_results):
    # sample_results 为 fixture，返回三种形状的字典
    ...
```

```bash
.venv/bin/pytest answers/chapter05/ -q
# 预期：全部通过，且报告用例数 = 参数表行数
```

### 改动并预测

以下实验均可在本地 `.venv` 中复现，每个按「改什么 → 预测 → 解释」三段式。

#### 改动并预测 实验 1：为一条 buggy 实现写测试 → 预测测试失败

- **改什么**：把 `answers/chapter05/buggy_impl.py` 中 `normalize_result` 的 `float(start) / MS_PER_S` 改回 `float(start)`（即忘记毫秒转秒），或直接将 `m2t.asr.normalize_result` 替换为 `buggy_impl.normalize_result` 后，运行 `pytest answers/chapter05/test_buggy_demo.py -v`（去掉 skip 后）。
- **预测**：`test_kills_ms_bug` 失败，断言信息类似 `assert 1000.0 == 1.0`；其他依赖时间断言的用例一并失败。
- **解释**：测试把「时间以秒为单位」这一契约钉死，buggy 实现破坏了契约，测试即告警。先写失败测试再修 bug，正是测试先行的价值——测试成为 bug 的可复现证明。

#### 改动并预测 实验 2：加 @pytest.mark.parametrize → 预测用例数翻倍

- **改什么**：在 `test_chapter05.py` 中把参数表从 3 行扩为 6 行（为每种形状各加一个边界条件，如 `spk` 缺失与 `timestamp` 非法项）。
- **预测**：`pytest -q` 报告的用例数从 N 变为 N+3（或从 3 变为 6），新增用例独立报告通过/失败，不影响原有用例的隔离性。
- **解释**：`parametrize` 的每一行即一条独立用例，pytest 在收集期展开。参数化的本质是「用数据驱动用例生成」，避免复制函数体。

#### 改动并预测 实验 3：把 fixture scope 从 function 改为 module → 预测隔离性变化

- **改什么**：把 `sentence_info_result` fixture 的 `@pytest.fixture(scope="function")` 改为 `@pytest.fixture(scope="module")`，并在测试中对返回的 `result[0]["sentence_info"].append(...)` 做可变修改。
- **预测**：`function` 作用域下各测试互不影响；改为 `module` 后，后执行的测试会看到前一个测试追加的元素，导致用例间相互污染、偶发失败。
- **解释**：`module` 作用域在模块内复用同一对象，适合不可变或重型资源；对可变数据复用会破坏 hermetic 隔离。默认 `function` 是最安全的选择。

#### 改动并预测 实验 4：删去清洗步骤 → 预测文本断言失败

- **改什么**：在 `m2t/asr.py` 的 `_clean_text` 中注释掉 `re.sub(r'<\|[^|>]+\|>', '', text)` 一行，或直接让 `normalize_result` 不调用 `_clean_text`，再运行 `pytest answers/chapter05/test_chapter05.py -k test_clean`。
- **预测**：含 `<|zh|>` 标签或句首标点的用例失败，期望 `"你好"` 实际得到 `"<|zh|>你好"` 或 `"。，你好"`，断言提示文本不等。
- **解释**：清洗是归一化的一部分，FunASR 回包常带语言标签与首标点，遗漏清洗会污染下游 `store` 与 `export` 的展示。测试把清洗契约显式化，删清洗必被捕获。

## 习题

> 参考答案与测试在 `answers/chapter05/`，运行 `.venv/bin/pytest answers/chapter05/ -q` 验证。题目均为 hermetic 纯函数，不依赖网络或外部服务。核心题为第 1 题「杀死 bug」。

1. **杀死 bug（TDD 反向）**：`answers/chapter05/buggy_impl.py` 提供了一份故意带 bug 的 `normalize_result`（毫秒未转秒且 `spk` 1 基偏移遗漏）。为其编写测试 `test_kills_buggy`，使其在 buggy 上失败、在 `m2t.asr.normalize_result` 上通过。要求断言包含 `start/end` 与 `speaker`。
2. **参数化补全**：用 `@pytest.mark.parametrize` 为 `normalize_result` 的三种形状各补一个边界用例（共 ≥3 行参数），并演示「加一行参数→多一条用例」。
3. **fixture 复用**：为三种形状各写一个 `fixture`（`sentence_info_result` / `fallback_result` / `empty_result`），在测试中注入复用，验证 `len` 与字段完整性。
4. **异常与空输入断言**：对 `None`、`"not a list"`、`[{}]`、`{"text": None, "timestamp": None}` 等非法输入，写测试断言返回 `[]`（或用 `pytest.raises` 断言不抛异常而是优雅返回）。
5. **清洗与说话人标签**：针对 `_clean_text` 的标签 stripping 与句首标点 stripping，分别写测试；并验证 `spk` 缺失时 `speaker == ""`，`spk=0` 时为 `"说话人1"`（使用 `SPEAKER_LABEL_TEMPLATE`）。
6. *（附加）* 为 `normalize_result` 补一个「timestamp 非法项跳过」测试：`timestamp` 含 `"nope"`、`[0]` 等畸形项，验证仅合法 `len==2` 的项被保留。

## 延伸挑战

1. 把本章的 hermetic 单测扩展为集成测试：用一个 fake `model.generate` 返回上述三种形状，调用 `m2t.asr.transcribe`（注入 fake model）验证归一化仍通过，体会单元与集成的边界。
2. 为 `m2t.store` 的 `init_db` + `create_task` 写一个集成测试（`tmp_path` + sqlite），验证任务写入后可读，思考「为何此测试不能是 hermetic 单元测试」。
3. 在你的项目中选一个「时间单位转换」函数（如毫秒转秒、分转小时），先写失败测试再修复，记录「测试先行」相比「先写代码后补测试」在定位与回归上的收益。

