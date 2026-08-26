"""保证直接 pytest 也能找到 cli（grader 会另行注入 PYTHONPATH）。

grader 运行时 PYTHONPATH 已含 solution_dir，此时 cli 已可导入，
conftest 不再覆盖，保证 buggy 隔离。直接跑 .venv/bin/pytest 时
若 cli 仍不可导入，则回退到 reference_solution。
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

if importlib.util.find_spec("cli") is None:
    # 优先 reference_solution，其次 student_solution
    here = pathlib.Path(__file__).resolve().parent
    for rel in ("../reference_solution", "../student_solution"):
        cand = (here / rel).resolve()
        if cand.is_dir() and (cand / "cli.py").exists():
            if str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
            # 再次探测，首个可用即停
            if importlib.util.find_spec("cli") is not None:
                break
