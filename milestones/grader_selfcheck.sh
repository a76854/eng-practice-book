#!/usr/bin/env bash
# milestones/grader_selfcheck.sh — THREE-branch dual reverse-verification (6.031 mode)
#
# (a) GOOD solution → tests PASS
# (b) deliberately BUGGY reference solution → tests must FAIL  (grader reports FAIL)
# (c) STUDENT-provided test suite run against BUGGY implementation → must FAIL
#     (proves tests actually catch bugs; a vacuous suite would fail this check)
#
# Isolated venv at /tmp/m2t-grader-venv — never touches book .venv.
# Cleanup receipt at end.
set -euo pipefail

VENV_DIR="/tmp/m2t-grader-venv"
FIXTURE_DIR="/tmp/m2t-grader-fixture-$$"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BOOK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors only if stdout is a tty; keep grep-able PASS/FAIL tokens always.
pass() { echo "[PASS] $*"; }
fail() { echo "[FAIL] $*"; }

cleanup() {
  echo "--- cleanup ---"
  rm -rf "$FIXTURE_DIR"
  if [ -d "$VENV_DIR" ]; then
    rm -rf "$VENV_DIR"
    echo "cleanup receipt: removed $VENV_DIR"
  else
    echo "cleanup receipt: $VENV_DIR already absent"
  fi
}
trap cleanup EXIT

echo "=== grader_selfcheck — dual reverse-verification ==="
echo "book dir: $BOOK_DIR"
echo "fixture:  $FIXTURE_DIR"
echo "venv:     $VENV_DIR"

# ---------------------------------------------------------------------------
# 1) Isolated venv with pytest
# ---------------------------------------------------------------------------
PYTEST_BIN=""
PYTEST_RUNTIME=""

# Always create a fresh isolated venv; never reuse book .venv.
if [ -d "$VENV_DIR" ]; then
  rm -rf "$VENV_DIR"
fi
echo "--- creating isolated venv at $VENV_DIR ---"
if python3 -m venv "$VENV_DIR" 2>&1; then
  # Try pip install; if network is unavailable, fall back to ambient pytest.
  if "$VENV_DIR/bin/pip" install --quiet pytest 2>&1; then
    PYTEST_BIN="$VENV_DIR/bin/pytest"
    PYTEST_RUNTIME="isolated-venv ($VENV_DIR) — pip install pytest succeeded"
  else
    echo "pip install pytest failed (offline?) — probing ambient pytest"
    if python3 -m pytest --version >/dev/null 2>&1; then
      PYTEST_BIN="python3 -m pytest"
      PYTEST_RUNTIME="ambient python3 -m pytest (pip install failed, fallback)"
    elif command -v pytest >/dev/null 2>&1; then
      PYTEST_BIN="pytest"
      PYTEST_RUNTIME="ambient pytest (pip install failed, fallback)"
    else
      echo "ERROR: no pytest available (isolated pip failed and no ambient pytest)"
      exit 2
    fi
  fi
else
  echo "python3 -m venv failed — probing ambient pytest"
  if python3 -m pytest --version >/dev/null 2>&1; then
    PYTEST_BIN="python3 -m pytest"
    PYTEST_RUNTIME="ambient python3 -m pytest (venv creation failed, fallback)"
  elif command -v pytest >/dev/null 2>&1; then
    PYTEST_BIN="pytest"
    PYTEST_RUNTIME="ambient pytest (venv creation failed, fallback)"
  else
    echo "ERROR: no pytest available"
    exit 2
  fi
fi

echo "pytest runtime: $PYTEST_RUNTIME"
echo "pytest bin:     $PYTEST_BIN"
# Record version
if [[ "$PYTEST_BIN" == *"pytest" ]]; then
  # shellcheck disable=SC2086
  $PYTEST_BIN --version 2>&1 || true
fi

# Resolve python executable for grader.py / run_grader helper
if [ -x "$VENV_DIR/bin/python" ]; then
  GRADER_PYTHON="$VENV_DIR/bin/python"
else
  GRADER_PYTHON="python3"
fi
echo "grader python: $GRADER_PYTHON"
echo ""

# ---------------------------------------------------------------------------
# 2) Create throwaway fixture milestone (add(a,b) task) under /tmp — NOT committed
# ---------------------------------------------------------------------------
mkdir -p "$FIXTURE_DIR"
MILESTONE="$FIXTURE_DIR/milestone_add"
mkdir -p "$MILESTONE/student_solution" "$MILESTONE/reference_solution" "$MILESTONE/tests" "$MILESTONE/buggy_solution" "$MILESTONE/student_tests"

# GOOD implementation (correct add)
cat > "$MILESTONE/student_solution/calc.py" <<'PY'
def add(a, b):
    return a + b
PY
cp "$MILESTONE/student_solution/calc.py" "$MILESTONE/reference_solution/calc.py"

# BUGGY implementation (off-by-one; intentionally wrong)
cat > "$MILESTONE/buggy_solution/calc.py" <<'PY'
def add(a, b):
    return a + b + 1
PY

# Teacher-provided black-box tests (authoritative)
cat > "$MILESTONE/tests/test_calc.py" <<'PY'
from calc import add

def test_add_positive():
    assert add(2, 3) == 5

def test_add_negative():
    assert add(-1, 1) == 0

def test_add_zero():
    assert add(0, 0) == 0
PY

# Student-provided test suite (also correct — must catch buggy impl)
cat > "$MILESTONE/student_tests/test_calc.py" <<'PY'
from calc import add

def test_student_add():
    assert add(10, 20) == 30

def test_student_zero():
    assert add(0, 5) == 5
PY

echo "fixture milestone created at $MILESTONE"
echo ""

# Helper: run pytest with given solution dir on given tests dir; returns exit code
# Usage: run_with <tests_dir> <solution_dir>
run_with() {
  local tests_dir="$1"
  local sol_dir="$2"
  # shellcheck disable=SC2086
  PYTHONPATH="$sol_dir:${PYTHONPATH:-}" $PYTEST_BIN -q "$tests_dir" 2>&1 || true
}

# Helper that captures exit code explicitly
run_with_rc() {
  local tests_dir="$1"
  local sol_dir="$2"
  set +e
  # shellcheck disable=SC2086
  PYTHONPATH="$sol_dir:${PYTHONPATH:-}" $PYTEST_BIN -q "$tests_dir" 2>&1
  local rc=$?
  set -e
  return $rc
}

# ---------------------------------------------------------------------------
# Branch (a): GOOD solution → tests PASS
# ---------------------------------------------------------------------------
echo "=== Branch (a): GOOD solution vs teacher tests — expect PASS ==="
set +e
OUT_A=$(PYTHONPATH="$MILESTONE/student_solution:${PYTHONPATH:-}" $PYTEST_BIN -q "$MILESTONE/tests" 2>&1)
RC_A=$?
set -e
echo "$OUT_A"
if [ $RC_A -eq 0 ]; then
  pass "Branch (a) PASS — good solution passed teacher tests (exit $RC_A)"
  BRANCH_A="PASS"
else
  fail "Branch (a) FAIL — good solution should have passed but exit $RC_A"
  BRANCH_A="FAIL"
fi
echo ""

# Demonstrate grader.py helper on branch (a) as well
echo "--- grader.py helper demo (branch a) ---"
"$GRADER_PYTHON" "$BOOK_DIR/milestones/grader.py" "$MILESTONE" --solution-dir "$MILESTONE/student_solution" 2>&1 || true
echo ""

# ---------------------------------------------------------------------------
# Branch (b): BUGGY reference solution → tests must FAIL (grader reports FAIL)
# ---------------------------------------------------------------------------
echo "=== Branch (b): BUGGY solution vs teacher tests — expect FAIL (grader reports FAIL) ==="
set +e
OUT_B=$(PYTHONPATH="$MILESTONE/buggy_solution:${PYTHONPATH:-}" $PYTEST_BIN -q "$MILESTONE/tests" 2>&1)
RC_B=$?
set -e
echo "$OUT_B"
if [ $RC_B -ne 0 ]; then
  pass "Branch (b) PASS — grader correctly reports FAIL for buggy solution (exit $RC_B)"
  BRANCH_B="PASS"
else
  fail "Branch (b) FAIL — buggy solution should have been caught but exit $RC_B"
  BRANCH_B="FAIL"
fi
echo ""

# Also via grader.py helper
echo "--- grader.py helper demo (branch b) ---"
set +e
"$GRADER_PYTHON" "$BOOK_DIR/milestones/grader.py" "$MILESTONE" --solution-dir "$MILESTONE/buggy_solution" 2>&1
RC_GRADER_B=$?
set -e
echo "grader.py exit: $RC_GRADER_B"
if [ $RC_GRADER_B -ne 0 ]; then
  echo "[PASS] grader.py correctly reports FAIL for buggy impl"
else
  echo "[FAIL] grader.py should have reported FAIL"
  BRANCH_B="FAIL"
fi
echo ""

# ---------------------------------------------------------------------------
# Branch (c): STUDENT tests vs BUGGY implementation → must FAIL
# (6.031 mode: proves student tests are not vacuous)
# ---------------------------------------------------------------------------
echo "=== Branch (c): BUGGY solution vs STUDENT tests — expect FAIL ==="
set +e
OUT_C=$(PYTHONPATH="$MILESTONE/buggy_solution:${PYTHONPATH:-}" $PYTEST_BIN -q "$MILESTONE/student_tests" 2>&1)
RC_C=$?
set -e
echo "$OUT_C"
if [ $RC_C -ne 0 ]; then
  pass "Branch (c) PASS — student tests caught buggy impl (exit $RC_C)"
  BRANCH_C="PASS"
else
  fail "Branch (c) FAIL — student tests are vacuous (did not catch buggy impl, exit $RC_C)"
  BRANCH_C="FAIL"
fi
echo ""

# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------
echo "=== VERDICT ==="
echo "Branch (a) GOOD→PASS:        $BRANCH_A  (expected PASS; sub-check exit $RC_A == 0)"
echo "Branch (b) BUGGY→FAIL:       $BRANCH_B  (expected grader FAIL; sub-check exit $RC_B != 0)"
echo "Branch (c) STUDENT×BUGGY:    $BRANCH_C  (expected FAIL; sub-check exit $RC_C != 0)"
echo "pytest runtime: $PYTEST_RUNTIME"

if [ "$BRANCH_A" = "PASS" ] && [ "$BRANCH_B" = "PASS" ] && [ "$BRANCH_C" = "PASS" ]; then
  echo ""
  echo "All three branches behaved as expected — dual reverse-verification succeeded."
  exit 0
else
  echo ""
  echo "Self-check FAILED — one or more branches did not meet expected outcome."
  exit 1
fi
