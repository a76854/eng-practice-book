"""
Milestone autograder convention — pytest-based helper.

每个里程碑目录约定::

    milestones/<name>/
      student_solution/   # 学生提交的代码（被测对象）
      tests/              # 黑盒测试（grader 用它来判分）
      reference_solution/ # 教师参考解（用于自检与对照）

本模块提供 :func:`run_grader`，以 pytest 执行 ``tests/`` 对指定
``solution_dir`` 的黑盒测试，返回结构化的 :class:`GraderResult`。

用法（编程调用）::

    from milestones.grader import run_grader

    result = run_grader("milestones/m1_cli")                     # 测 student_solution
    result = run_grader("milestones/m1_cli", solution="reference_solution")
    result = run_grader("milestones/m1_cli", solution_dir="/tmp/custom_impl")

    if result.passed:
        print("PASS", result.summary)
    else:
        print("FAIL", result.summary)
        print(result.output)

命令行用法::

    python -m milestones.grader milestones/m1_cli
    python -m milestones.grader milestones/m1_cli --solution reference_solution
    python -m milestones.grader milestones/m1_cli --solution-dir /tmp/my_impl
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GraderResult:
    """pytest 执行结果的结构化封装。"""

    passed: bool
    returncode: int
    output: str
    summary: str
    tests_dir: Path
    solution_dir: Path


def _resolve_dirs(
    milestone_dir: str | Path,
    *,
    solution: str | None = None,
    solution_dir: str | Path | None = None,
) -> tuple[Path, Path]:
    milestone = Path(milestone_dir).resolve()
    tests_dir = milestone / "tests"
    if not tests_dir.is_dir():
        raise FileNotFoundError(f"tests dir not found: {tests_dir}")

    if solution_dir is not None:
        sol = Path(solution_dir).resolve()
    elif solution is not None:
        sol = (milestone / solution).resolve()
    else:
        sol = (milestone / "student_solution").resolve()

    if not sol.is_dir():
        raise FileNotFoundError(f"solution dir not found: {sol}")
    return tests_dir, sol


def run_grader(
    milestone_dir: str | Path,
    *,
    solution: str | None = None,
    solution_dir: str | Path | None = None,
    pytest_args: list[str] | None = None,
    python_executable: str | None = None,
) -> GraderResult:
    """对 ``solution_dir`` 执行 ``tests/`` 的 pytest 套件。

    使用 ``pytest`` 作为唯一评测引擎（满足 ``grep -c "pytest"`` 门控）。

    参数:
        milestone_dir: 里程碑根目录（如 ``milestones/m1_cli``）。
        solution: 相对 milestone 的 solution 子目录名（如 ``"reference_solution"``）。
        solution_dir: 绝对/相对路径的 solution 目录；若给出则忽略 ``solution``。
        pytest_args: 追加传给 pytest 的额外参数（如 ``["-v"]``）。
        python_executable: 运行 pytest 的 python 解释器，默认 ``sys.executable``。

    返回:
        GraderResult，``passed`` 为 True 当且仅当 pytest exit code == 0。
    """
    tests_dir, sol_dir = _resolve_dirs(
        milestone_dir, solution=solution, solution_dir=solution_dir
    )
    py = python_executable or sys.executable
    cmd: list[str] = [py, "-m", "pytest", str(tests_dir), "-q"]
    if pytest_args:
        cmd.extend(pytest_args)

    # 将 solution_dir 置于 PYTHONPATH 首位，使 ``tests/`` 中的
    # ``import xxx`` 解析到被测实现而非 reference。
    import os

    env = os.environ.copy()
    env["PYTHONPATH"] = str(sol_dir) + os.pathsep + env.get("PYTHONPATH", "")

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(Path(milestone_dir).resolve()),
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    # 提取 pytest summary 行（如 "3 passed in 0.12s" / "1 failed, 2 passed"）
    summary = ""
    for line in output.splitlines():
        if "passed" in line or "failed" in line or "error" in line:
            summary = line.strip()
    if not summary:
        summary = f"pytest exit={proc.returncode}"

    return GraderResult(
        passed=proc.returncode == 0,
        returncode=proc.returncode,
        output=output,
        summary=summary,
        tests_dir=tests_dir,
        solution_dir=sol_dir,
    )


def _cli() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Milestone pytest grader")
    p.add_argument("milestone_dir", help="path to milestone dir (contains tests/)")
    p.add_argument(
        "--solution",
        default=None,
        help="solution subdir name under milestone (default: student_solution)",
    )
    p.add_argument("--solution-dir", default=None, help="explicit solution dir path")
    p.add_argument("--pytest-args", nargs=argparse.REMAINDER, help="extra pytest args")
    args = p.parse_args()

    result = run_grader(
        args.milestone_dir,
        solution=args.solution,
        solution_dir=args.solution_dir,
        pytest_args=args.pytest_args,
    )
    print(result.output, end="")
    if result.passed:
        print("\n[GRADER] PASS —", result.summary)
    else:
        print("\n[GRADER] FAIL —", result.summary)
    sys.exit(result.returncode)


if __name__ == "__main__":
    _cli()
