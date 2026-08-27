"""Lab01 starter: minimal runnable entry with argparse + subprocess.

Usage:
  python main.py --help
  python main.py --name World
  python main.py --check
  python main.py --verbose --name Alice
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lab01-starter",
        description="Lab01 starter: project bootstrap and automation demo",
    )
    parser.add_argument("--name", default="World", help="name to greet (default: World)")
    parser.add_argument("--check", action="store_true", help="run a subprocess check (git --version)")
    parser.add_argument("--verbose", action="store_true", help="enable verbose output")
    return parser


def run_check(verbose: bool = False) -> int:
    """Run a harmless subprocess call without shell=True."""
    cmd = [sys.executable, "--version"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = (result.stdout or result.stderr).strip()
        if verbose:
            print(f"[check] {' '.join(cmd)} -> {output}")
        else:
            print(output)
        return 0
    except FileNotFoundError as exc:
        print(f"[error] executable not found: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"[error] command failed ({exc.returncode}): {exc}", file=sys.stderr)
        return exc.returncode or 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.verbose:
        print(f"[info] hello, {args.name} (verbose on)")

    if args.check:
        return run_check(verbose=args.verbose)

    print(f"hello, {args.name}")
    if args.verbose:
        print(f"[info] python: {sys.version.split()[0]}")
        print(f"[info] prefix: {sys.prefix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
