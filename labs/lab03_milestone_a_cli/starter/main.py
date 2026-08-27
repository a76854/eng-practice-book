"""Lab03 starter: CLI 音频转写工具骨架。

为什么是子命令：MeetingToText 后续会有 serve、transcribe 等多个入口，
子命令能让“转写”与“服务”在同一入口下共存，且各自的帮助信息独立清晰。

设计约束：
  - 只依赖标准库 argparse + pathlib，不引入 Web 框架。
  - 业务逻辑抽成 transcribe_file 纯函数，便于被 import 复用。
  - 可只读复用 m2t.audio / m2t.asr，starter 本身保持可运行占位。

Run:
  python main.py --help
  python main.py transcribe --help
  python main.py transcribe sample.wav --out result.txt
  python main.py info
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ALLOWED_FORMATS = ("txt", "srt", "md")
ALLOWED_EXTENSIONS = (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm")


def transcribe_file(audio_path: str | Path, *, language: str | None = None) -> str:
    """转写核心函数，接收音频路径返回文本。

    当前为占位实现，保证骨架可运行。学生在实验中应在此替换为
    只读复用 m2t.audio / m2t.asr 的真实逻辑。

    参数:
        audio_path: 音频文件路径
        language: 可选语言标识，透传给后续 ASR

    返回:
        转写文本，骨架阶段回显路径信息。

    异常:
        FileNotFoundError: 路径不存在时抛出
        ValueError: 格式不支持时抛出
    """
    _ = language
    p = Path(audio_path)
    if not p.exists():
        raise FileNotFoundError(f"audio not found: {p}")
    if p.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(f"unsupported audio format: {p.suffix} (allowed: {', '.join(ALLOWED_EXTENSIONS)})")

    # 尝试只读复用 m2t，若不可用则回退到占位文本
    try:
        from m2t.audio import load_audio  # type: ignore[import-not-found]

        samples, sr = load_audio(str(p))
        # 占位：真实实验中在此做 resample 与 ASR 调用
        return f"[placeholder] loaded {p.name}: {len(samples)} samples at {sr}Hz"
    except ImportError:
        return f"[placeholder] transcribe {p.name} (m2t not installed, skeleton output)"
    except Exception as exc:
        # 音频读取失败时给出可读回退，不直接抛堆栈
        return f"[placeholder] transcribe {p.name} (load failed: {exc})"


def format_transcript(text: str, fmt: str) -> str:
    """按格式包装文本，骨架阶段做最小包装。"""
    if fmt == "srt":
        return f"1\n00:00:00,000 --> 00:00:05,000\n{text}\n"
    if fmt == "md":
        return f"# Transcript\n\n{text}\n"
    return text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lab03-starter",
        description="Lab03 starter: CLI audio transcription tool (milestone A)",
    )
    sub = parser.add_subparsers(dest="command", required=False, help="subcommands")

    # transcribe 子命令
    p_trans = sub.add_parser("transcribe", help="transcribe an audio file")
    p_trans.add_argument("audio", help="path to audio file (wav/mp3/m4a/flac/ogg/webm)")
    p_trans.add_argument("--out", dest="out", default=None, help="output file path (default: <audio>.<format>)")
    p_trans.add_argument(
        "--format",
        dest="format",
        choices=ALLOWED_FORMATS,
        default="txt",
        help="output format: txt/srt/md (default: txt)",
    )
    p_trans.add_argument("--language", default=None, help="optional language hint (e.g. zh, en)")
    p_trans.add_argument("--verbose", action="store_true", help="enable verbose output")

    # info 子命令
    p_info = sub.add_parser("info", help="show environment and m2t availability")
    p_info.add_argument("--verbose", action="store_true", help="verbose output")

    return parser


def _handle_transcribe(args: argparse.Namespace) -> int:
    audio = args.audio
    fmt: str = args.format
    out: str | None = args.out
    verbose: bool = args.verbose

    try:
        text = transcribe_file(audio, language=args.language)
    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    formatted = format_transcript(text, fmt)

    if out is None:
        base = Path(audio).stem
        # 默认输出到当前目录，避免与输入同目录的写权限问题
        out = f"{base}.{fmt}"

    out_path = Path(out)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(formatted, encoding="utf-8")
    except OSError as exc:
        print(f"[error] cannot write {out_path}: {exc}", file=sys.stderr)
        return 1

    if verbose:
        print(f"[info] wrote {out_path} ({len(formatted)} chars, format={fmt})")
    else:
        print(f"wrote {out_path}")
    return 0


def _handle_info(args: argparse.Namespace) -> int:
    print(f"python: {sys.version.split()[0]}")
    print(f"prefix: {sys.prefix}")
    print(f"allowed formats: {', '.join(ALLOWED_FORMATS)}")
    print(f"allowed audio: {', '.join(ALLOWED_EXTENSIONS)}")
    try:
        import m2t  # type: ignore[import-not-found]

        print(f"m2t: {m2t.__version__} ({m2t.__file__})")
    except ImportError:
        print("m2t: not installed (skeleton still runnable)")
    if args.verbose:
        print(f"argv: {sys.argv}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "transcribe":
        return _handle_transcribe(args)
    if args.command == "info":
        return _handle_info(args)

    # 无子命令时打印帮助，保持与实验一和实验二一致的 --help 语义
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
