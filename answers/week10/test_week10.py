"""week10 习题测试（hermetic，确定性并发，≥5 例）。

所有多线程断言均用 join / Future.result / Event 确定性等待，
不用 sleep 竞态；asyncio 测试用 asyncio.run 同步驱动。
"""

from __future__ import annotations

import asyncio
import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "week10_solution",
    pathlib.Path(__file__).with_name("solution.py"),
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

parallel_sum = _mod.parallel_sum  # type: ignore[attr-defined]
run_counter = _mod.run_counter  # type: ignore[attr-defined]
future_cancel_queued = _mod.future_cancel_queued  # type: ignore[attr-defined]
future_cancel_running = _mod.future_cancel_running  # type: ignore[attr-defined]
gather_double = _mod.gather_double  # type: ignore[attr-defined]
cooperative_run = _mod.cooperative_run  # type: ignore[attr-defined]


def test_parallel_sum_basic() -> None:
    nums = list(range(1, 101))
    assert parallel_sum(nums, max_workers=4) == sum(nums)
    assert parallel_sum(nums, max_workers=1) == sum(nums)


def test_parallel_sum_empty_and_single() -> None:
    assert parallel_sum([], max_workers=2) == 0
    assert parallel_sum([42], max_workers=4) == 42
    assert parallel_sum([1, 2, 3], max_workers=10) == 6


def test_run_counter_with_lock_correct() -> None:
    # 加锁时恒等于期望，确定性
    assert run_counter(4, 1000, use_lock=True) == 4000
    assert run_counter(10, 500, use_lock=True) == 5000
    assert run_counter(2, 100, use_lock=True) == 200


def test_run_counter_without_lock_bounded() -> None:
    # 不加锁时结果 <= 期望（可能因竞态丢失），且 >0 且为 int
    result = run_counter(10, 1000, use_lock=False)
    assert isinstance(result, int)
    assert 0 < result <= 10000
    # 多次运行中至少有一次能体现与加锁版本的差异由实现保证，
    # 但此处只断言上界以保持确定性不 flaky
    result2 = run_counter(4, 250, use_lock=False)
    assert 0 < result2 <= 1000


def test_future_cancel_queued_succeeds() -> None:
    ret = future_cancel_queued()
    assert ret["cancelled"] is True
    assert ret["done"] is True
    assert ret["is_cancelled"] is True


def test_future_cancel_running_fails() -> None:
    ret = future_cancel_running()
    assert ret["cancelled"] is False
    assert ret["was_cancelled"] is False
    assert ret["was_done"] is True
    assert ret["result"] == 42


def test_gather_double_order() -> None:
    nums = [3, 1, 4, 1, 5]
    result = asyncio.run(gather_double(nums))
    assert result == [6, 2, 8, 2, 10]
    # 空列表
    assert asyncio.run(gather_double([])) == []
    # 单元素
    assert asyncio.run(gather_double([7])) == [14]
    # 顺序保持：调换输入顺序结果相应调换
    assert asyncio.run(gather_double([5, 3])) == [10, 6]
    assert asyncio.run(gather_double([3, 5])) == [6, 10]


def test_cooperative_run_no_cancel() -> None:
    assert cooperative_run(5, None) == [0, 1, 2, 3, 4]
    assert cooperative_run(0, None) == []
    assert cooperative_run(3, None) == [0, 1, 2]


def test_cooperative_run_with_cancel() -> None:
    # 在第 2 步后取消，下一轮 break，已执行 [0,1,2]
    assert cooperative_run(5, 2) == [0, 1, 2]
    assert cooperative_run(5, 0) == [0]
    assert cooperative_run(5, 4) == [0, 1, 2, 3, 4]
    # 取消点超出范围等价于不取消
    assert cooperative_run(3, 10) == [0, 1, 2]
    # 取消后长度 < steps
    ret = cooperative_run(10, 3)
    assert len(ret) < 10
    assert ret == [0, 1, 2, 3]
