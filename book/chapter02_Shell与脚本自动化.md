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

# 第2章 Shell 与脚本自动化

> 为什么要学 Shell？因为「把重复操作变成一行命令」是工程师的第一层自动化。装环境、批量转写、跑测试、查日志——这些日常工作若每次都靠手点，慢且易错。本章以 MeetingToText 的批量音频处理为落点（`for f in *.wav; do meetingtotext transcribe "$f"; done`），串起 Shell 的核心工具：管道与重定向、文件查找与文本过滤（`find`/`grep`）、结构化处理（`awk`/`jq`）。学完本章，你能把「对一堆文件做同一件事」写成可复用的脚本，并用 Makefile 把常用命令固化为团队共识——正如 MeetingToText 根 `Makefile` 把 `install`/`test`/`lint` 等目标收敛为单一入口。

## 学习目标

完成本章后，你将能够：

1. 能解释管道（pipe）与重定向（redirect）的区别，并组合 `|`、`>`、`>>`、`2>&1` 完成「过滤—聚合—落盘」链路。
2. 能用 `find`、`grep`、`awk`、`jq` 在文件树与文本流中定位目标，并用 `glob` 通配与正则区分「文件名匹配 vs 内容匹配」。
3. 能编写 `for` 循环与最小可执行脚本，完成批量音频转写等「对一堆文件做同一件事」的自动化任务。
4. 能阅读 MeetingToText 根 `Makefile` 的目标划分（`install`/`test`/`lint`/`typecheck`/`format`/`build`/`docker-up`/`docker-down`/`help`），并为新项目新增一个自动化目标。

## 先修要求

- 完成 [第1章 环境与项目骨架](chapter01_环境与项目骨架.md)，已建好虚拟环境并能 `pip install -e .`。
- 会用 `cd` / `ls` / `cat` 基础命令；无需 Shell 脚本经验。

## 正文

### 2.1 Shell 是什么：从「敲命令」到「写脚本」

Shell（壳）是人与操作系统内核之间的命令解释器：你输入一行文本，它解析、执行、返回结果。常见的 Shell 有 `bash` / `zsh`，语法大同小异，本书统一用 `bash` 示意。

Shell 有两种使用形态：

- **交互式（interactive）**：在终端逐行输入，适合探索与调试。
- **脚本（script）**：把多行命令写入 `*.sh` 文件，用 `bash {脚本}` 或 `chmod +x` 后直接执行，适合固化与复用。

与 Python 的对照：Python 擅长「复杂逻辑 + 数据结构」，Shell 擅长「把现有程序像搭积木一样连起来」。两者分工而非替代——批量处理音频时，Shell 负责「遍历文件、调度命令」，`meetingtotext transcribe` 负责「重活（ASR）」。

最小脚本示例（示意片段）：

```bash
#!/usr/bin/env bash
set -euo pipefail
echo "hello from shell"
ls -lh {目录}
```

`set -euo pipefail` 是脚本的「安全带」：`e` 遇错即停、`u` 未定义变量即报错、`o pipefail` 管道中任一环节失败即视为整体失败。后续脚本均以此为默认头。

### 2.2 管道与重定向：让程序「连起来」

Shell 最核心的抽象是「一切皆文件描述符」：每个进程默认有 `stdin(0)` / `stdout(1)` / `stderr(2)` 三个流。重定向与管道就是在流之间「接管子」：

| 符号 | 含义 | 示例 |
|---|---|---|
| `>` | 重定向标准输出到文件（覆盖） | `echo hello > {输出文件}` |
| `>>` | 追加到文件 | `echo world >> {输出文件}` |
| `2>` / `2>&1` | 重定向标准错误；合并错误到输出 | `make test 2>&1 \| tee {日志}` |
| `\|` | 管道：左命令的 `stdout` 接右命令的 `stdin` | `cat {文件} \| grep ERROR \| wc -l` |
| `<` | 从文件读入标准输入 | `sort < {输入文件}` |

管道的威力在于「组合」——每个小工具只做一件事，管道把它們串成流水线：

```bash
# 统计某个目录下所有 .wav 文件按扩展名的分布（演示管道组合）
find {音频目录} -type f -name "*.wav" | sed 's/.*\.//' | sort | uniq -c | sort -rn

# 查日志中 ERROR 行并落盘，同时在终端可见
cat {日志文件} | grep "ERROR" | tee {错误摘录} | wc -l

# 批量转写的变体：先列文件，再逐行处理（xargs 串联）
find {音频目录} -name "*.wav" -print0 | xargs -0 -I {} bash -c 'meetingtotext transcribe "{}"'
```

> **何时用重定向/何时用管道？** 重定向连接「进程与文件」，管道连接「进程与进程」。需要落地就用 `>`，需要继续加工就用 `|`。

用 Python 镜像「管道」的思想（可运行）：

```{code-cell} ipython3
import pathlib, tempfile, os, glob, collections

# 建一个临时目录，模拟一批音频文件
tmpdir = tempfile.mkdtemp()
for name in ["a.wav", "b.wav", "c.mp3", "d.wav", "notes.txt"]:
    pathlib.Path(tmpdir, name).write_text("dummy")

# glob 通配 ≈ Shell 的 *.wav 展开
wav_files = sorted(glob.glob(os.path.join(tmpdir, "*.wav")))
print("glob *.wav:", [os.path.basename(p) for p in wav_files])

# 管道 sort | uniq -c 的 Python 等价：Counter 聚合
all_files = [os.path.basename(p) for p in glob.glob(os.path.join(tmpdir, "*"))]
exts = [p.rsplit(".", 1)[-1] if "." in p else "" for p in all_files]
counter = collections.Counter(exts)
print("按扩展名聚合（≈ sort | uniq -c）:", dict(counter))

# 过滤 ≈ grep
txt_like = [p for p in all_files if "note" in p]
print("grep 'note':", txt_like)
```

### 2.3 文件查找与文本过滤：find / grep

#### find：按「文件属性」找文件

`find` 在目录树中按条件筛选文件，常用谓词：

```bash
# 按名字（glob 模式，注意引号避免 Shell 提前展开）
find {项目根} -type f -name "*.wav"
find {项目根} -type f -name "*.py" | head -20

# 按时间与大小
find {项目根} -type f -mtime -7          # 7 天内修改过的
find {项目根} -type f -size +10M         # 大于 10MB

# 组合动作：找到后直接执行
find {音频目录} -name "*.wav" -exec ls -lh {} \;
find {音频目录} -name "*.wav" -exec meetingtotext transcribe {} \;
```

`find` 的输出是「每行一个路径」，常作为管道的起点，交由 `grep`/`awk`/`xargs` 进一步处理。

#### grep：按「文本内容」找行

`grep` 在文本流中按正则匹配行：

```bash
# 在项目中搜关键字（递归、显示行号、忽略大小写）
grep -rn "meetingtotext" {项目根} --include="*.py" --include="*.md"
grep -rin "error" {日志目录}

# 只列文件名 / 统计命中数 / 反选
grep -rl "TODO" {项目根}
grep -c "ERROR" {日志文件}
grep -v "DEBUG" {日志文件} | head

# 用正则精确定位
grep -E "transcribe.*\.wav" {脚本文件}
```

> **区分**：`find -name "*.wav"` 匹配「文件名」，`grep -r "wav"` 匹配「文件内容」。两者常管道组合：`find … -name "*.py" | xargs grep -l "transcribe"`——先定范围，再搜内容。

### 2.4 结构化处理：awk / jq

当文本有「列」或「JSON 结构」时，`awk` 与 `jq` 比 `grep` 更合适。

#### awk：按列处理

`awk` 把每行按分隔符切成 `$1, $2, …` 列（默认空白分隔）：

```bash
# 打印第 2 列（示例：ps 输出的 CPU 占用）
ps aux | awk '{print $2, $11}' | head

# 按条件过滤并重排
cat {转写结果.csv} | awk -F, '$3 > 30 {print $1, $2, $3}'

# 统计：类似 Python 的 Counter
find {音频目录} -type f | awk -F. '{print $NF}' | sort | uniq -c | sort -rn
```

#### jq：处理 JSON

`jq` 是 JSON 的 `grep+awk`：

```bash
# 提取字段
cat {任务列表.json} | jq '.[].id'
cat {任务列表.json} | jq '.[] | select(.status=="done") | .id'

# 重塑输出
cat {任务列表.json} | jq -r '.[] | "\(.id) \(.status)"'
```

三者分工速记：`grep` 定行、`awk` 定列、`jq` 定 JSON 路径。遇到结构化日志（JSON Lines）时，`jq` 几乎是必选。

### 2.5 应用：批量处理音频

本章的应用落点是「把目录里的一堆音频批量转写」。最直接的写法就是任务要求中的一行循环：

```bash
# 批量转写当前目录下所有 wav（示意，{音频目录} 需替换）
for f in {音频目录}/*.wav; do
  echo "transcribing $f ..."
  meetingtotext transcribe "$f"
done
```

进一步自动化时，有三类常见增强：

**1. 用 Makefile 固化命令**（参考 MeetingToText 根 `Makefile`）：

MeetingToText 的 `Makefile` 把常用操作收敛为 `make {目标}`，分组为「安装/运行/质量门/打包部署/帮助」五组，目标包括 `install`（装后端与前端依赖）、`test`/`test-system`（常规/系统测试）、`lint`（`ruff check` + `eslint`）、`typecheck`（`mypy` + `vue-tsc`）、`format`（`ruff format` + `prettier`）、`build`（前端构建）、`docker-up`/`docker-down`（容器启停）、`help`（列目标）。关键细节：`lint`/`typecheck`/`format` 用 `;` 串联前后端两段检查（两段都跑并汇总结果），而 `install`/`build` 用 `&&`（前一步失败则不继续）。

为批量转写新增一个目标（示意）：

```bash
# 在 Makefile 末尾新增（示意片段，占位符需替换）
transcribe-all: ## 批量转写 {音频目录} 下的 wav
	for f in {音频目录}/*.wav; do meetingtotext transcribe "$$f"; done

help: ## 列出可用目标（已在 MeetingToText Makefile 中实现）
	@awk '/^[a-zA-Z_-]+:/{ if ($$2 == "##") { name=$$1; sub(/:$$/, "", name); desc=substr($$0, index($$0, "##")+3); printf "  %-14s %s\n", name, desc } }' $(MAKEFILE_LIST)
```

之后只需 `make transcribe-all`，无需记忆长命令。

**2. 参数化与健壮性**：

```bash
#!/usr/bin/env bash
set -euo pipefail
AUDIO_DIR="{音频目录}"
OUT_DIR="{输出目录}"
mkdir -p "$OUT_DIR"
for f in "$AUDIO_DIR"/*.wav; do
  # 处理空 glob（无匹配时 for 会得到字面量 "*.wav"）
  [ -e "$f" ] || continue
  base=$(basename "$f" .wav)
  meetingtotext transcribe "$f" > "$OUT_DIR/$base.txt" 2>&1
  echo "done: $f -> $OUT_DIR/$base.txt"
done
```

**3. 可观测性**：把 `stdout`/`stderr` 分流到日志并在终端可见：

```bash
for f in {音频目录}/*.wav; do
  meetingtotext transcribe "$f" 2>&1 | tee -a {日志文件}
done
```

用 Python 镜像「批量处理」的核心逻辑（可运行，含 `glob` + 过滤 + 排序 + 命令拼接）：

```{code-cell} ipython3
import glob as globlib
import os, pathlib, tempfile, shlex

# 复用 2.2 的临时目录，再补几个文件
tmpdir2 = tempfile.mkdtemp()
for name in ["talk1.wav", "talk2.wav", "music.mp3", "empty.wav"]:
    pathlib.Path(tmpdir2, name).write_text("fake audio")

def glob_audio_files(directory: str, pattern: str = "*.wav") -> list[str]:
    """Shell glob 的 Python 镜像：返回排序后的匹配路径。"""
    return sorted(globlib.glob(os.path.join(directory, pattern)))

def filter_by_ext(paths: list[str], ext: str) -> list[str]:
    """按扩展名过滤（ext 可带或不带点）。"""
    ext = ext if ext.startswith(".") else f".{ext}"
    ext = ext.lower()
    return [p for p in paths if p.lower().endswith(ext)]

def build_transcribe_commands(wav_files: list[str]) -> list[str]:
    """为每个 wav 拼出 meetingtotext 命令（安全引号）。"""
    return [f"meetingtotext transcribe {shlex.quote(f)}" for f in wav_files]

wavs = glob_audio_files(tmpdir2, "*.wav")
print("wavs:", [os.path.basename(p) for p in wavs])
print("filter .wav:", [os.path.basename(p) for p in filter_by_ext(wavs, ".wav")])
# 管道 sort | uniq -c 的聚合思想：按扩展名计数
from collections import Counter
all_paths = globlib.glob(os.path.join(tmpdir2, "*"))
ext_counter = Counter(os.path.splitext(p)[1].lower() for p in all_paths)
print("ext Counter:", dict(ext_counter))
print("commands:", build_transcribe_commands(wavs)[:2])
```

### 改动并预测

以下实验均可在本机 Shell 或本章 `{code-cell}` 中复现。按「改什么 → 预测 → 解释」三段式书写。

#### 改动并预测 实验 1：改 `glob` 模式 `*.wav` → `*.mp3` → 预测命中数变化

- **改什么**：把批量脚本中的 `for f in {音频目录}/*.wav` 改为 `for f in {音频目录}/*.mp3`，或在 Python 中把 `glob_audio_files(tmpdir2, "*.wav")` 改为 `glob_audio_files(tmpdir2, "*.mp3")`。
- **预测**：命中数从 `2`（`talk1.wav`/`talk2.wav`/`empty.wav` 视目录而定）变为 `1`（`music.mp3`），Python 返回列表长度相应变化；若目录无 `*.mp3`，Shell 的 `for` 会得到字面量 `*.mp3`（需 `[ -e "$f" ] || continue` 防御），Python 则返回空列表 `[]`。
- **解释**：`glob` 是「文件名模式匹配」，`*` 匹配任意字符但不跨目录，扩展名不同即不同集合。Shell 与 `glob.glob` 语义一致，区别在于「无匹配时的行为」——Shell 保留字面量，Python 返回空列表，脚本需分别处理。

#### 改动并预测 实验 2：管道里加 `sort | uniq -c` → 预测聚合效果

- **改什么**：在 `find {音频目录} -type f | awk -F. '{print $NF}'` 后追加 `| sort | uniq -c | sort -rn`，或在 Python 中把 `ext_counter = Counter(...)` 后的输出改为 `counter.most_common()` 排序。
- **预测**：原本每行一个扩展名（如 `wav` 重复多行），追加后变为「计数 + 扩展名」的聚合表（如 `3 wav` / `1 mp3`），并按计数降序排列；Python 侧 `most_common()` 同样给出降序列表。
- **解释**：`sort` 将相同扩展名聚到一起，`uniq -c` 统计连续相同行的出现次数，二者组合实现「分组计数」。`sort -rn` 再按计数数值反向排序，等价于 Python `Counter.most_common()`。去掉 `sort` 则 `uniq -c` 只能对相邻重复计数，结果错误——这正是「管道顺序」的重要性。

#### 改动并预测 实验 3：`grep` 加 `-v` 反选 → 预测输出翻转

- **改什么**：把 `grep "ERROR" {日志文件}` 改为 `grep -v "ERROR" {日志文件}`，或在 Python 中把 `[p for p in lines if "ERROR" in p]` 改为 `[p for p in lines if "ERROR" not in p]`。
- **预测**：原本只输出含 `ERROR` 的行，改后输出「除 `ERROR` 外的所有行」；行数从「少数」变为「多数」，两者之和等于总行数（无重叠、无遗漏）。
- **解释**：`-v` 是 `grep` 的反选（invert-match）开关，将匹配谓词取反。与之等价的还有 `awk '!/ERROR/'`。该实验验证「过滤条件是否可逆」——正选与反选互补，管道中常用 `grep -v "DEBUG"` 去噪后再统计。

#### 改动并预测 实验 4：重定向 `>` 改 `>>` → 预测文件是覆盖还是追加

- **改什么**：把批量脚本中的 `meetingtotext transcribe "$f" > "$OUT_DIR/$base.txt"` 改为 `>> "$OUT_DIR/$base.txt"`，连续对同一文件执行两次。
- **预测**：用 `>` 时第二次执行会覆盖第一次的内容，文件大小约等于单次输出；用 `>>` 时第二次会在文件末尾追加，文件大小近似翻倍（可用 `wc -c` 验证）。
- **解释**：`>` 以 `O_TRUNC` 打开文件（先清空），`>>` 以 `O_APPEND` 打开（定位到末尾）。日志场景常需 `>>` 追加，而结果文件常需 `>` 覆盖——选错会导致「日志被截断」或「结果被污染」。`2>&1 | tee -a` 则是「既落盘又可见」的追加变体。

## 习题

> 参考答案与测试在 `answers/chapter02/`，运行 `pytest answers/chapter02/ -q` 验证。题目均为 hermetic 纯函数，不依赖网络或外部服务。

1. **通配列文件**：实现 `glob_audio_files(directory: str, pattern: str = "*.wav") -> list[str]`，返回按字典序排序的匹配路径；目录不存在返回 `[]`。
2. **按扩展名过滤**：实现 `filter_by_ext(paths: list[str], ext: str) -> list[str]`，`ext` 可带或不带点，大小写不敏感。
3. **解析 find 输出**：实现 `parse_find_output(lines: list[str]) -> list[str]`，对 `find` 的每行输出做 `strip`、去空行、去重后按字典序返回。
4. **扩展名计数（uniq -c 镜像）**：实现 `count_by_extension(paths: list[str]) -> dict[str, str]` 的变体 `count_by_extension(paths) -> dict`，返回 `{".wav": 3, ".mp3": 1}`（小写归一，无扩展名记 `""`）。
5. **拼转写命令**：实现 `build_transcribe_commands(wav_files: list[str], out_dir: str | None = None) -> list[str]`，为每个文件生成 `meetingtotext transcribe {quoted}` 命令；若 `out_dir` 非空则追加 `> {out_dir}/{base}.txt` 重定向（安全引号）。
6. *（附加）* **类 jq 提取**：实现 `jq_extract(records: list[dict], key: str) -> list`，从每条 `dict` 中提取 `key` 对应的值，缺失则跳过；`key` 支持点号路径如 `"a.b"`。

## 延伸挑战

1. 为本书仓库写一个 `Makefile` 目标 `transcribe-all`，支持 `AUDIO_DIR={目录} make transcribe-all` 覆盖默认目录，并在 `help` 中可见（含 `##` 注释）。
2. 用 `find {目录} -name "*.wav" -print0 | xargs -0 -P 2 -I {} bash -c '...'` 尝试并行批量处理，对比串行 `for` 循环的日志顺序差异，思考何时需要 `-P` 并行、何时必须串行。
3. 构造一个含空格与特殊字符的文件名（如 `my talk (1).wav`），验证 `for f in *.wav; do meetingtotext transcribe "$f"; done` 加引号与不加引号的区别；再用 Python `shlex.quote` 观察安全引号的效果。
