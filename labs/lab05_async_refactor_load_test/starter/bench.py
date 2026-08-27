"""Lab05 bench: 标准库压测辅助脚本，无第三方依赖。

思路对齐 ab / locust 的核心度量：固定并发度与总请求数，统计
总耗时、平均时延、吞吐。I/O 用 asyncio.sleep 模拟，可替换为
真实 HTTP 或 DB 调用。

Run:
  python bench.py
  python bench.py --mode sync --requests 20 --concurrency 5
  python bench.py --mode async --requests 20 --concurrency 5 --delay 0.03
  python bench.py --help
"""

from __future__ import annotations

import argparse
import asyncio
import time
from typing import Literal


def sync_job(job_id: int, delay: float = 0.03) -> str:
    time.sleep(delay)
    return f"ok-{job_id}"


async def async_job(job_id: int, delay: float = 0.03) -> str:
    await asyncio.sleep(delay)
    return f"ok-{job_id}"


def run_sync_bench(total: int, delay: float) -> dict:
    t0 = time.perf_counter()
    latencies: list[float] = []
    for i in range(total):
        s = time.perf_counter()
        sync_job(i, delay)
        latencies.append(time.perf_counter() - s)
    elapsed = time.perf_counter() - t0
    latencies.sort()
    return _summarize(latencies, elapsed, total)


async def run_async_bench(total: int, concurrency: int, delay: float) -> dict:
    sem = asyncio.Semaphore(max(1, concurrency))
    latencies: list[float] = []

    async def _one(jid: int) -> None:
        async with sem:
            s = time.perf_counter()
            await async_job(jid, delay)
            latencies.append(time.perf_counter() - s)

    t0 = time.perf_counter()
    await asyncio.gather(*(_one(i) for i in range(total)))
    elapsed = time.perf_counter() - t0
    latencies.sort()
    return _summarize(latencies, elapsed, total)


def _summarize(latencies: list[float], elapsed: float, total: int) -> dict:
    n = len(latencies)
    avg = sum(latencies) / n if n else 0.0
    p50 = latencies[n // 2] if n else 0.0
    p95 = latencies[int(n * 0.95)] if n else 0.0
    p95 = latencies[min(int(n * 0.95), n - 1)] if n else 0.0
    tput = total / elapsed if elapsed > 0 else 0.0
    return {
        "total": total,
        "elapsed": elapsed,
        "avg_ms": avg * 1000,
        "p50_ms": p50 * 1000,
        "p95_ms": p95 * 1000,
        "throughput_rps": tput,
    }


def print_report(title: str, stats: dict, concurrency: int) -> None:
    print(f"[{title}] concurrency={concurrency} total={stats['total']}")
    print(f"  elapsed   : {stats['elapsed']:.3f}s")
    print(f"  avg latency: {stats['avg_ms']:.1f} ms")
    print(f"  p50        : {stats['p50_ms']:.1f} ms")
    print(f"  p95        : {stats['p95_ms']:.1f} ms")
    print(f"  throughput : {stats['throughput_rps']:.1f} req/s")
    print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lab05-bench",
        description="Lab05 bench: stdlib pressure helper (sync vs async)",
    )
    parser.add_argument("--mode", choices=["sync", "async", "both"], default="both", help="bench mode")
    parser.add_argument("--requests", type=int, default=20, help="total requests (default: 20)")
    parser.add_argument("--concurrency", type=int, default=5, help="concurrency for async mode")
    parser.add_argument("--delay", type=float, default=0.03, help="per-request I/O delay in seconds")
    parser.add_argument("--csv", action="store_true", help="also print CSV line")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.requests <= 0 or args.concurrency <= 0 or args.delay < 0:
        parser.error("requests and concurrency must be >0, delay >=0")

    mode: Literal["sync", "async", "both"] = args.mode

    print(f"[bench] mode={mode} requests={args.requests} concurrency={args.concurrency} delay={args.delay}")
    print()

    if mode in ("sync", "both"):
        stats = run_sync_bench(args.requests, args.delay)
        print_report("sync", stats, concurrency=1)
        if args.csv:
            print(f"csv,sync,1,{args.requests},{stats['elapsed']:.3f},{stats['throughput_rps']:.1f}")
    if mode in ("async", "both"):
        stats = asyncio.run(run_async_bench(args.requests, args.concurrency, args.delay))
        print_report("async", stats, concurrency=args.concurrency)
        if args.csv:
            print(f"csv,async,{args.concurrency},{args.requests},{stats['elapsed']:.3f},{stats['throughput_rps']:.1f}")

    if mode == "both":
        print("[hint] async should show lower elapsed and higher throughput when delay is I/O bound")
        print("[hint] increase --concurrency to see throughput scale, then plateau")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
