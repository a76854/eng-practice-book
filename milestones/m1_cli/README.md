# 里程碑 M1：CLI 转写工具（第6章）

> 对应章节：`chapter06_里程碑M1_CLI转写工具.md`（CLI 与工程化章）  
> 前置能力：Shell、argparse、文件 I/O、`import m2t` 基础

## 1. 任务说明

实现一个命令行工具（示例名 `m2tc`）——读取一个音频文件路径，经 `m2t` 转写，输出到 `txt / srt / md` 三种格式中的一种。

**不实现 ASR 本体，走 `m2t.asr`（教学环境用 mock / fake 模型）**。真实环境下 `m2t.asr.transcribe` 懒加载 FunASR；教学与评测环境**全程 hermetic**，不安装 `funasr / torch`，不访问网络/真实模型。CLI 必须通过注入**确定性 fake 模型**（或接受 `--stub` 开关）完成转写，返回固定段结构，再复用 `m2t.export` 导出。禁止在测试时导入 `funasr`、`torch`。

### 命令行接口

```bash
# 基础：默认 txt，输出到 <stem>.txt
python -m cli transcribe path/to/audio.wav

# 指定格式
python -m cli transcribe path/to/audio.wav --format srt
python -m cli transcribe path/to/audio.wav --format md

# 指定输出路径（覆盖默认 <stem>.<ext> 规则）
python -m cli transcribe path/to/audio.wav --format txt --out /tmp/result.txt
python -m cli transcribe path/to/audio.wav --format srt --out /tmp/subdir/out.srt

# 教学 stub（可选）：显式走 fake 模型；未传时也默认 fake，保证 hermetic
python -m cli transcribe path/to/audio.wav --stub
```

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `audio` | positional `str` | 必填 | 音频文件路径（单文件） |
| `--format` | `{txt,srt,md}` | `txt` | 输出格式；非法值 → 非零退出 + 中文报错 |
| `--out` | `str` | `<stem>.<format>` | 输出文件路径；父目录不存在时自动创建 |
| `--stub` | flag | `false` |（可选）强制使用内置 fake 模型；默认即 fake，保证离线可测 |

### 输入约束

- 支持的音频扩展名：`.wav .mp3 .m4a .flac .ogg .webm`（与 MeetingToText `ALLOWED_EXTENSIONS` 子集对齐；至少包含 `.wav`）
- 坏扩展 / 缺失文件 / 非法 `--format` → **非零退出码 + 中文报错**（`stderr` 含 `错误` 字样）
- 仅实现单文件转写即可；多文件为加分项，非必需

### 输出

- `txt`：`m2t.export` 的 `_export_txt` 语义 —— 每段一行，`[说话人] 文本`（无说话人则裸文本），`\n` 连接
- `srt`：`_export_srt` 语义 —— `序号 / 00:00:00,000 --> 00:00:01,200 / [说话人] 文本` 块，块间空行
- `md`：`_export_md` 语义 —— `# 会议转录 — <filename>` 标题、时长引用块、二级标题段

所有写入均为 UTF-8。

## 2. 提交结构

```
milestones/m1_cli/
  README.md               # 本文件（任务说明，对学生只读）
  reference_solution/
    cli.py                # 教师参考解（argparse 子命令 + main(argv)）
  student_solution/
    cli.py                # 学生提交（被测对象；grader 默认测此目录）
  tests/
    conftest.py           # 保证直接 pytest 也能找到 cli（grader 另行注入 PYTHONPATH）
    test_cli.py           # 黑盒测试（唯一判分依据）
```

`reference_solution/cli.py` 与 `student_solution/cli.py` **同接口**：

```python
def build_parser() -> argparse.ArgumentParser: ...
def main(argv: list[str] | None = None) -> None: ...
if __name__ == "__main__":
    main()
```

## 3. 评测（黑盒）

唯一判分引擎：`pytest`（`milestones/grader.py:run_grader` 封装）。测试**只断言可观测行为**：退出码、`stdout/stderr`、产出文件内容；不窥探内部变量。

```bash
# 测学生提交（默认）
python -m milestones.grader milestones/m1_cli
# 自检参考解
python -m milestones.grader milestones/m1_cli --solution reference_solution
# 直接 pytest（hermetic，无需 PYTHONPATH 手动设置，conftest 会回退到 reference）
.venv/bin/pytest milestones/m1_cli/tests -q
```

测试覆盖（≥6 用例，hermetic，无 funasr/torch/网络/真实模型）：

1. 合法 `wav` → 写出 `txt` 且内容正确（fake 固定输出）
2. `--format srt` → 写出 `.srt` 且含 ` --> ` 时间戳与说话人
3. `--format md` → 含 Markdown 标题与段
4. `--out` 生效（自定义路径，父目录自动创建）
5. 坏扩展（`.xyz`）→ 非零退出 + 中文「错误 / 不支持的文件格式」
6. 缺失文件 → 非零退出 + 中文「错误 / 不存在」
7. 非法 `--format` 值 → 非零退出 + 中文「错误 / 不支持的格式」

### fake 模型

参考解注入**确定性 fake 模型**（实现 `generate(input, ...)` 返回固定形状），经 `m2t.asr.transcribe(model=fake)` 归一后得到固定 `[{speaker, text, start, end}]`，再 `m2t.export.export(task, fmt)` 导出。固定形状覆盖 `m2t.asr.normalize_result` 的三种形状之至少一种（本参考解覆盖形状 1 `sentence_info`）。

### 双反向验证

`milestones/grader_selfcheck.sh` 的三分支思想同样适用于本里程碑：

- (a) 好解（`reference_solution`）→ `tests` PASS
- (b) 故意 buggy 的实现 → `tests` FAIL（`grader` 报告 FAIL）
- (c) 学生自带测试（若有）× buggy 实现 → FAIL（证明测试非空心）

本目录提供 `verify_reverse.sh` 可执行验证并产出 `evidence/task-11-m1.txt`。

## 4. 实现提示

- 思路对齐 `MeetingToText/cli.py:_cmd_transcribe`（只读参考，**不逐字复制**，教学精简版）：校验存在性与扩展名 → 解析输出路径与有效格式 → `create_task`/`run_pipeline` 的简化版即 `m2t.asr.transcribe` + `m2t.export` → 原子写文件 → 打印 `转录完成 → <path>`。
- 错误一律 `print("错误: ...", file=sys.stderr); sys.exit(1)`，让 `argparse` 非法参数也落到中文分支（手动校验 `--format` 而非仅依赖 `choices`）。
- 保持 `import m2t` 可成功（`m2t` 仅依赖 `numpy/soundfile`），`funasr` 懒导入永不触发。
- 满足 `grep -c "不实现 ASR 本体\|mock\|fake" milestones/m1_cli/README.md` ≥1 的声明门控。

## 5. 常见问题

- **需要训练/下载模型吗？** 不需要。`--stub` / 默认 fake 已满足评测；真实 `m2t.asr` 仅在非教学环境按需加载。
- **如何本地自测？** `.venv/bin/pytest milestones/m1_cli/tests -q` 或 `python -m milestones.grader milestones/m1_cli --solution reference_solution`。
- **并发安全？** 无共享状态；`verify_reverse.sh` 的 buggy 夹具在 `/tmp` 隔离。
