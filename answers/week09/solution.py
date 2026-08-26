"""week09 习题参考答案（hermetic）。

覆盖：日志级别过滤、RotatingFileHandler 轮转、cProfile.Profile 剖析与 ncalls 断言、
dictConfig 形状、sort_stats 排序语义、断点可开关。

不依赖网络/外部服务/真实模型，仅用 tempfile 与内存。
"""

from __future__ import annotations

import cProfile
import io
import logging
import logging.handlers
import pathlib
import pstats


# ---------------------------------------------------------------------------
# 1. 日志级别过滤：内存 Handler
# ---------------------------------------------------------------------------
class ListHandler(logging.Handler):
    """捕获 LogRecord 到内存列表的 Handler（hermetic 测试用）."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def create_memory_logger(level: str, name: str | None = None) -> tuple[logging.Logger, ListHandler]:
    """创建绑定 ListHandler 的 logger，level 为阈值字符串（如 "INFO"）.

    返回 (logger, handler)，handler.records 可检查捕获的记录。
    logger.propagate=False 避免污染 root。
    """
    import uuid as _uuid

    logger_name = name or f"week09.memory.{_uuid.uuid4().hex[:8]}"
    logger = logging.getLogger(logger_name)
    # 清理旧 handler（Jupyter 重复执行时）
    logger.handlers.clear()
    logger.propagate = False
    lvl = getattr(logging, level.upper(), logging.INFO) if isinstance(level, str) else logging.INFO
    # 非法 level 回落 INFO（与 build_demo_log_config 一致）
    if not isinstance(lvl, int):
        lvl = logging.INFO
    if level.upper() not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL") and isinstance(level, str):
        lvl = logging.INFO
    logger.setLevel(lvl)
    handler = ListHandler()
    handler.setLevel(lvl)
    logger.addHandler(handler)
    return logger, handler


# ---------------------------------------------------------------------------
# 2. RotatingFileHandler 轮转计数
# ---------------------------------------------------------------------------
def write_with_rotation(tmp_dir: str, max_bytes: int, backup_count: int, n: int) -> list[str]:
    """在 tmp_dir 下创建 RotatingFileHandler 并写入 n 条定长日志，返回轮转后的文件名列表.

    文件名为 app.log，单条约 60 字节，max_bytes/backup_count 由调用方指定。
    """
    log_path = str(pathlib.Path(tmp_dir) / "app.log")
    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger = logging.getLogger(f"week09.rotate.{pathlib.Path(tmp_dir).name}.{max_bytes}.{backup_count}")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    for i in range(n):
        logger.info(f"line {i:04d} " + "x" * 40)
    handler.close()
    logger.removeHandler(handler)
    files = sorted(pathlib.Path(tmp_dir).glob("app.log*"))
    return [f.name for f in files]


# ---------------------------------------------------------------------------
# 3. cProfile 剖析 slow 函数
# ---------------------------------------------------------------------------
def slow_compute(n: int = 20000) -> int:
    """纯计算慢函数（可被 cProfile 稳定捕获的热点）."""
    total = 0
    for i in range(n):
        total += (i * i) % 10007
    return total


def transcribe_pipeline_mock(repeats: int = 8) -> None:
    """模拟转写流水线：多次调用 slow_compute."""
    for _ in range(repeats):
        slow_compute()
    # 轻量对比
    sum(range(100))


def profile_slow_compute(n: int = 20000) -> pstats.Stats:
    """用 cProfile.Profile 剖析 slow_compute，返回 pstats.Stats."""
    prof = cProfile.Profile()
    prof.enable()
    slow_compute(n)
    prof.disable()
    buf = io.StringIO()
    stats = pstats.Stats(prof, stream=buf).sort_stats("cumulative")
    # 预生成输出以确保 stream 有内容（调用方可用 stats.stats 检查）
    stats.print_stats()
    return stats


def profile_pipeline(sort_key: str = "cumulative") -> list[str]:
    """剖析 transcribe_pipeline_mock 并按 sort_key 排序，返回前 3 个函数名的列表."""
    prof = cProfile.Profile()
    prof.enable()
    transcribe_pipeline_mock()
    prof.disable()
    buf = io.StringIO()
    stats = pstats.Stats(prof, stream=buf).sort_stats(sort_key)
    stats.print_stats(20)
    output = buf.getvalue()
    # 解析输出：每行形如 "   8    0.001    0.000    0.015    0.002 path:lineno(func)"
    func_names: list[str] = []
    for line in output.splitlines():
        # 统计表行含 " " 分隔的 ncalls 且含 "("
        line = line.strip()
        if not line or line.startswith("Ordered by") or "ncalls" in line or "function calls" in line or line.startswith("{"):
            continue
        # 提取括号内函数名
        if "(" in line and ")" in line:
            # 取最后括号内
            start = line.rfind("(")
            end = line.rfind(")")
            if start != -1 and end != -1:
                fname = line[start + 1 : end]
                func_names.append(fname)
                if len(func_names) >= 3:
                    break
    return func_names


# ---------------------------------------------------------------------------
# 4. dictConfig 形状
# ---------------------------------------------------------------------------
def build_demo_log_config(level: str, log_file: str | None) -> dict:
    """生成 dictConfig 兼容字典（简化版，对标 meetingtotext.logging_config.build_log_config）."""
    lvl = level.upper() if isinstance(level, str) else "INFO"
    if lvl not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        lvl = "INFO"
    handlers: dict[str, dict[str, object]] = {}
    names: list[str] = []
    handlers["console"] = {
        "class": "logging.StreamHandler",
        "level": lvl,
        "formatter": "readable",
        "stream": "ext://sys.stderr",
    }
    names.append("console")
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
        "formatters": {
            "readable": {
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
        "handlers": handlers,
        "root": {"level": lvl, "handlers": names},
    }


# ---------------------------------------------------------------------------
# 6. 断点可开关
# ---------------------------------------------------------------------------
def maybe_breakpoint(enabled: bool) -> str:
    """enabled=False 时直接返回，True 时调用 breakpoint() 后返回."""
    if not enabled:
        return "no break"
    breakpoint()
    return "break called"
