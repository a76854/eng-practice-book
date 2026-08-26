#!/usr/bin/env bash
# verify_reverse.sh — 三分支双反向验证（对齐 grader_selfcheck.sh 思想，但针对 m1_cli）
# (a) 好解 reference_solution → PASS
# (b) 故意 buggy 实现 → FAIL
# (c) 学生测试（此处复用教师 tests，因本里程碑黑盒测试即判分依据）× buggy → FAIL
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BOOK_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
MILESTONE="$SCRIPT_DIR"
VENV_PY="$BOOK_DIR/.venv/bin/python"
PYTEST="$BOOK_DIR/.venv/bin/pytest"
TMP_BUG="/tmp/m1_cli_buggy_$$"

echo "=== M1 CLI reverse verification — three branches ==="
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

# 构造 buggy 实现（与 evidence 生成一致）
mkdir -p "$TMP_BUG"
cat > "$TMP_BUG/cli.py" <<'PY'
"""故意 buggy 的 m2tc 实现，用于证明 grader 非摆设。"""
import argparse, os, sys
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"}
ALLOWED_FORMATS = {"txt","srt","md"}
def build_parser():
    p = argparse.ArgumentParser(prog="m2tc")
    sub = p.add_subparsers(dest="command", required=True)
    t = sub.add_parser("transcribe")
    t.add_argument("audio")
    t.add_argument("--format", dest="format", default="txt")
    t.add_argument("--out", dest="out", default=None)
    t.add_argument("--stub", action="store_true", default=False)
    return p
def _cmd_transcribe(args):
    audio = getattr(args,"audio","")
    fmt = (getattr(args,"format","txt") or "txt").strip().lower().lstrip(".")
    out = getattr(args,"out", None)
    if out:
        output_path = out
    else:
        base = os.path.splitext(audio)[0]
        output_path = f"{base}.{fmt if fmt in ALLOWED_FORMATS else 'txt'}"
    parent = os.path.dirname(os.path.abspath(output_path))
    if parent and not os.path.exists(parent):
        try: os.makedirs(parent, exist_ok=True)
        except: pass
    with open(output_path,"w",encoding="utf-8") as f:
        f.write("buggy")
    print(f"转录完成 → {output_path}")
def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args,"command",None)=="transcribe":
        _cmd_transcribe(args)
        return
    parser.error("unknown")
if __name__ == "__main__":
    main(sys.argv[1:])
PY

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
# 复用同一 tests 目录，证明测试非空心
set +e
OUT_C=$(PYTHONPATH="$TMP_BUG:${PYTHONPATH:-}" $PYTEST -q "$MILESTONE/tests" 2>&1)
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
