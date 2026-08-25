"""week03 习题测试（≥5，含 tmp_path 真 git 冲突断言）。"""

from __future__ import annotations

import subprocess
import sys

import pytest

from solution import (
    has_conflict_markers,
    is_ancestor,
    is_revert_commit,
    is_valid_branch_name,
    parse_git_log,
)

# ---------------------------------------------------------------------------
# hermetic 题
# ---------------------------------------------------------------------------


def test_parse_git_log_conventional():
    lines = [
        "a1b2c3d docs(week03): add feature branch demo",
        "e4f5a6b fix(store): handle WAL lock",
    ]
    recs = parse_git_log(lines)
    assert recs[0]["hash"] == "a1b2c3d"
    assert recs[0]["type"] == "docs"
    assert recs[0]["scope"] == "week03"
    assert recs[0]["subject"] == "add feature branch demo"
    assert recs[1]["type"] == "fix"


def test_parse_git_log_without_conventional():
    lines = ["abc1234 Merge branch 'feature/a' into main"]
    recs = parse_git_log(lines)
    assert recs[0]["hash"] == "abc1234"
    assert recs[0]["subject"] == "Merge branch 'feature/a' into main"
    # 无 type/scope 拆解时为空
    assert recs[0]["type"] == ""
    assert recs[0]["scope"] == ""


def test_parse_git_log_empty_and_invalid():
    assert parse_git_log([]) == []
    assert parse_git_log(["   ", ""]) == []
    recs = parse_git_log(["not-a-valid-log-line"])
    # 仍保留 hash/subject 兜底
    assert len(recs) == 1
    assert recs[0]["hash"] == "not-a-valid-log-line"


def test_is_valid_branch_name_ok():
    assert is_valid_branch_name("feature/week03-demo") is True
    assert is_valid_branch_name("fix/bug-123") is True
    assert is_valid_branch_name("docs/style_guide") is True
    assert is_valid_branch_name("chore/init") is True
    assert is_valid_branch_name("feature/a_b-c/d_e") is True


def test_is_valid_branch_name_bad():
    assert is_valid_branch_name("") is False
    assert is_valid_branch_name("Feature/week03") is False  # 大写
    assert is_valid_branch_name("hotfix/bug") is False  # 非法前缀
    assert is_valid_branch_name("feature/") is False  # 后缀空
    assert is_valid_branch_name("feature//a") is False
    assert is_valid_branch_name("feature/-bad") is False
    assert is_valid_branch_name("week03-demo") is False  # 无前缀


def test_has_conflict_markers_true():
    text = "line1\n<<<<<<< HEAD\nhello from main\n=======\nhello from a\n>>>>>>> feature/a\nline2\n"
    assert has_conflict_markers(text) is True


def test_has_conflict_markers_false():
    assert has_conflict_markers("hello\nworld\n") is False
    assert has_conflict_markers("") is False
    # 只是包含箭头但非标记行
    assert has_conflict_markers("value <<<<<<< not a marker\n") is False


def test_is_revert_commit_true():
    assert is_revert_commit('Revert "docs(week03): add demo"') is True
    assert is_revert_commit("revert: fix bug") is True
    assert is_revert_commit("Revert: chore init") is True
    assert is_revert_commit('revert "feat: bad"') is True


def test_is_revert_commit_false():
    assert is_revert_commit("docs(week03): add demo") is False
    assert is_revert_commit("") is False
    assert is_revert_commit("fix: revert logic") is False  # 中间含 revert 非前缀


def test_is_ancestor_basic():
    graph = {
        "c0": [],
        "c1": ["c0"],
        "c2": ["c1"],
        "c3": ["c1"],
        "c4": ["c2", "c3"],
    }
    assert is_ancestor(graph, "c0", "c4") is True
    assert is_ancestor(graph, "c1", "c2") is True
    assert is_ancestor(graph, "c2", "c3") is False
    assert is_ancestor(graph, "c4", "c4") is True  # 相等视为是
    assert is_ancestor(graph, "c3", "c2") is False


def test_is_ancestor_missing_node():
    graph: dict[str, list[str]] = {"a": []}
    assert is_ancestor(graph, "a", "b") is False
    assert is_ancestor(graph, "b", "a") is False


# ---------------------------------------------------------------------------
# 真 git 题（tmp_path + subprocess）
# ---------------------------------------------------------------------------


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True, timeout=5)
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _git_available(), reason="git not available")
def test_git_merge_conflict_markers(tmp_path):
    """在 tmp_path 建临时仓库，复现 merge 冲突并断言冲突标记。"""
    repo = tmp_path / "repo"
    repo.mkdir()

    def run(*args: str, check: bool = True):
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            check=check,
            timeout=10,
        )

    run("init", "-b", "main")
    run("config", "user.email", "test@example.com")
    run("config", "user.name", "Test")
    # 初始提交
    (repo / "demo.txt").write_text("line: base\n", encoding="utf-8")
    run("add", "demo.txt")
    run("commit", "-m", "chore: init")
    # 分支 a
    run("switch", "-c", "feature/a")
    (repo / "demo.txt").write_text("line: hello from a\n", encoding="utf-8")
    run("add", "demo.txt")
    run("commit", "-m", "feat: add line from a")
    # 回 main 改同一行
    run("switch", "main")
    (repo / "demo.txt").write_text("line: hello from main\n", encoding="utf-8")
    run("add", "demo.txt")
    run("commit", "-m", "feat: add line from main")
    # 合并应冲突
    result = run("merge", "feature/a", check=False)
    assert result.returncode != 0
    combined = (result.stdout or "") + (result.stderr or "")
    assert "CONFLICT" in combined or "conflict" in combined.lower()
    status = run("status", "--porcelain")
    assert "UU" in status.stdout or "both modified" in status.stdout or "demo.txt" in status.stdout
    content = (repo / "demo.txt").read_text(encoding="utf-8")
    assert has_conflict_markers(content) is True
    assert "<<<<<<<" in content
    assert "=======" in content
    assert ">>>>>>>" in content
    # 清理：abort 合并，避免 tmp_path 残留冲突状态（pytest 回收目录即可）
    run("merge", "--abort", check=False)


@pytest.mark.skipif(not _git_available(), reason="git not available")
def test_git_revert_creates_new_commit(tmp_path):
    """验证 git revert 新增提交而非改写历史。"""
    repo = tmp_path / "repo2"
    repo.mkdir()

    def run(*args: str, check: bool = True):
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            check=check,
            timeout=10,
        )

    run("init", "-b", "main")
    run("config", "user.email", "test@example.com")
    run("config", "user.name", "Test")
    (repo / "file.txt").write_text("v1\n", encoding="utf-8")
    run("add", "file.txt")
    run("commit", "-m", "chore: init")
    (repo / "file.txt").write_text("v2 bad\n", encoding="utf-8")
    run("add", "file.txt")
    run("commit", "-m", "feat: bad change")
    bad_hash = run("rev-parse", "HEAD").stdout.strip()
    # revert
    run("revert", "--no-edit", bad_hash)
    log = run("log", "--oneline", "-n", "3").stdout
    assert 'Revert "feat: bad change"' in log or "Revert" in log
    # 原 bad 提交仍在历史中
    log_all = run("log", "--oneline").stdout
    assert "feat: bad change" in log_all
    # 工作区已回到 v1
    assert (repo / "file.txt").read_text(encoding="utf-8") == "v1\n"
    # 用 is_revert_commit 校验新增提交标题
    latest_subject = run("log", "--format=%s", "-n", "1").stdout.strip()
    assert is_revert_commit(latest_subject) is True
    # 用 parse_git_log 解析 log 文本
    lines = log_all.strip().splitlines()
    recs = parse_git_log(lines)
    assert any(r["type"].lower() == "revert" or "Revert" in r["subject"] for r in recs)
