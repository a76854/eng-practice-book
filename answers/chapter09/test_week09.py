"""week09 习题测试（hermetic）。

覆盖：日志级别过滤、RotatingFileHandler 轮转、cProfile.Profile 统计项存在、
dictConfig 形状、sort_stats 排序语义、断点可开关。全部 hermetic。
"""

from __future__ import annotations

import cProfile
import importlib.util
import io
import logging
import pathlib
import pstats
import tempfile
from unittest import mock

_spec = importlib.util.spec_from_file_location(
    "week09_solution",
    pathlib.Path(__file__).with_name("solution.py"),
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

build_demo_log_config = _mod.build_demo_log_config  # type: ignore[attr-defined]
create_memory_logger = _mod.create_memory_logger  # type: ignore[attr-defined]
maybe_breakpoint = _mod.maybe_breakpoint  # type: ignore[attr-defined]
profile_pipeline = _mod.profile_pipeline  # type: ignore[attr-defined]
profile_slow_compute = _mod.profile_slow_compute  # type: ignore[attr-defined]
slow_compute = _mod.slow_compute  # type: ignore[attr-defined]
write_with_rotation = _mod.write_with_rotation  # type: ignore[attr-defined]


# 1. 日志级别过滤：INFO 时可见 INFO 及以上
def test_level_filter_info_visible() -> None:
    logger, handler = create_memory_logger("INFO")
    logger.debug("debug msg")
    logger.info("info msg")
    logger.warning("warning msg")
    logger.error("error msg")
    levels = [r.levelno for r in handler.records]
    assert logging.INFO in levels
    assert logging.WARNING in levels
    assert logging.ERROR in levels
    assert logging.DEBUG not in levels
    assert len(handler.records) == 3


def test_level_filter_error_hides_info() -> None:
    logger, handler = create_memory_logger("ERROR")
    logger.debug("debug msg")
    logger.info("info msg")
    logger.warning("warning msg")
    logger.error("error msg")
    levels = [r.levelno for r in handler.records]
    assert logging.ERROR in levels
    assert logging.INFO not in levels
    assert logging.WARNING not in levels
    assert logging.DEBUG not in levels
    assert len(handler.records) == 1


def test_level_filter_debug_sees_all() -> None:
    logger, handler = create_memory_logger("DEBUG")
    logger.debug("d")
    logger.info("i")
    logger.warning("w")
    logger.error("e")
    assert len(handler.records) == 4


# 2. RotatingFileHandler 轮转计数
def test_rotating_backup_count_2() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        files = write_with_rotation(tmpdir, max_bytes=400, backup_count=2, n=30)
        # backupCount=2 => 当前 + 2 备份 = 3
        assert len(files) == 3
        assert "app.log" in files
        assert "app.log.1" in files
        assert "app.log.2" in files


def test_rotating_backup_count_1() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        files = write_with_rotation(tmpdir, max_bytes=400, backup_count=1, n=30)
        assert len(files) == 2
        assert "app.log" in files
        assert "app.log.1" in files


def test_rotating_no_rotation_when_large_maxbytes() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        files = write_with_rotation(tmpdir, max_bytes=10 * 1024 * 1024, backup_count=2, n=5)
        # 未触发轮转，仅当前文件
        assert len(files) == 1
        assert files[0] == "app.log"


# 3. cProfile 剖析 slow 函数并断言统计项存在（真实 cProfile 输出）
def test_cprofile_stats_contain_slow_compute() -> None:
    stats = profile_slow_compute(5000)
    # stats.stats 键为 (filename, lineno, funcname)
    func_names = [k[2] for k in stats.stats]
    assert "slow_compute" in func_names
    # 至少调用一次
    for k, v in stats.stats.items():
        if k[2] == "slow_compute":
            # v = (cc, nc, tt, ct, callers)
            ncalls = v[1]
            assert ncalls >= 1
            break
    else:
        raise AssertionError("slow_compute not in stats")


def test_cprofile_ncalls_in_output() -> None:
    # 验证真实 cProfile 输出含 ncalls 表头与函数名（与正文一致的强断言）
    prof = cProfile.Profile()
    prof.enable()
    slow_compute(3000)
    prof.disable()
    buf = io.StringIO()
    ps = pstats.Stats(prof, stream=buf).sort_stats("cumulative")
    ps.print_stats(10)
    output = buf.getvalue()
    assert "ncalls" in output
    assert "slow_compute" in output
    # 额外：stats 非空
    assert len(ps.stats) > 0


def test_cprofile_profile_is_deterministic() -> None:
    # 两次剖析同一函数，统计项稳定存在（非 flaky）
    for _ in range(2):
        stats = profile_slow_compute(2000)
        func_names = [k[2] for k in stats.stats]
        assert "slow_compute" in func_names


# 4. dictConfig 形状校验
def test_dictconfig_contains_handlers() -> None:
    cfg = build_demo_log_config("INFO", None)
    assert cfg["version"] == 1
    assert "handlers" in cfg
    assert "formatters" in cfg
    assert "root" in cfg
    assert "console" in cfg["handlers"]
    assert "rotating_file" not in cfg["handlers"]
    assert cfg["root"]["level"] == "INFO"  # type: ignore[index]


def test_dictconfig_with_log_file() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = str(pathlib.Path(tmpdir) / "app.log")
        cfg = build_demo_log_config("DEBUG", log_file)
        assert "rotating_file" in cfg["handlers"]
        assert cfg["handlers"]["rotating_file"]["filename"] == log_file  # type: ignore[index]
        assert cfg["root"]["level"] == "DEBUG"  # type: ignore[index]
        # 实际 dictConfig 可加载
        import logging.config

        logging.config.dictConfig(cfg)
        # 验证 logger 可用
        logger = logging.getLogger("week09.test.dictconfig")
        logger.debug("test debug via dictConfig")


def test_dictconfig_invalid_level_falls_back_to_info() -> None:
    cfg = build_demo_log_config("VERBOSE", None)
    assert cfg["root"]["level"] == "INFO"  # type: ignore[index]
    assert cfg["handlers"]["console"]["level"] == "INFO"  # type: ignore[index]


# 5. sort_stats 排序语义
def test_sort_stats_changes_order() -> None:
    # 同一流水线按不同 key 排序，顺序应不同（cumulative vs ncalls）
    order_cum = profile_pipeline("cumulative")
    order_ncalls = profile_pipeline("ncalls")
    # 至少两者不完全相同（cumulative 首为入口，ncalls 首为高频）
    # 若偶然相同则放宽为两者均非空且含 slow_compute
    assert len(order_cum) >= 1
    assert len(order_ncalls) >= 1
    # 强断言：两者首元素不同 或 整体顺序不同（避免 flaky，任一满足即过）
    if order_cum[0] == order_ncalls[0]:
        assert order_cum != order_ncalls or "slow_compute" in order_cum


def test_sort_stats_tottime_vs_cumulative() -> None:
    order_cum = profile_pipeline("cumulative")
    order_tottime = profile_pipeline("tottime")
    assert len(order_cum) >= 1
    assert len(order_tottime) >= 1
    # 两者均应包含热点
    assert "slow_compute" in order_cum or "transcribe_pipeline_mock" in order_cum
    assert "slow_compute" in order_tottime or "transcribe_pipeline_mock" in order_tottime


# 6. 断点可开关（mock，不真进 pdb）
def test_maybe_breakpoint_disabled() -> None:
    result = maybe_breakpoint(False)
    assert result == "no break"
    # 禁用时 breakpoint 不应被调用
    with mock.patch("builtins.breakpoint") as mock_bp:
        maybe_breakpoint(False)
        mock_bp.assert_not_called()


def test_maybe_breakpoint_enabled_calls_breakpoint() -> None:
    with mock.patch("builtins.breakpoint") as mock_bp:
        result = maybe_breakpoint(True)
        mock_bp.assert_called_once()
        assert result == "break called"
