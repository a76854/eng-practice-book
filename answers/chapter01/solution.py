"""week01 习题参考答案（hermetic 纯函数）。"""

from __future__ import annotations

import re
import tomllib


def parse_requires_python(pyproject_text: str) -> str:
    """从 pyproject.toml 文本中解析 project.requires-python，不存在则返回 ""。"""
    try:
        data = tomllib.loads(pyproject_text)
    except Exception:
        return ""
    val = data.get("project", {}).get("requires-python", "")
    return val if isinstance(val, str) else ""


def required_fields_present(pyproject_text: str) -> list[str]:
    """检查 project.name/version/requires-python/dependencies 是否齐全，返回缺失字段名列表。"""
    required = ["name", "version", "requires-python", "dependencies"]
    try:
        data = tomllib.loads(pyproject_text)
    except Exception:
        return required.copy()
    project = data.get("project", {}) if isinstance(data.get("project"), dict) else {}
    missing: list[str] = []
    for field in required:
        if field not in project:
            missing.append(field)
        else:
            v = project[field]
            # 空字符串 / 空列表视为缺失（更严格，符合教学预期）
            if v == "" or v == []:
                missing.append(field)
    return missing


_CONSTRAINT_RE = re.compile(
    r"""^\s*
    (
        \*                          # bare wildcard
        |
        (~=|==|!=|>=|<=|>|<)        # operator
        \s*
        \d+(\.\d+)*                 # version core
        (\.\*)?                     # trailing wildcard like 1.0.*
    )
    \s*$""",
    re.VERBOSE,
)


def normalize_version_constraint(s: str) -> bool:
    """判断字符串是否为合法的版本约束，合法返回 True。"""
    if not isinstance(s, str):
        return False
    s = s.strip()
    if not s:
        return False
    return bool(_CONSTRAINT_RE.match(s))


def parse_scripts(pyproject_text: str) -> dict[str, str]:
    """解析 [project.scripts] 段，返回 {命令名: \"模块:函数\"}，无则 {}。"""
    try:
        data = tomllib.loads(pyproject_text)
    except Exception:
        return {}
    scripts = data.get("project", {}).get("scripts", {})
    if not isinstance(scripts, dict):
        return {}
    # 只保留 str->str
    return {k: v for k, v in scripts.items() if isinstance(k, str) and isinstance(v, str)}


_DEP_NAME_RE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)")


def extract_dependency_names(pyproject_text: str) -> list[str]:
    """从 project.dependencies 中提取包名列表，保持原顺序。"""
    try:
        data = tomllib.loads(pyproject_text)
    except Exception:
        return []
    deps = data.get("project", {}).get("dependencies", [])
    if not isinstance(deps, list):
        return []
    names: list[str] = []
    for dep in deps:
        if not isinstance(dep, str):
            continue
        m = _DEP_NAME_RE.match(dep)
        if m:
            names.append(m.group(1))
    return names


def _parse_version_tuple(v: str) -> tuple[int, ...]:
    parts = v.strip().split(".")
    out: list[int] = []
    for p in parts:
        # 去掉可能的后缀如 "rc1" 只取数字前缀
        num = re.match(r"^\d+", p)
        if num:
            out.append(int(num.group(0)))
        else:
            out.append(0)
    return tuple(out)


def is_python_version_compatible(requires: str, version: str) -> bool:
    """判断给定版本是否满足约束。支持 >= > == <= < ~= *，或逗号分隔的多约束（与语义）。"""
    requires = requires.strip()
    version = version.strip()
    if not requires or not version:
        return False
    if requires == "*":
        return True
    v_tuple = _parse_version_tuple(version)
    # 逗号分隔视为 AND
    constraints = [c.strip() for c in requires.split(",") if c.strip()]
    for c in constraints:
        if c == "*":
            continue
        m = re.match(r"^(~=|==|!=|>=|<=|>|<)\s*(\d+(?:\.\d+)*)", c)
        if not m:
            return False
        op, ver_str = m.group(1), m.group(2)
        c_tuple = _parse_version_tuple(ver_str)
        # 归一化长度补零比较
        max_len = max(len(v_tuple), len(c_tuple))
        vt = v_tuple + (0,) * (max_len - len(v_tuple))
        ct = c_tuple + (0,) * (max_len - len(c_tuple))
        if op == "==":
            if vt != ct:
                return False
        elif op == "!=":
            if vt == ct:
                return False
        elif op == ">=":
            if vt < ct:
                return False
        elif op == "<=":
            if vt > ct:
                return False
        elif op == ">":
            if vt <= ct:
                return False
        elif op == "<":
            if vt >= ct:
                return False
        elif op == "~=":
            # ~=2.2 等价于 >=2.2, ==2.*
            # ~=1.4.5 等价于 >=1.4.5, ==1.4.*
            # 通用：前缀除最后一段必须相等，且 >=
            if vt < ct:
                return False
            # 前缀比较：requires 的除最后一段外的前缀必须与 version 相同
            c_parts = ver_str.split(".")
            v_parts = version.split(".")
            # 取 c 长度 -1 作为前缀长度
            prefix_len = len(c_parts) - 1
            if prefix_len > 0:
                if _parse_version_tuple(".".join(v_parts[:prefix_len])) != _parse_version_tuple(
                    ".".join(c_parts[:prefix_len])
                ):
                    return False
            else:
                # ~=2 这种，major 必须相等
                if v_parts[0] != c_parts[0]:
                    return False
        else:
            return False
    return True
