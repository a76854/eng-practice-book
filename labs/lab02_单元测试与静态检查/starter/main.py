"""Lab02 starter: functions under test + runnable demo.

Run:
  python main.py            # demo output
  python main.py --help     # help

Students will add pytest cases for the functions below
and configure mypy Ruff to strict level.
"""

from __future__ import annotations

import argparse
import pathlib


def format_duration(seconds: int) -> str:
    """Format seconds as H:MM:SS or M:SS.

    Examples:
      0 -> "0:00"
      65 -> "1:05"
      3661 -> "1:01:01"
    """
    if not isinstance(seconds, int):
        raise TypeError("seconds must be int")
    if seconds < 0:
        raise ValueError("seconds must be non-negative")
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def normalize_text(text: str) -> str:
    """Normalize whitespace and strip leading/trailing spaces.

    Collapses consecutive whitespace into a single space.
    Returns empty string for whitespace-only input.
    """
    if not isinstance(text, str):
        raise TypeError("text must be str")
    return " ".join(text.split())


def chunk_list(items: list[int], size: int) -> list[list[int]]:
    """Split list into chunks of given size.

    The last chunk may be smaller. Raises ValueError for invalid size.
    """
    if not isinstance(size, int):
        raise TypeError("size must be int")
    if size <= 0:
        raise ValueError("size must be positive")
    return [items[i : i + size] for i in range(0, len(items), size)]


def write_summary(path: str | pathlib.Path, lines: list[str]) -> pathlib.Path:
    """Write lines to a file, one per line. Returns the path.

    Minimal I/O helper for fixture/mocking exercises.
    """
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lab02-starter",
        description="Lab02 starter: functions under test demo",
    )
    parser.add_argument("--demo", action="store_true", help="run demo (default)")
    args = parser.parse_args(argv)
    _ = args

    print("format_duration(0)      ->", format_duration(0))
    print("format_duration(65)     ->", format_duration(65))
    print("format_duration(3661)   ->", format_duration(3661))
    print("normalize_text('  hi   there ') ->", repr(normalize_text("  hi   there ")))
    print("chunk_list([1,2,3,4,5], 2) ->", chunk_list([1, 2, 3, 4, 5], 2))
    tmp = pathlib.Path("summary_demo.txt")
    # Demo I/O: students should replace with tmp_path fixture in tests
    write_summary(tmp, ["hello", "world"])
    print(f"wrote {tmp} ({tmp.read_text(encoding='utf-8').count(chr(10))} lines)")
    tmp.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
