"""week02 习题参考答案（hermetic 纯函数，镜像 Shell 概念）。"""

from __future__ import annotations

import glob as globlib
import os
import re as _re
import shlex

re_error = _re.error


def glob_audio_files(directory: str, pattern: str = "*.wav") -> list[str]:
    """返回按字典序排序的匹配路径；目录不存在返回 []。"""
    if not isinstance(directory, str) or not isinstance(pattern, str):
        return []
    if not os.path.isdir(directory):
        return []
    # 避免 pattern 含路径分隔符时越权，仅做简单拼接
    full = os.path.join(directory, pattern)
    try:
        matched = globlib.glob(full)
    except re_error:
        return []
    except Exception:
        return []
    # 只保留文件（与 Shell glob 行为对齐，目录不应计入音频）
    files = [p for p in matched if os.path.isfile(p)]
    return sorted(files)


def filter_by_ext(paths: list[str], ext: str) -> list[str]:
    """按扩展名过滤，ext 可带或不带点，大小写不敏感。"""
    if not isinstance(paths, list) or not isinstance(ext, str):
        return []
    ext = ext.strip()
    if not ext:
        return []
    if not ext.startswith("."):
        ext = f".{ext}"
    ext = ext.lower()
    out: list[str] = []
    for p in paths:
        if not isinstance(p, str):
            continue
        _, e = os.path.splitext(p)
        if e.lower() == ext:
            out.append(p)
    return out


def parse_find_output(lines: list[str]) -> list[str]:
    """对 find 每行输出做 strip、去空行、去重后按字典序返回。"""
    if not isinstance(lines, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for raw in lines:
        if not isinstance(raw, str):
            continue
        s = raw.strip()
        if not s:
            continue
        if s not in seen:
            seen.add(s)
            out.append(s)
    return sorted(out)


def count_by_extension(paths: list[str]) -> dict[str, int]:
    """统计扩展名出现次数（小写归一，无扩展名记 \"\"）。"""
    if not isinstance(paths, list):
        return {}
    from collections import Counter

    exts: list[str] = []
    for p in paths:
        if not isinstance(p, str):
            continue
        _, e = os.path.splitext(p)
        exts.append(e.lower())
    return dict(Counter(exts))


def build_transcribe_commands(
    wav_files: list[str], out_dir: str | None = None
) -> list[str]:
    """为每个文件生成 meetingtotext transcribe 命令；out_dir 非空则追加重定向。"""
    if not isinstance(wav_files, list):
        return []
    cmds: list[str] = []
    for f in wav_files:
        if not isinstance(f, str) or not f:
            continue
        base_cmd = f"meetingtotext transcribe {shlex.quote(f)}"
        if out_dir is not None and isinstance(out_dir, str) and out_dir.strip():
            od = out_dir.strip().rstrip("/")
            base = os.path.splitext(os.path.basename(f))[0]
            # 空 base（如文件名无 basename）回退为 "output"
            if not base:
                base = "output"
            out_path = f"{od}/{base}.txt"
            base_cmd = f"{base_cmd} > {shlex.quote(out_path)}"
        cmds.append(base_cmd)
    return cmds


def jq_extract(records: list[dict], key: str) -> list:
    """从每条 dict 提取 key 对应的值，支持点号路径如 \"a.b\"，缺失跳过。"""
    if not isinstance(records, list) or not isinstance(key, str) or not key.strip():
        return []
    parts = key.strip().split(".")
    out: list = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        cur: object = rec
        found = True
        for part in parts:
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                found = False
                break
        if found:
            out.append(cur)
    return out
