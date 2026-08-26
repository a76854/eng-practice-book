#!/usr/bin/env bash
# verify_reverse.sh — 三分支双反向验证（对齐 grader_selfcheck.sh 思想，但针对 m2_webapi）
# (a) 好解 reference_solution → PASS
# (b) 故意 buggy 实现 → FAIL
# (c) tests-not-hollow（测试非摆设）检查 — 同一套黑盒 tests 复跑于 buggy 实现之上 → expect FAIL（证明 tests 能捕获回归，非空心）
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BOOK_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
MILESTONE="$SCRIPT_DIR"
VENV_PY="$BOOK_DIR/.venv/bin/python"
PYTEST="$BOOK_DIR/.venv/bin/pytest"
TMP_BUG="/tmp/m2_webapi_buggy_$$"

echo "=== M2 Web-API reverse verification — three branches ==="
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

# 构造 buggy 实现（故意错：状态不流转、导出恒为 buggy、缺参/404 均不判错）
mkdir -p "$TMP_BUG"
cat > "$TMP_BUG/app.py" <<'PY'
"""故意 buggy 的 M2 实现，用于证明 grader 非摆设。

错误点：
- POST /transcribe 无参数校验，恒回 pending 且不启动后台；
- GET /status 恒回 pending（永不到 done），也不做 404；
- GET /export 恒回 "buggy" 文本，非法 format 也不判 400。
"""

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

app = FastAPI(title="buggy m2")


@app.post("/transcribe")
def post_transcribe(body: dict | None = None):  # type: ignore[no-untyped-def]
    # 故意不校验 audio_path，恒返回 pending
    return {"task_id": "buggy-id", "status": "pending"}


@app.get("/status/{task_id}")
def get_status(task_id: str):  # type: ignore[no-untyped-def]
    # 恒 pending，永不 404
    return {"task_id": task_id, "status": "pending", "filename": "mock.wav", "error": ""}


@app.get("/export/{task_id}")
def get_export(task_id: str, format: str | None = None):  # type: ignore[no-untyped-def]
    # 恒回 buggy，不校验 format/404/未完成
    return PlainTextResponse(content="buggy", media_type="text/plain; charset=utf-8")


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

echo "--- Branch (c): tests-not-hollow（测试非摆设）检查 — same black-box tests × buggy → expect FAIL ---"
# tests-not-hollow：同一套黑盒 tests（含 m2_webapi）直接对 buggy 实现跑，验证测试非摆设
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
