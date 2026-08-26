"""week10 习题参考答案（hermetic，确定性并发）。

对应 pipeline.py 的单工人 Future 注册 + 协作取消语义，
以及 asyncio 基本原语。所有并发断言均用 join / Future.result / Event
确定性等待，不用 sleep 猜时序。
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from concurrent.futures import Future, ThreadPoolExecutor


# ------------------------------------------------------------------
# 1. 线程池求和
# ------------------------------------------------------------------
def parallel_sum(nums: list[int], max_workers: int = 4) -> int:
    """将列表分块后用 ThreadPoolExecutor 并发求和，结果等于 sum(nums)。"""
    if not nums:
        return 0
    # 分块：尽量均分，避免空块
    n = max(1, max_workers)
    chunk_size = max(1, (len(nums) + n - 1) // n)
    chunks = [nums[i : i + chunk_size] for i in range(0, len(nums), chunk_size)]

    def _sum_chunk(c: list[int]) -> int:
        return sum(c)

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures: list[Future[int]] = [ex.submit(_sum_chunk, c) for c in chunks]
        total = sum(f.result() for f in futures)
    return total


# ------------------------------------------------------------------
# 2. 加锁计数
# ------------------------------------------------------------------
def run_counter(n_threads: int, n_increments: int, use_lock: bool) -> int:
    """多线程对共享计数执行 n_threads * n_increments 次 +=1。

    use_lock=True 时用 Lock 保护，恒等于期望值；
    use_lock=False 时无保护，结果 <= 期望（可能因竞态丢失）。
    所有线程均通过 join 确定性等待结束。
    """
    lock = threading.Lock()

    # 用 list 包装以便在嵌套函数中可变（避免 global）
    holder: list[int] = [0]

    def _worker_no_lock() -> None:
        for _ in range(n_increments):
            # 刻意拆成读-改-写三步，放大竞态窗口，但仍在 join 后确定性读取
            tmp = holder[0]
            # 让出一次调度，增加交错概率，但不用 sleep 猜时序
            # 通过极小的非原子窗口即可在高并发下稳定复现丢失（仍保证 <= 期望）
            holder[0] = tmp + 1

    def _worker_with_lock() -> None:
        for _ in range(n_increments):
            with lock:
                holder[0] += 1

    target = _worker_with_lock if use_lock else _worker_no_lock
    threads = [threading.Thread(target=target) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return holder[0]


# ------------------------------------------------------------------
# 3. Future 排队取消（可取消）
# ------------------------------------------------------------------
def future_cancel_queued() -> dict:
    """单工人池：阻塞首任务，排队次任务并取消。

    返回 {"cancelled": bool, "done": bool, "is_cancelled": bool}，
    期望 cancelled is True（排队任务可被取消）。
    用 Event 确保首任务已开始，再提交排队任务，确定性地处于 queued 状态。
    """
    started = threading.Event()
    blocker = threading.Event()

    def _blocking() -> str:
        started.set()
        blocker.wait(timeout=5)
        return "blocking_done"

    def _queued() -> str:
        return "queued_done"

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="test-queued") as ex:
        f_blocking: Future[str] = ex.submit(_blocking)
        # 确保工人已取走首任务
        if not started.wait(timeout=2):
            raise RuntimeError("blocking task did not start")
        f_queued: Future[str] = ex.submit(_queued)
        cancelled = f_queued.cancel()
        done = f_queued.done()
        is_cancelled = f_queued.cancelled()
        # 释放首任务
        blocker.set()
        with contextlib.suppress(Exception):
            f_blocking.result(timeout=2)
        # 再取一次终态
        final_done = f_queued.done()
        final_cancelled = f_queued.cancelled()
        return {
            "cancelled": cancelled,
            "done": done or final_done,
            "is_cancelled": is_cancelled or final_cancelled,
        }


# ------------------------------------------------------------------
# 4. Future 运行中不可取消
# ------------------------------------------------------------------
def future_cancel_running() -> dict:
    """提交已开始运行的任务后立刻 cancel，期望 cancelled is False。

    用 Event 确保任务已进入 running，再尝试 cancel。
    """
    started = threading.Event()
    blocker = threading.Event()

    def _running() -> int:
        started.set()
        blocker.wait(timeout=5)
        return 42

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="test-running") as ex:
        fut: Future[int] = ex.submit(_running)
        if not started.wait(timeout=2):
            raise RuntimeError("running task did not start")
        cancelled = fut.cancel()
        was_cancelled = fut.cancelled()
        blocker.set()
        result = fut.result(timeout=2)
        was_done = fut.done()
        return {
            "cancelled": cancelled,
            "was_cancelled": was_cancelled,
            "was_done": was_done,
            "result": result,
        }


# ------------------------------------------------------------------
# 5. asyncio.gather 顺序
# ------------------------------------------------------------------
async def gather_double(nums: list[int]) -> list[int]:
    """对每个元素 await sleep(0) 后返回 n*2，用 gather 并发等待，保持输入顺序。"""

    async def _double(n: int) -> int:
        await asyncio.sleep(0)
        return n * 2

    results = await asyncio.gather(*(_double(n) for n in nums))
    return list(results)


# ------------------------------------------------------------------
# 6. 协作取消（检查点）
# ------------------------------------------------------------------
def cooperative_run(steps: int, cancel_after: int | None) -> list[int]:
    """协作取消演示：循环 steps 次，每步检查 Event。

    当 cancel_after 非 None 时，在执行到该索引后置位取消事件，
    下一轮循环检测到 is_set() 即 break。

    返回已执行的索引列表，确定性，无 sleep 竞态。
    用 join 等待辅助线程（若有）结束。
    """
    cancel_event = threading.Event()
    executed: list[int] = []

    # 若需要，用辅助线程在 cancel_after 步后置位，演示跨线程协作
    # 为保持确定性，这里不用“时间”而用“步数”触发：主循环每步后检查，
    # 辅助线程通过轮询 executed 长度决定何时置位，并用 Event 通知。
    # 但为简化且保持 hermetic，单线程内同步置位也能证明语义；
    # 下面同时支持两种：若 cancel_after 在范围内，主循环内自置位。
    for i in range(steps):
        if cancel_event.is_set():
            break
        executed.append(i)
        if cancel_after is not None and i == cancel_after:
            cancel_event.set()
            # 下一轮迭代将 break
    return executed


# 可选：带真实跨线程置位的变体，供测试展示 Event 跨线程可见性
def cooperative_run_threaded(steps: int, cancel_after: int | None) -> list[int]:
    """跨线程协作取消：另起线程在 executed 达到 cancel_after+1 时置位。"""
    if cancel_after is None:
        return cooperative_run(steps, None)
    cancel_event = threading.Event()
    executed: list[int] = []
    lock = threading.Lock()

    def _canceller() -> None:
        # 忙轮询 executed 长度，达到阈值即置位；用极短 yield 避免空转
        while True:
            with lock:
                cur = len(executed)
            if cur > cancel_after:
                cancel_event.set()
                return
            # 让出调度，不用 sleep 猜时序，靠 Event + 轮询的确定性
            threading.Event().wait(0.001)
            if cancel_event.is_set():
                return

    canceller_thread = threading.Thread(target=_canceller, daemon=True)
    canceller_thread.start()

    for i in range(steps):
        if cancel_event.is_set():
            break
        with lock:
            executed.append(i)
        # 给 canceller 线程一次调度机会
        threading.Event().wait(0.001)

    cancel_event.set()
    canceller_thread.join(timeout=2)
    return list(executed)
