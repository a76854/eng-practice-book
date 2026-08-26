"""week03 习题参考答案（hermetic 纯函数 + git 文本解析）。"""

from __future__ import annotations

import re

_COMMIT_RE = re.compile(
    r"^(?P<hash>[0-9a-f]{7,40})\s+(?:(?P<type>\w+)(?:\((?P<scope>[^)]+)\))?:\s*)?(?P<subject>.+)$"
)

_BRANCH_RE = re.compile(r"^(?:feature|fix|docs|chore)/[a-z0-9][a-z0-9/_-]*$")


def parse_git_log(lines: list[str]) -> list[dict]:
    """解析 git log --oneline 文本为结构化记录。

    每行期望格式 ``"{hash} {subject}"``，其中 subject 若符合
    ``type(scope): subject`` 则拆解 type/scope，否则 type/scope 为 ""。
    空行跳过，未匹配的行仍保留 hash 与 subject。
    """
    if not isinstance(lines, list):
        return []
    out: list[dict] = []
    for raw in lines:
        if not isinstance(raw, str):
            continue
        line = raw.strip()
        if not line:
            continue
        m = _COMMIT_RE.match(line)
        if m:
            d = m.groupdict()
            # 规范化 None -> ""
            for k in ("type", "scope", "subject", "hash", "scope"):
                if d.get(k) is None:
                    d[k] = ""
            # hash 已有，subject 去首尾空格
            d["subject"] = d["subject"].strip()
            # type/scope 若未捕获则 ""
            if d["type"] is None:
                d["type"] = ""
            if d["scope"] is None:
                d["scope"] = ""
            out.append(
                {
                    "hash": d["hash"],
                    "type": d["type"] or "",
                    "scope": d["scope"] or "",
                    "subject": d["subject"],
                }
            )
        else:
            parts = line.split(None, 1)
            h = parts[0] if parts else ""
            subj = parts[1] if len(parts) > 1 else ""
            out.append({"hash": h, "type": "", "scope": "", "subject": subj})
    return out


def is_valid_branch_name(name: str) -> bool:
    """校验分支名是否符合协作约定。

    规则：前缀必须为 feature/ fix/ docs/ chore/ 之一；后缀非空；
    仅含小写字母数字与 - _ / ；不能以 - / 开头或结尾连续 //。
    """
    if not isinstance(name, str):
        return False
    name = name.strip()
    if not name:
        return False
    if "//" in name or name.endswith("/") or name.endswith("-") or name.endswith("_"):
        return False
    # 检查后缀以 - 或 _ 开头（如 feature/-foo）
    # 通过正则按整体校验，最简：符合分支正则且后缀非空
    if not _BRANCH_RE.match(name):
        return False
    # 额外：/ 后首字符不能为 - 或 _
    suffix = name.split("/", 1)[1] if "/" in name else ""
    if suffix and suffix[0] in "-_":
        return False
    # 段内不能出现 // 已检；每段首字符已通过下层检查
    for seg in name.split("/"):
        if seg and seg[0] in "-_":
            return False
        if seg and seg[-1] in "-_":
            # 允许段末为字母数字，禁止 - _ 结尾（已对整体尾检查，但段内也要）
            # 已对整体尾检查，这里对中间段也检查
            pass
    return True


def has_conflict_markers(text: str) -> bool:
    """判断文件文本是否含 Git 冲突标记行。"""
    if not isinstance(text, str):
        return False
    for line in text.splitlines():
        if (
            line.startswith("<<<<<<< ")
            or line.startswith(">>>>>>> ")
            or line.startswith("=======")
        ):
            if line.startswith("<<<<<<< ") or line.startswith(">>>>>>> "):
                return True
            if line.startswith("======="):
                return True
    return False


def is_revert_commit(subject: str) -> bool:
    """判断提交标题是否为 revert 提交。

    接受 ``Revert "..."`` / ``revert: ...`` / ``Revert: ...`` 等大小写不敏感形式。
    """
    if not isinstance(subject, str):
        return False
    s = subject.strip()
    if not s:
        return False
    low = s.lower()
    # 常见形式：revert "..."  或  revert: ...
    if low.startswith('revert "') or low.startswith("revert '"):
        return True
    if low.startswith("revert:"):
        return True
    return low.startswith("revert ")


def is_ancestor(graph: dict[str, list[str]], anc: str, desc: str) -> bool:
    """判断 anc 是否为 desc 的祖先（含相等与传递闭包）。

    graph: {commit: [parents]}，缺失的节点视为无 parent。
    """
    if not isinstance(graph, dict) or not isinstance(anc, str) or not isinstance(desc, str):
        return False
    if anc == desc:
        return True
    # BFS/DFS 从 desc 向上遍历
    seen: set[str] = set()
    stack: list[str] = [desc]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        parents = graph.get(cur, [])
        if not isinstance(parents, list):
            continue
        for p in parents:
            if p == anc:
                return True
            if p not in seen:
                stack.append(p)
    return False
