"""保证直接 pytest 也能找到 app（grader 会另行注入 PYTHONPATH）。

grader 运行时 PYTHONPATH 已含 solution_dir，此时 app 已可导入，
conftest 不再覆盖，保证 buggy 隔离。直接跑 .venv/bin/pytest 时
若 app 仍不可导入，则回退到 reference_solution。
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys

if importlib.util.find_spec("app") is None:
    here = pathlib.Path(__file__).resolve().parent
    for rel in ("../reference_solution", "../student_solution"):
        cand = (here / rel).resolve()
        if cand.is_dir() and (cand / "app.py").exists():
            if str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
            if importlib.util.find_spec("app") is not None:
                break

# 额外：确保仓库根在 sys.path 以便 `import m2t`
import pathlib as _pl

_book_root = pathlib.Path(__file__).resolve().parents[2]
if str(_book_root) not in sys.path:
    sys.path.insert(0, str(_book_root))
