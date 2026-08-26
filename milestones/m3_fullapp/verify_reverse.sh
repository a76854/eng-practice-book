#!/usr/bin/env bash
# verify_reverse.sh — 三分支双反向验证（对齐 grader_selfcheck.sh 思想，但针对 m3_fullapp）
# (a) 好解 reference_solution → PASS
# (b) 故意 buggy 实现 → FAIL
# (c) 学生测试（此处复用教师 tests，因本里程碑黑盒测试即判分依据）× buggy → FAIL
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BOOK_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
MILESTONE="$SCRIPT_DIR"
VENV_PY="$BOOK_DIR/.venv/bin/python"
PYTEST="$BOOK_DIR/.venv/bin/pytest"
TMP_BUG="/tmp/m3_fullapp_buggy_$$"

echo "=== M3 Full-App reverse verification — three branches ==="
echo "book dir: $BOOK_DIR"
echo "milestone: $MILESTONE"
echo "pytest: $PYTEST"
echo "venv python: $VENV_PY"
echo ""

cleanup() {
  rm -rf "$TMP_BUG"
  echo "cleanup receipt: removed $TMP_BUG"
}
trap cleanup EXIT

# 构造 buggy 实现（故意错：状态不流转、导出恒为 buggy、纪要空、HTML 缺关键词）
mkdir -p "$TMP_BUG"
cat > "$TMP_BUG/app.py" <<'PY'
"""故意 buggy 的 M3 实现，用于证明 grader 非摆设。

错误点：
- POST /transcribe 无参数校验，恒回 pending 且不启动后台；
- GET /status 恒回 pending（永不到 done），也不做 404；
- GET /tasks 恒回空列表；
- POST /generate 恒回空 minutes；
- GET /export 恒回 "buggy" 文本，非法 format 也不判 400；
- GET / 返回不含任务列表关键词的 HTML（无 MeetingToText / 任务列表 / fetch）。
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse

app = FastAPI(title="buggy m3")


@app.post("/transcribe")
def post_transcribe(body: dict | None = None):  # type: ignore[no-untyped-def]
    return {"task_id": "buggy-id", "status": "pending"}


@app.get("/status/{task_id}")
def get_status(task_id: str):  # type: ignore[no-untyped-def]
    return {"task_id": task_id, "status": "pending", "filename": "mock.wav", "error": ""}


@app.get("/tasks")
def list_tasks():  # type: ignore[no-untyped-def]
    return {"tasks": []}


@app.post("/generate/{task_id}")
def post_generate(task_id: str, body: dict | None = None):  # type: ignore[no-untyped-def]
    return {"task_id": task_id, "minutes": ""}


@app.get("/export/{task_id}")
def get_export(task_id: str, format: str | None = None):  # type: ignore[no-untyped-def]
    return PlainTextResponse(content="buggy", media_type="text/plain; charset=utf-8")


@app.get("/")
def get_index():  # type: ignore[no-untyped-def]
    return HTMLResponse(content="<html><body>buggy</body></html>", media_type="text/html; charset=utf-8")


def reset_state() -> None:  # type: ignore[no-untyped-def]
    pass
PY
touch "$TMP_BUG/__init__.py"

echo "--- Branch (a): GOOD reference_solution vs tests — expect PASS ---"
set +e
OUT_A=$(cd "$BOOK_DIR" && PYTHONPATH="$BOOK_DIR:${PYTHONPATH:-}" $VENV_PY -m milestones.grader "$MILESTONE" --solution reference_solution 2>&1)
RC_A=$?
set -e
echo "$OUT_A"
if [ $RC_A -eq 0 ]; then echo "[PASS] Branch (a) PASS"; BRANCH_A="PASS"; else echo "[FAIL] Branch (a) FAIL"; BRANCH_A="FAIL"; fi
echo ""

echo "--- Branch (b): BUGGY solution vs tests — expect FAIL ---"
set +e
OUT_B=$(cd "$BOOK_DIR" && PYTHONPATH="$BOOK_DIR:${PYTHONPATH:-}" $VENV_PY -m milestones.grader "$MILESTONE" --solution-dir "$TMP_BUG" 2>&1)
RC_B=$?
set -e
echo "$OUT_B"
if [ $RC_B -ne 0 ]; then echo "[PASS] Branch (b) PASS — buggy correctly failed"; BRANCH_B="PASS"; else echo "[FAIL] Branch (b) FAIL — buggy should have failed"; BRANCH_B="FAIL"; fi
echo ""

echo "--- Branch (c): BUGGY vs tests (student_tests 同源) — expect FAIL ---"
set +e
OUT_C=$(PYTHONPATH="$TMP_BUG:${PYTHONPATH:-}:$BOOK_DIR" $PYTEST -q "$MILESTONE/tests" 2>&1)
RC_C=$?
set -e
echo "$OUT_C"
if [ $RC_C -ne 0 ]; then echo "[PASS] Branch (c) PASS — student tests caught buggy"; BRANCH_C="PASS"; else echo "[FAIL] Branch (c) FAIL — vacuous"; BRANCH_C="FAIL"; fi
echo ""

echo "=== VERDICT ==="
echo "Branch (a) GOOD→PASS: $BRANCH_A"
echo "Branch (b) BUGGY→FAIL: $BRANCH_B"
echo "Branch (c) STUDENT×BUGGY: $BRANCH_C"
if [ "$BRANCH_A" = "PASS" ] && [ "$BRANCH_B" = "PASS" ] && [ "$BRANCH_C" = "PASS" ]; then
  echo "All three branches behaved as expected — dual reverse-verification succeeded."
  exit 0
else
  echo "Self-check FAILED"
  exit 1
fi
