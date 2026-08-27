"""Lab05 starter: 同步 vs 异步最小示例 + 耗时对比。

为什么这样对比：同步路径用 time.sleep 模拟阻塞 I/O，异步路径用
asyncio.sleep 模拟非阻塞等待，二者在单机标准库下即可复现
"串行叠加 vs 并发重叠"的核心差异，对应第6章的事件循环模型。

Run:
  python main.py
  python main.py --tasks 5 --delay 0.06
  python main.py --help
"""

from __future__ import annotations

import argparse
import asyncio
import time


def sync_fetch(task_id: int, delay: float = 0.05) -> str:
    """同步 I/O 模拟：阻塞等待 delay 后返回结果。"""
    time.sleep(delay)
    return f"result-{task_id}"


async def async_fetch(task_id: int, delay: float = 0.05) -> str:
    """异步 I/O 模拟：非阻塞等待 delay 后返回结果。"""
    await asyncio.sleep(delay)
    return f"result-{task_id}"


def run_sync_many(n: int, delay: float) -> tuple[list[str], float]:
    t0 = time.perf_counter()
    results = [sync_fetch(i, delay) for i in range(n)]
    elapsed = time.perf_counter() - t0
    return results, elapsed


async def run_async_many(n: int, delay: float) -> tuple[list[str], float]:
    t0 = time.perf_counter()
    results = await asyncio.gather(*(async_fetch(i, delay) for i in range(n)))
    elapsed = time.perf_counter() - t0
    return list(results), elapsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lab05-starter",
        description="Lab05 starter: sync vs async DB / I/O demo with timing",
    )
    parser.add_argument("--tasks", type=int, default=5, help="number of tasks (default: 5)")
    parser.add_argument("--delay", type=float, default=0.05, help="per-task delay in seconds (default: 0.05)")
    parser.add_argument("--concurrency", type=int, default=5, help="async concurrency hint (default: 5)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    n = args.tasks
    delay = args.delay
    conc = min(args.concurrency, n) if n > 0 else 1

    if n <= 0 or delay < 0:
        parser.error("tasks must be >0 and delay must be >=0")

    print(f"[lab05] tasks={n} delay={delay:.3f}s concurrency={conc}")
    print(f"[lab05] python: {time.strftime('%Y-%m-%d')} stdlib only, no third-party deps")
    print()

    # 同步串行：耗时约 n * delay
    sync_results, t_sync = run_sync_many(n, delay)
    print(f"sync  serial : {t_sync:.3f}s for {n} tasks -> {sorted(sync_results)[:3]} ...")
    print(f"       avg per task ~ {t_sync / n:.3f}s, throughput ~ {n / t_sync:.1f} req/s")

    # 异步并发：耗时约 delay（等待重叠）
    async_results, t_async = asyncio.run(run_async_many(n, delay))
    print(f"async gather : {t_async:.3f}s for {n} tasks -> {sorted(async_results)[:3]} ...")
    print(f"       avg per task ~ {t_async / n:.3f}s, throughput ~ {n / t_async:.1f} req/s")

    print()
    if t_async < t_sync:
        ratio = t_sync / t_async if t_async > 0 else float("inf")
        print(f"[result] async faster by {ratio:.1f}x (concurrent overlap wins)")
    else:
        print("[result] sync and async similar (check delay / task count)")

    # 陷阱提示：若在 async 中直接调用 sync_fetch，会退化为串行
    print()
    print("[hint] try bench.py for pressure with --concurrency / --requests")
    print("[hint] trap demo: calling time.sleep inside async would block the loop,")
    print("       fix with await loop.run_in_executor(None, sync_fetch, i) or use def route")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
