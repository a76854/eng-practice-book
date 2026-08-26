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

# 周9 调试与性能剖析

> 为什么要把调试与性能剖析放在一起？前几周你已经能写 HTTP 服务、持久化任务、调用 ASR/LLM——但当转写变慢、日志刷屏看不出问题、接口返回 500 却不知哪一行触发时，仅靠“多打几个 print”会越调越乱。日志（logging）是“事后可查的现场记录”，断点（breakpoint）是“暂停现场的显微镜”，而性能剖析（profiling）是“给程序计时的秒表”。本章先把日志的分级、落盘与轮转配好，再用断点定位逻辑错误，最后用 `cProfile` 找到转写流水线的真正热点——三者配合，才能从“能跑”迈向“可维护、可变快”。

## 学习目标

完成本章后，你将能够：

1. 能解释 `DEBUG/INFO/WARNING/ERROR/CRITICAL` 五级日志的语义与过滤规则，并预测改动 `level` 后的可见性变化。
2. 能用 `logging.basicConfig` 完成快速配置，并用 `logging.config.dictConfig`（含 `RotatingFileHandler`）编写可落盘、可轮转的生产级日志配置，对照 MeetingToText 的 `backend/app/logging_config.py` 说明落盘路径与多 worker 隔离。
3. 能在代码中插入 `breakpoint()` 进入 `pdb` 调试会话，完成单步、查看变量、继续/退出的最小调试闭环。
4. 能用 `python -m cProfile` 与 `cProfile.Profile()` + `pstats` 两种方式剖析程序，读懂 `ncalls/tottime/cumtime` 表并用 `sort_stats` 定位热点。

## 先修要求

- 完成 [周1 环境与项目骨架](week01_环境与项目骨架.md)与 [周5 测试的思维与工程](week05_测试的思维与工程.md)（会在 `.venv` 中 `pytest` 与 `tempfile`）。
- 会用 `m2t.export` / `m2t.store` 的基本调用（本章热点示例用 mock 流水线模拟，不依赖真实 ASR 模型）。
- 已阅读 MeetingToText `cli.py` 的 `--log-level/--log-file` 两个选项的帮助信息（只读参考，不需运行模型）。

## 正文

### 9.1 日志的本质：分级与过滤

日志不是 `print` 的别名，而是“带级别、带去向、可过滤的结构化记录”。Python `logging` 定义了五级（数值越大越严重）：

| 级别 | 数值 | 语义 | 何时用 |
|---|---|---|---|
| `DEBUG` | 10 | 调试细节 | 循环内变量、分支进入 |
| `INFO` | 20 | 正常进展 | 任务创建、转写完成 |
| `WARNING` | 30 | 可恢复的异常 | 重试、降级 |
| `ERROR` | 40 | 需关注的失败 | 转写失败、导出失败 |
| `CRITICAL` | 50 | 致命 | 进程无法继续 |

过滤规则只有一条：**“低于阈值的记录被丢弃，高于等于阈值的放行”**。阈值由 `logger` 与 `handler` 各自的 `level` 共同决定（取更严格者）。例如 `logger.level=INFO` 时，`DEBUG` 被丢弃，`INFO` 及以上放行；改为 `ERROR` 后，连 `INFO` 也消失。

最小演示——用 `basicConfig` 快速配置控制台输出（`force=True` 保证在 Jupyter 重复执行时也能重置）：

```{code-cell} ipython3
import logging

# 演示：basicConfig 一行配好控制台日志（真实项目用 dictConfig，见 9.2）
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s", force=True)
logger = logging.getLogger("week09.demo")
logger.setLevel(logging.INFO)

logger.debug("这条 DEBUG 不可见（低于 INFO）")
logger.info("转写任务 demo123 已创建")
logger.warning("ASR 重试 1/3")
logger.error("转写失败：音频为空")
print("—— 阈值 INFO 时，DEBUG 被过滤，INFO 及以上可见 ——")
```

把阈值改成 `WARNING` 后，`INFO` 也会消失——这正是下一节要验证的“级别即过滤器”。

### 9.2 配置日志：basicConfig 与 dictConfig

`basicConfig` 适合脚本与演示：一次调用配好 `root` logger 与 `StreamHandler`。参数常用：

```python
logging.basicConfig(
    level=logging.INFO,              # 阈值
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,                      # 已有配置时强制覆盖（Jupyter 必加）
)
```

生产服务需要更细的控制：同时输出到控制台与文件、不同 logger 不同级别、轮转等——这时用 `dictConfig`（字典即配置）。MeetingToText 的 `backend/app/logging_config.py` 就是典型 `dictConfig`（只读参考）：顶层 `version/disable_existing_loggers/formatters/handlers/root/loggers`，`handlers` 中同时声明 `console`（`StreamHandler`）与 `rotating_file`（`RotatingFileHandler`），`root` 与 `uvicorn.*` 三个 logger 复用同一组 handler，`level` 由 `cli.py --log-level` 传入（默认 `INFO`，可选 `DEBUG/INFO/WARNING/ERROR`）。

对照其 `build_log_config(level, log_file, console=True, pid=None)` 的形状，简化版如下（与真实实现一致的键名，可直接 `dictConfig`）：

```{code-cell} ipython3
import logging.config
import tempfile
import os

def build_demo_config(level: str, log_file: str | None):
    lvl = level.upper()
    if lvl not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        lvl = "INFO"
    handlers: dict = {}
    names: list[str] = []
    # 控制台
    handlers["console"] = {
        "class": "logging.StreamHandler",
        "level": lvl,
        "formatter": "readable",
        "stream": "ext://sys.stderr",
    }
    names.append("console")
    # 文件（可选）
    if log_file is not None:
        handlers["rotating_file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": lvl,
            "formatter": "readable",
            "filename": log_file,
            "maxBytes": 10 * 1024,
            "backupCount": 3,
            "encoding": "utf-8",
        }
        names.append("rotating_file")
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"readable": {"format": "%(asctime)s %(name)s %(levelname)s %(message)s", "datefmt": "%Y-%m-%d %H:%M:%S"}},
        "handlers": handlers,
        "root": {"level": lvl, "handlers": names},
    }

# 演示：dictConfig 同时配控制台与文件（文件落在临时目录，不污染仓库）
tmpdir = tempfile.mkdtemp()
demo_log = os.path.join(tmpdir, "demo.log")
config = build_demo_config("INFO", demo_log)
logging.config.dictConfig(config)
log = logging.getLogger("week09.dict_demo")
log.info("dictConfig 生效：这条会同时去控制台与文件")
log.debug("这条 DEBUG 仍被 INFO 阈值过滤")
# 验证文件已落盘
print("log file exists:", os.path.exists(demo_log))
with open(demo_log, encoding="utf-8") as f:
    print("file content preview:", f.read().strip().splitlines()[-1][:80])
```

关键区别：`basicConfig` 是“快捷键”，`dictConfig` 是“完整配置表”——后者才能表达“多 handler、多 logger、落盘与轮转”（见 9.3）。`cli.py` 的 `--log-level/--log-file` 正是把命令行参数翻译成 `build_log_config` 的两个实参，再传给 `uvicorn.run(log_config=...)`，从而让 `uvicorn.*` 日志与业务日志走同一套落盘。

### 9.3 落盘与轮转：RotatingFileHandler

“落盘”指把日志写入文件而非仅打印到终端；“轮转”指文件过大时自动切新文件、保留 N 个备份，避免单文件无限增长。

`RotatingFileHandler` 三个关键参数：

- `filename`：落盘路径（如 `data/logs/meetingtotext.log`，`cli.py --log-file` 指定，`build_log_config` 中做 `os.makedirs` 预创建）。
- `maxBytes`：单文件上限（MeetingToText 用 `10 * 1024 * 1024` 即 10 MB）。
- `backupCount`：保留的备份数（MeetingToText 用 `5`，即 `app.log` + `app.log.1` … `app.log.5`）。

当写入超过 `maxBytes` 时，`app.log` → `app.log.1` → `app.log.2` … 最老的被丢弃。多 worker 场景下，`build_log_config` 会按 `pid` 插入后缀（`app.12345.log`）避免并发写同一文件。

```{code-cell} ipython3
import logging.handlers
import tempfile, os, pathlib

tmpdir2 = tempfile.mkdtemp()
log_path = os.path.join(tmpdir2, "rotate.log")

# 小阈值演示轮转：maxBytes=400 字节，backupCount=2，写 30 条约 50 字节/条
handler = logging.handlers.RotatingFileHandler(log_path, maxBytes=400, backupCount=2, encoding="utf-8")
handler.setFormatter(logging.Formatter("%(message)s"))
rot_logger = logging.getLogger("week09.rotate")
rot_logger.handlers.clear()
rot_logger.setLevel(logging.INFO)
rot_logger.addHandler(handler)
rot_logger.propagate = False

for i in range(30):
    rot_logger.info(f"line {i:02d} " + "x" * 40)

handler.close()
rot_logger.removeHandler(handler)

files = sorted(pathlib.Path(tmpdir2).glob("rotate.log*"))
print(f"轮转后文件数: {len(files)} (期望 3 = 当前 + 2 备份，backupCount=2)")
for p in files:
    print(p.name, p.stat().st_size, "bytes")
```

若把 `backupCount` 从 `2` 改为 `1`，文件数会从 3 变为 2——这正是“改动并预测”实验 3 要验证的。

> 小结：MeetingToText 的 `cli.py --log-file {路径}` + `logging_config.build_log_config(level, log_file)` 即“命令行→字典配置→落盘轮转”的完整链路；`--log-level` 控制阈值，`--log-file` 为空则仅控制台。

### 9.4 断点调试：何时停下来

当日志告诉你“结果错了”但看不出哪一行算错时，需要“暂停现场、查看变量”。Python 3.7+ 的 `breakpoint()` 即“在此处暂停、进入调试会话（pdb）”的入口（等价于 `import pdb; pdb.set_trace()`，但可被 `PYTHONBREAKPOINT` 环境变量统一开关）。

最小工作流（在终端中对脚本执行，Jupyter 中仅示意）：

```python
def normalize_segments(segments):
    for seg in segments:
        breakpoint()  # 执行到此暂停，进入 (Pdb) 提示符
        seg["text"] = seg["text"].strip()

# (Pdb) n  # next：执行下一行
# (Pdb) p seg  # print：查看变量
# (Pdb) c  # continue：继续运行到下一断点或结束
# (Pdb) q  # quit：退出调试
```

```bash
# 终端运行含断点的脚本（示意，不在 Jupyter 中执行）
# PYTHONBREAKPOINT=0 python script.py  # 一键禁用所有 breakpoint()
```

何时用断点、何时用日志：

- **断点**：复现路径明确、需观察中间变量、单步验证分支时。
- **日志**：问题发生在用户现场、需事后回溯、或需长期保留证据时。

本章不展开调试器内核（如 `bdb` 事件循环、帧对象 `frame.f_back` 等实现细节），仅要求掌握“插入断点→单步→查看→继续”的最小闭环；更多调试技巧放在习题与延伸挑战中练习。

### 9.5 性能剖析：cProfile 与热点定位

“性能剖析（profiling）”回答“时间花在哪”。Python 标准库 `cProfile` 是确定性剖析器（deterministic profiler）：为每个函数记录 `ncalls`（调用次数）、`tottime`（函数自身耗时，不含子调用）、`cumtime`（含子调用的累积耗时）。两种用法：

**用法 A：命令行**（对整个脚本剖析，无需改代码）：

```bash
# 对脚本整体剖析，按 cumtime 排序，取前 20 行
python -m cProfile -s cumulative {脚本路径} 
# 常见 -s key：cumulative（累积耗时）、tottime（自身耗时）、ncalls（调用次数）
python -m cProfile -s tottime m2t_demo.py
# 输出到文件供 pstats 交互查看
python -m cProfile -o profile.out {脚本路径}
python -c "import pstats; pstats.Stats('profile.out').sort_stats('cumulative').print_stats(20)"
```

**用法 B：代码内**（对指定片段剖析，适合 Jupyter / 单测）：

```{code-cell} ipython3
import cProfile
import pstats
import io

# --- 模拟 m2t 转写流水线的热点：一个可被剖析的小函数 ---
def slow_transform(n: int = 20000) -> int:
    """模拟转写中的文本变换（可被 cProfile 捕获的热点）"""
    total = 0
    for i in range(n):
        total += (i * i) % 10007
    return total

def transcribe_pipeline_mock(repeats: int = 8):
    """模拟流水线：多次调用 slow_transform + 少量其它工作"""
    for _ in range(repeats):
        slow_transform()
    # 少量轻量调用，作为对比
    sum(range(100))

# 用 cProfile.Profile 剖析指定片段（hermetic，不依赖命令行）
prof = cProfile.Profile()
prof.enable()
transcribe_pipeline_mock()
prof.disable()

# 用 pstats 打印 ncalls 表（真实 cProfile 输出，含 ncalls/tottime/cumtime）
buf = io.StringIO()
ps = pstats.Stats(prof, stream=buf).sort_stats("cumulative")
ps.print_stats(12)
output = buf.getvalue()
print(output)
# 校验：输出必含表头 ncalls 且含被剖析的函数名（用于习题断言的稳定锚点）
assert "ncalls" in output
assert "slow_transform" in output
assert "transcribe_pipeline_mock" in output
print("—— 断言通过：ncalls 表头与热点函数名均存在 ——")
```

读表要点（以真实输出为例）：

```
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
        8    0.015    0.002    0.015    0.002 {code-cell}:slow_transform
        1    0.000    0.000    0.015    0.015 {code-cell}:transcribe_pipeline_mock
```

- `ncalls=8` 即 `slow_transform` 被调用 8 次（与 `repeats=8` 一致）。
- `tottime` 大者为热点自身；`cumtime` 大者为“含子调用”的热点入口。`transcribe_pipeline_mock` 的 `cumtime` 是其所有子调用之和，故常排顶部；按 `tottime` 排序则 `slow_transform` 会升至顶部。

改 `sort_stats` 的 key 会改变排序：`sort_stats("cumulative")` 按 `cumtime` 排序（入口函数在前），`sort_stats("tottime")` 按自身耗时排序（叶子热点在前），`sort_stats("ncalls")` 按调用次数排序（高频小函数在前）——这正是实验 2 要预测的。

### 9.6 应用：定位 m2t 转写热点

把 9.5 的方法套用到“m2t 转写”场景（mock，不依赖真实 `FunASR` 模型）：假设流水线为 `load_audio → asr_infer → normalize → export`，其中 `asr_infer` 最耗时。用 `cProfile` 即可在不改业务代码的情况下定位：

```python
# 伪代码：对真实 m2t 流水线的剖析思路（需本地有音频文件时才运行，仅示意）
# python -m cProfile -s cumulative -m m2t.cli transcribe {音频路径} --format txt
# 或在代码中：
# prof = cProfile.Profile()
# prof.enable()
# run_pipeline(task_id)  # 复用 m2t 的同步流水线
# prof.disable()
# pstats.Stats(prof).sort_stats("cumulative").print_stats(20)
```

热点定位后的常规动作：

1. **确认热点**：`tottime` 最大的 1–2 个函数即优化目标（如 `slow_transform` 或真实的 `_load_audio`/`model.generate`）。
2. **区分“可优化”与“外部等待”**：若热点是 `time.sleep`/`requests.get` 等 I/O 等待，优化方向是并发/缓存而非算法；若是纯计算，则考虑向量化、缓存、减少重复调用。
3. **用日志补充上下文**：在热点前后加 `logger.debug("stage start/end")`，结合 `cProfile` 的 `cumtime` 与日志时间戳交叉验证。

> 提示：剖析前先用日志确认“慢在哪一阶段”（`INFO` 级别记录各阶段起止），再对可疑阶段做 `cProfile` 细粒度剖析——先粗后细，避免对全量代码盲目剖析。

### 改动并预测

以下 4 个实验均可在本章 `{code-cell}` 或本地 `.venv` 中复现，按“改什么 → 预测 → 解释”三段式。

#### 改动并预测 实验 1：日志级别 `INFO` → `ERROR` → 预测 `INFO` 是否可见

- **改什么**：把 `logging.basicConfig(level=logging.INFO, ...)` 或 `build_demo_config("INFO", ...)` 中的 `"INFO"` 改为 `"ERROR"`，保持 `logger.info("转写完成")` 与 `logger.error("转写失败")` 两条调用不变，重新运行。
- **预测**：`INFO` 消息消失，仅 `ERROR`（及以上）可见；控制台与落盘文件均不再出现 `INFO` 行。
- **解释**：`level` 是阈值过滤器，`ERROR(40) > INFO(20)`，低于阈值的记录在 `logger` 或 `handler` 层即被丢弃，不会到达格式化与输出。MeetingToText 的 `cli.py --log-level ERROR` 即此效果——生产排障时切 `DEBUG` 可见细节，切 `ERROR` 则降噪。

#### 改动并预测 实验 2：`sort_stats("cumulative")` → `sort_stats("ncalls")` → 预测排序变化

- **改什么**：把 `pstats.Stats(prof).sort_stats("cumulative")` 改为 `sort_stats("ncalls")`（或 `"tottime"`），对同一份 `prof` 重新 `print_stats(12)`，对比两次输出的首行函数。
- **预测**：`cumulative` 时首行常为 `transcribe_pipeline_mock`（`cumtime` 最大，含所有子调用）；改为 `ncalls` 后首行变为调用次数最多的叶子函数（如被调用 8 次的 `slow_transform` 或高频的 `<built-in>`）；改为 `tottime` 时首行变为自身耗时最长的函数（常仍是 `slow_transform`，但与 `cumulative` 的理由不同）。
- **解释**：`sort_stats` 的 key 决定“按哪一列排序”。`cumulative` 突出“入口热点”（谁包含的子调用最重），`tottime` 突出“自身热点”（谁自己最重），`ncalls` 突出“高频调用”。定位热点前需先选对排序依据，否则会在错误的维度上优化。

#### 改动并预测 实验 3：`RotatingFileHandler(backupCount=2)` → `backupCount=1` → 预测轮转文件数

- **改什么**：把 9.3 代码中的 `RotatingFileHandler(log_path, maxBytes=400, backupCount=2)` 改为 `backupCount=1`，保持 `maxBytes` 与写入条数（30 条）不变，重新运行并 `glob("rotate.log*")`。
- **预测**：原先 `backupCount=2` 时文件数为 3（`rotate.log` + `rotate.log.1` + `rotate.log.2`），改为 `1` 后文件数为 2（`rotate.log` + `rotate.log.1`），最老的备份被丢弃，总占用减半。
- **解释**：`backupCount` 即“保留几份历史”，超出的最老备份在轮转时删除。MeetingToText 用 `5` 即保留 5 份、共 6 个文件（当前 + 5 备份），单文件 10 MB 时上限约 60 MB，避免日志撑满磁盘。

#### 改动并预测 实验 4：`dictConfig(disable_existing_loggers=False)` → `True` → 预测已有 logger 行为

- **改什么**：把 `build_demo_config` 返回字典中的 `"disable_existing_loggers": False` 改为 `True`，在 `dictConfig` 之前先 `logging.getLogger("week09.pre_existing").addHandler(...)` 创建一个已有 logger，再 `dictConfig` 后尝试 `getLogger("week09.pre_existing").info("test")`。
- **预测**：`False` 时已有 logger 保留、仍可输出；改为 `True` 后该 logger 被禁用（`disabled=True`），其 `info` 不再输出，除非在新配置的 `loggers` 字典中显式声明它。
- **解释**：`disable_existing_loggers` 控制“未在新配置中出现的旧 logger 是否禁用”。`False`（MeetingToText 的选择）适合增量配置——不因一次 `dictConfig` 而静默已有模块的日志；`True` 则为“全量接管”，适合启动时一次性重建。

## 习题

> 参考答案与测试在 `answers/week09/`，运行 `.venv/bin/pytest answers/week09/ -q` 验证。题目均为 hermetic（不依赖网络/真实模型/外部服务），仅用 `tempfile` 与内存。

1. **日志级别过滤**：实现 `create_memory_logger(level: str) -> tuple[Logger, ListHandler]`，返回绑定了内存 `ListHandler` 的 `logger`（`propagate=False`）。对同一 `logger` 分别 `debug/info/warning/error` 四条，断言 `level="INFO"` 时 `records` 含 `INFO` 及以上、`level="ERROR"` 时仅含 `ERROR`。
2. **RotatingFileHandler 轮转计数**：实现 `write_with_rotation(tmp_dir: str, max_bytes: int, backup_count: int, n: int) -> list[str]`，在 `tmp_dir` 下创建 `RotatingFileHandler(app.log, maxBytes=max_bytes, backupCount=backup_count)` 并写入 `n` 条定长日志，返回 `glob("app.log*")` 的文件名列表。断言 `backup_count=2` 时文件数 `==3`，`backup_count=1` 时 `==2`。
3. **cProfile 剖析 slow 函数并断言统计项存在**：实现 `slow_compute(n: int = 20000) -> int`（纯计算）与 `profile_slow_compute(n: int = 20000) -> pstats.Stats`（用 `cProfile.Profile()` 剖析 `slow_compute`）。测试中对 `stats` 调用 `get_stats()` 或 `print_stats` 后的 `stats.stats` 断言 `slow_compute` 在统计键中且 `ncalls >=1`，并断言输出含 `"ncalls"`。
4. **dictConfig 形状校验**：实现 `build_demo_log_config(level: str, log_file: str | None) -> dict`（形如 9.2 的 `build_demo_config`），测试断言返回字典含 `version/handlers/formatters/root`，且当 `log_file is not None` 时 `handlers` 含 `rotating_file` 且 `filename == log_file`，`level` 非法时回落为 `INFO`。
5. **sort_stats 排序语义**：实现 `profile_pipeline(sort_key: str) -> list[str]`，对 `transcribe_pipeline_mock`（含 `slow_transform` 被调用多次）做 `cProfile` 并按 `sort_key` 排序，返回 `print_stats` 输出中前 3 个函数名的顺序列表。测试断言 `sort_key="cumulative"` 与 `sort_key="ncalls"` 的返回顺序不同（或首元素不同），验证排序 key 的作用。
6. *（附加）* **断点可开关**：实现 `maybe_breakpoint(enabled: bool) -> str`，当 `enabled=False` 时不调用 `breakpoint()` 直接返回 `"no break"`，`enabled=True` 时通过 `unittest.mock.patch("builtins.breakpoint")` 验证 `breakpoint` 被调用一次。测试用 `mock` 断言可开关性（不实际进入 pdb）。

## 延伸挑战

1. 用 `python -m cProfile -s cumulative` 对 `answers/week09/solution.py` 的 `slow_compute(50000)` 单独跑一次（`python -m cProfile -s cumulative -c "import answers.week09.solution; answers.week09.solution.slow_compute(50000)"`），对比 `tottime` 与 `cumtime`，记录热点是否仍为 `slow_compute`。
2. 给 `write_with_rotation` 增加 `maxBytes` 边界测试：设 `maxBytes=1` 极小值，观察每次写入即轮转时文件数的稳定性，思考“过小 `maxBytes` 对 I/O 的代价”。
3. 为 `m2t.store` 的 `create_task` 前后加 `logger.debug("create start/end")`，用 `level=DEBUG` 与 `level=INFO` 各跑一次，对比日志量与 `cProfile` 中 `create_task` 的 `tottime` 占比，体会“日志级别对性能的间接影响”（`DEBUG` 在热路径上需谨慎）。

> 本章内容原创，日志落盘与轮转概念对应 MeetingToText 的 `backend/app/logging_config.py` 与 `cli.py --log-level/--log-file`，cProfile 剖析思路对应转写流水线热点定位，示例代码与表述均为原创。
