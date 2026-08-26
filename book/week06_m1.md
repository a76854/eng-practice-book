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

# 里程碑 M1：CLI 转写工具

> 从零散脚本到可交付工具的跨越——本周把前 5 周的 Shell、Git、类型与测试能力收敛为一个可被黑盒评测的命令行转写工具。工具不实现 ASR 本体，而是复用 `m2t` 子包并以确定性 fake 模型离线完成转写与导出，完整链路可在 `pytest` 与 `jupyter-book --execute` 下复现。

## 学习目标

完成本里程碑后，你将能够：

1. 能用 `argparse` 子命令实现 `transcribe` 的参数解析与中文错误退出，并解释 `choices` 与手动校验的权衡。
2. 能复用 `m2t.asr.transcribe(model=fake)` + `m2t.export.export(task, fmt)` 完成 hermetic 转写与多格式导出，不触 `funasr/torch`。
3. 能按 `milestones/m1_cli/README.md` 的提交结构组织 `student_solution/cli.py`、`tests/` 与 `reference_solution/`。
4. 能用 `milestones/grader.py:run_grader` 自检并通过三分支双反向验证，读懂黑盒测试只断言退出码与文件内容。
5. 能在答辩中演示 `txt/srt/md` 导出差异并回答状态码与路径创建的实现抉择。

## 先修要求

- 已完成周 1–5（环境、Shell、Git、类型检查、pytest hermetic 测试）。
- 会执行 `.venv/bin/pytest -q` 与 `jupyter-book build --execute`，理解 `m2t` 为只读教学包。
- 已阅读 `milestones/m1_cli/README.md` 与 `milestones/grader.py` 的目录约定。

## 1. 里程碑目标

M1 的交付物是一个最小可用的 CLI 转写工具（示例名 `m2tc`）：给定一个音频文件路径，经 `m2t` 转写后按 `--format txt|srt|md` 写出结果文件。**不实现 ASR 本体，走 `m2t` mock**——真实环境下 `m2t.asr.transcribe` 懒加载 FunASR；教学与评测环境全程 hermetic，不安装 `funasr/torch`，不访问网络/真实模型。CLI 通过注入**确定性 fake 模型**（实现 `generate(input, ...)` 返回固定 `sentence_info`）完成转写，再复用 `m2t.export` 导出，满足 `grep -c "不实现 ASR 本体\|mock\|fake" milestones/m1_cli/README.md ≥1` 的声明门控。

详细任务定义以 [`milestones/m1_cli/README.md`](../milestones/m1_cli/README.md) 为权威，本文仅作摘要与教学导读。

## 2. 任务说明（摘要）

### 命令行接口

```bash
# 默认 txt，输出到 <stem>.txt
python -m cli transcribe path/to/audio.wav

# 指定格式
python -m cli transcribe path/to/audio.wav --format srt
python -m cli transcribe path/to/audio.wav --format md

# 指定输出路径（父目录自动创建）
python -m cli transcribe path/to/audio.wav --format txt --out /tmp/result.txt
python -m cli transcribe path/to/audio.wav --format srt --out /tmp/subdir/out.srt

# 教学 stub（可选）：显式走 fake；未传时也默认 fake，保证 hermetic
python -m cli transcribe path/to/audio.wav --stub
```

参数表：`audio`（positional 必填）、`--format {txt,srt,md}` 默认 `txt`、非法值非零退出且 `stderr` 含 `错误`、`--out <path>` 默认 `<stem>.<format>` 且父目录 `os.makedirs(exist_ok=True)`、`--stub` flag 可选。输入约束：支持扩展名 `.wav .mp3 .m4a .flac .ogg .webm` 子集（至少 `.wav`）；坏扩展、缺失文件、非法格式均非零退出 + 中文报错。

### 输出语义

- `txt`：`m2t.export` 的 `_export_txt`——每段一行 `[说话人] 文本`，`\n` 连接。
- `srt`：`_export_srt`——序号 / `00:00:00,000 --> 00:00:01,200` / `[说话人] 文本` 块，块间空行。
- `md`：`_export_md`——`# 会议转录 — <filename>` 标题、时长引用块与段落。

思路对齐 `MeetingToText/cli.py:_cmd_transcribe`（只读参考，不逐字复制）：校验存在性与扩展名 → 解析输出路径与有效格式 → `m2t.asr.transcribe(model=fake)` + `m2t.export.export(task, fmt)` → 原子写文件（UTF-8）→ 打印 `转录完成 → <path>`。错误一律 `print("错误: ...", file=sys.stderr); sys.exit(1)`。

## 3. 提交结构

```
milestones/m1_cli/
  README.md               # 任务说明（只读）
  reference_solution/
    cli.py                # 教师参考解（argparse 子命令 + main(argv)）
  student_solution/
    cli.py                # 学生提交（被测对象；grader 默认测此目录）
  tests/
    conftest.py           # 保证直接 pytest 也能找到 cli
    test_cli.py           # 黑盒测试（唯一判分依据）
```

`reference_solution/cli.py` 与 `student_solution/cli.py` 同接口：

```python
def build_parser() -> argparse.ArgumentParser: ...
def main(argv: list[str] | None = None) -> None: ...
if __name__ == "__main__":
    main()
```

`conftest.py` 在 grader 外的直接 `pytest` 场景下回退到 `reference_solution`；`grader` 另行注入 `PYTHONPATH` 指向被测目录。

## 4. 评测（黑盒 + grader 约定）

唯一判分引擎为 `pytest`，由 [`milestones/grader.py`](../milestones/grader.py) 的 `run_grader` 封装：

```bash
# 测学生提交（默认）
python -m milestones.grader milestones/m1_cli
# 自检参考解
python -m milestones.grader milestones/m1_cli --solution reference_solution
# 直接 pytest（hermetic）
.venv/bin/pytest milestones/m1_cli/tests -q
```

测试只断言可观测行为（退出码、`stdout/stderr`、产出文件内容），不窥探内部变量，覆盖 ≥6 用例：合法 wav→txt 正确、srt 含 ` --> `、md 含标题、`--out` 生效、坏扩展/缺失文件/非法格式三条中文错误，以及 `funasr/torch` 未加载的 hermetic 保障（`test_no_real_asr_import_at_runtime`）。`milestones/grader.py:run_grader` 将 `solution_dir` 置于 `PYTHONPATH` 首位，使 `tests/test_cli.py` 的 `import cli` 解析到被测实现。

### 双反向验证

`milestones/m1_cli/verify_reverse.sh` 三分支对齐 `grader_selfcheck.sh` 思想：(a) 好解→PASS (b) buggy 实现→FAIL (c) 学生测试× buggy →FAIL，产出 `evidence/task-11-m1.txt`，保证测试非空心。

## 5. 评分 rubric 要点

周 6 教师指南 rubric（见 `teacher_guide.md` 周 6）：功能正确性 40%（`pytest tests/ -q` 全绿，grader 通过）、代码质量 20%（`ruff check` 0 告警）、测试覆盖 20%（≥5 用例，覆盖正常/异常/边界）、可读性 10%（函数级 docstring）、双反向验证 10%（`grader_selfcheck.sh` 三分支通过）。评审时重点看：是否通过 `m2t` 复用而非直调 FunASR、错误分支是否中文且 `stderr` 可断言、输出文件是否 UTF-8 与目录自动创建。

## 6. 答辩提示

- 演示脚本：准备一个 `sample.wav`（任意占位文件，fake 不读内容）现场跑三条命令（`txt/srt/md`）并 `cat` 输出，突出 `srt` 的时间戳与 `md` 的标题差异。
- 必答问题准备：为何 `--format` 要手动校验而非仅依赖 `choices`？`--out` 父目录不存在时为何要 `exist_ok=True`？如何证明测试未加载 `funasr`？
- 自检清单：`python -m milestones.grader milestones/m1_cli --solution reference_solution` 是否 PASS？`--out` 嵌套路径是否自动创建？`stderr` 中文是否含 `错误`？

## 自测实验（改动并预测）

#### 实验 1：把 `--format` 改回 `choices` 自动校验 → 预测中文报错消失

- **改什么**：将手动 `if fmt not in ("txt","srt","md"): print("错误: 不支持的格式", file=sys.stderr); sys.exit(1)` 改为 `parser.add_argument("--format", choices=["txt","srt","md"])`。
- **预测**：非法 `--format pdf` 时 `argparse` 直接以 `invalid choice` 英文退出，`test_invalid_format_exits_nonzero_and_chinese` 因断言 `不支持的格式` 而失败。
- **解释**：手动校验保留中文错误文案的教学意图，与 `choices` 的英文提示冲突；黑盒测试钉住文案即钉住用户体验。

#### 实验 2：删掉 `os.makedirs` → 预测嵌套 `--out` 失败

- **改什么**：注释掉 `os.makedirs(os.path.dirname(out_path), exist_ok=True)`。
- **预测**：`test_out_option_honored` 在 `nested/out/custom.txt` 上抛 `FileNotFoundError`，非零退出但错误文案非预期。
- **解释**：输出路径的父目录自动创建是 CLI 的可用性契约，测试以嵌套路径固化该契约。

#### 实验 3：让测试导入 `funasr` → 预测 hermetic 保障失败

- **改什么**：在 `cli.py` 顶层加 `import funasr`（即使未使用）。
- **预测**：`test_no_real_asr_import_at_runtime` 断言 `funasr not in sys.modules` 失败。
- **解释**：hermetic 要求 `m2t` 仅依赖 `numpy/soundfile`，`funasr` 必须懒导入；顶层导入破坏离线可测。

```{code-cell} ipython3
# M1 自检：hermetic 导入与导出格式冒烟（不触真实 ASR）
from m2t.asr import normalize_result
fake_raw = [{"sentence_info": [{"text": "你好", "start": 0, "end": 1000, "spk": 0}]}]
segs = normalize_result(fake_raw)
assert segs[0]["speaker"] == "说话人1" and segs[0]["text"] == "你好"
print("M1 hermetic 冒烟通过 — fake sentence_info 已归一，m2t.export 可据此导出 txt/srt/md")
```

## 习题

> 参考答案与测试在 `answers/` 各周目录；里程碑习题即 `milestones/m1_cli/tests/` 的黑盒用例，需保证 hermetic。

1. 为 `build_parser` 补一个 `test_build_parser_has_transcribe_subcommand`，断言 `transcribe` 子命令存在且含 `--format/--out/--stub`。
2. 写一个边界测试：`audio` 为目录路径 `tmp_path / "a.wav".mkdir()` 时是否非零退出且含 `错误`？
3. 用 `@pytest.mark.parametrize` 把三种格式的导出断言参数化为一张表（`fmt → expected_substring`），演示加一行即多一条用例。
4. 为 `main` 写一个 `capfd` 测试，验证成功时 `stdout` 含 `转录完成` 且文件已落盘。
5. 复盘本章 rubric：若你的实现 `ruff check` 报 1 条 `E501`，按 20% 权重会如何扣分？如何在不改语义下换行消除？

## 延伸挑战

1. 支持多文件批量：`python -m cli transcribe a.wav b.wav --format srt --out out_dir/` 时批量导出并保持 `pending→done` 的串行语义。
2. 为 CLI 增加 `--json` 结构化输出（`{"task_id","status","output_path"}`），便于被 `jq` 消费。
3. 用 `pytest` + `subprocess` 写一条系统级测试，真实启动子进程 `python -m cli` 并断言文件落盘（体会单元与系统测试的边界）。

> 本章内容原创，概念对应 MeetingToText 的 `cli.py:_cmd_transcribe` 与 `m2t.asr`/`m2t.export` 的复用链路，任务结构与 grader 约定对应 `milestones/m1_cli/README.md` 与 `milestones/grader.py`，习题与表述均为原创。
