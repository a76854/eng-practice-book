#!/usr/bin/env python3
"""扫描 book/**/*.md，校验 STYLE.md §4 定义的反 AI 味负面模式。

两类规则：
  红线（RED）  —— 0 容忍，正文出现即违规；
  频次（FREQ） —— 按单个文件计数，超过上限即违规。

只统计正文：跳过 frontmatter、代码围栏（含 code-cell）、行内代码、
HTML 注释，并忽略加粗/斜体标记本身。

用法：
  python scripts/check_style.py            # 详细报告，有违规退出码 1
  python scripts/check_style.py --summary  # 只输出超标文件汇总表
  python scripts/check_style.py --only red # 只查红线

退出码：0 = 全部通过；1 = 存在违规；2 = 参数或路径错误。
与 `myst build --html --execute --strict` 同为交稿门禁。
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BOOK_DIR = REPO_ROOT / "book"

# 扫描时跳过的文件（契约文件本身收录了负面示例，不能计入）
EXCLUDED_FILES = {"STYLE.md"}
EXCLUDED_DIR_PARTS = {"node_modules", "_build", ".venv"}

# ---------------------------------------------------------------- 红线规则 ----
# (规则名, 正则, 违规说明)
RED_RULES: list[tuple[str, str, str]] = [
    ("破折号", r"——", "不使用破折号“——”，改为逗号、冒号或拆句"),
    ("直角引号", r"[「」]", "正文引用一律用弯双引号“”"),
    ("感叹号", r"！", "正文不使用感叹号（代码注释在围栏内，不计）"),
    ("emoji", r"[☀-➿⬀-⯿\U0001F000-\U0001FAFF️]", "不用 emoji"),
    (
        "口语化用词",
        r"咱们|大家|其实|说白了|翻车|玄学|人肉|帮手|闭门造车",
        "不用口语化表达与网络用语",
    ),
    (
        "可X可Y 堆叠",
        # 形如 “可重放、可回滚”“可测试与可替换”“可靠不等于产品可用”；
        # 双侧 lookaround 排除 “不可”“可能”“可以”“可是” 等正常用法
        r"(?<![不])可(?![能是以不])[^，。；、\n）\"]{1,8}[、与，]\s*可(?![能是以不])"
        r"|(?<![不])可(?![能是以不])[^，。；、\n）\"]{1,6}可(?![能是以不])",
        "不用“可 X、可 Y”式能力词堆叠，改为动词或具体表述",
    ),
    (
        "抽象品质连排",
        # 每项都带定语（的/得/过）的顿号链，如“校验过的输入、可信的身份、有界的重试”；
        # 真实 taxonomy（“插值、属性绑定、事件绑定”）各项不带定语，不会命中
        r"(?:[一-鿿]{0,4}(?:的|得|过)[一-鿿]{1,5}、){2,}"
        r"[一-鿿]{0,4}(?:的|得|过)[一-鿿]{1,5}",
        "带定语的抽象品质顿号连排至多 2 项，3 项起为堆叠，改为具体表述或拆句",
    ),
]

# ------------------------------------------------------------ 频次上限规则 ----
# (规则号, 规则名, 正则, 每文件上限, 违规说明)
# 上限含义：单文件内出现次数 <= limit 为通过。
FREQ_RULES: list[tuple[str, str, str, int, str]] = [
    (
        "A",
        "对仗反转",
        r"不[^。；！？\n]{0,40}而是",
        1,
        "“不……而是……”对仗反转每文件至多 1 次，段段反转是典型 AI 修辞",
    ),
    (
        "B",
        "本质化收束",
        r"本质(?:上)?(?:是|在于|就是)",
        1,
        "“本质是/本质上是/本质在于”每文件至多 1 次，避免句句下定义",
    ),
    (
        "C",
        "升华钩子",
        r"这正是",
        1,
        "“这正是……”每文件至多 1 次，段末升华要克制",
    ),
    (
        "D",
        "数字排比标题",
        r"^#{1,6}\s+.*(?<!第)[二三四五六七八九十两3-9][种个条笔层重心张份]",
        1,
        "“N 种/N 个/N 条”式排比标题每文件至多 1 个（“第 N 步”步骤序列不计）",
    ),
    (
        "E",
        "拟人比喻",
        r"第[一二三四五]笔债|旧账|人走茶凉|看门人|逼出来|难以为继|登场|敲门|住下|穿针引线",
        2,
        "拟人/口语比喻每文件至多 2 处，比喻要克制",
    ),
    (
        "F",
        "长顿号链",
        r"(?:[一-鿿]{3,7}、){3,}[一-鿿]{3,7}",
        1,
        "4 项以上的顿号列举每文件至多 1 处，同文件反复长链列举是生成式文风",
    ),
]

EMPHASIS_RE = re.compile(r"\*\*|__|(?<!\w)\*|\*(?!\w)")
INLINE_CODE_RE = re.compile(r"`[^`]*`")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


@dataclass
class Hit:
    line: int
    text: str


@dataclass
class FileReport:
    path: Path
    red: dict[str, list[Hit]] = field(default_factory=dict)
    freq: dict[str, list[Hit]] = field(default_factory=dict)  # 规则号 -> 命中

    @property
    def red_total(self) -> int:
        return sum(len(v) for v in self.red.values())

    @property
    def freq_breaches(self) -> dict[str, list[Hit]]:
        out: dict[str, list[Hit]] = {}
        for rule_no, hits in self.freq.items():
            limit = next(r[3] for r in FREQ_RULES if r[0] == rule_no)
            if len(hits) > limit:
                out[rule_no] = hits
        return out

    @property
    def has_violation(self) -> bool:
        return self.red_total > 0 or bool(self.freq_breaches)


def iter_prose_lines(path: Path):
    """产出 (行号, 正文文本)。跳过 frontmatter、围栏、行内代码、注释。"""
    lines = path.read_text(encoding="utf-8").splitlines()

    start = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                start = i + 1
                break

    in_fence = False
    for idx in range(start, len(lines)):
        line = lines[idx]
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        prose = HTML_COMMENT_RE.sub("", line)
        prose = INLINE_CODE_RE.sub("", prose)
        prose = EMPHASIS_RE.sub("", prose)
        yield idx + 1, prose


def scan_file(path: Path) -> FileReport:
    report = FileReport(path=path)
    for lineno, prose in iter_prose_lines(path):
        if not prose.strip():
            continue
        for name, pattern, _msg in RED_RULES:
            for m in re.finditer(pattern, prose):
                report.red.setdefault(name, []).append(Hit(lineno, m.group(0)))
        for rule_no, _name, pattern, _limit, _msg in FREQ_RULES:
            for m in re.finditer(pattern, prose):
                report.freq.setdefault(rule_no, []).append(
                    Hit(lineno, m.group(0).strip())
                )
    return report


def scan(book_dir: Path) -> list[FileReport]:
    reports = []
    for path in sorted(book_dir.rglob("*.md")):
        if path.name in EXCLUDED_FILES:
            continue
        if any(part in EXCLUDED_DIR_PARTS for part in path.parts):
            continue
        reports.append(scan_file(path))
    return reports


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def print_detail(reports: list[FileReport]) -> None:
    red_msgs = {name: msg for name, _p, msg in RED_RULES}
    freq_meta = {no: (name, limit, msg) for no, name, _p, limit, msg in FREQ_RULES}

    for rep in reports:
        if not rep.has_violation:
            continue
        print(f"\n{rel(rep.path)}")
        for name, hits in rep.red.items():
            print(f"  [红线·{name}] {len(hits)} 处 —— {red_msgs[name]}")
            for h in hits:
                print(f"      L{h.line}  {h.text}")
        for rule_no, hits in rep.freq_breaches.items():
            name, limit, msg = freq_meta[rule_no]
            locs = ", ".join(f"L{h.line}" for h in hits)
            print(
                f"  [频次·{rule_no} {name}] {len(hits)} > {limit} —— {msg}"
            )
            print(f"      位置：{locs}")


def print_summary(reports: list[FileReport]) -> None:
    red_total = sum(r.red_total for r in reports)
    freq_files = [r for r in reports if r.freq_breaches]
    red_files = [r for r in reports if r.red_total]
    print("红线违规：")
    by_rule: dict[str, int] = {}
    for r in reports:
        for name, hits in r.red.items():
            by_rule[name] = by_rule.get(name, 0) + len(hits)
    if by_rule:
        for name in sorted(by_rule, key=lambda n: -by_rule[n]):
            print(f"  {name:<8} {by_rule[name]:>4} 处 / "
                  f"{sum(1 for r in reports if name in r.red)} 个文件")
    else:
        print("  无")
    print("频次超标：")
    if freq_files:
        for r in sorted(freq_files, key=lambda r: -len(r.freq_breaches)):
            breaches = ", ".join(
                f"{no}×{len(h)}" for no, h in r.freq_breaches.items()
            )
            print(f"  {rel(r.path):<70} {breaches}")
    else:
        print("  无")
    print(
        f"\n合计：红线 {red_total} 处 / {len(red_files)} 个文件；"
        f"频次超标 {len(freq_files)} 个文件；"
        f"扫描 {len(reports)} 个文件"
    )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="STYLE.md 反 AI 味模式扫描")
    parser.add_argument("--book", type=Path, default=DEFAULT_BOOK_DIR,
                        help="正文目录（默认 book/）")
    parser.add_argument("--summary", action="store_true",
                        help="只输出汇总表")
    parser.add_argument("--only", choices=["red", "freq"], default=None,
                        help="只查红线或只查频次")
    args = parser.parse_args(argv)

    if not args.book.is_dir():
        print(f"错误：目录不存在 {args.book}", file=sys.stderr)
        return 2

    reports = scan(args.book)
    if args.only == "red":
        for r in reports:
            r.freq.clear()
    elif args.only == "freq":
        for r in reports:
            r.red.clear()

    if args.summary:
        print_summary(reports)
    else:
        print_detail(reports)
        print_summary(reports)

    return 1 if any(r.has_violation for r in reports) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
