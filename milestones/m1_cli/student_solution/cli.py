"""m2tc — M1 CLI 转写工具参考解（教学精简版）。

思路对齐 MeetingToText/cli.py:_cmd_transcribe（校验→解析输出路径→m2t.asr→m2t.export→写文件），
但**不逐字复制**、不依赖后端 DB/pipeline，仅用 m2t 教学包完成 hermetic 转写。

不实现 ASR 本体，走 m2t.asr（教学环境用 mock / fake 模型）。
"""

from __future__ import annotations

import argparse
import os
import sys

# 与 MeetingToText/backend/app/routers/upload.py:ALLOWED_EXTENSIONS 对齐的子集
# 至少包含 .wav，满足任务「坏扩展」探针
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm"}
ALLOWED_FORMATS = {"txt", "srt", "md"}

# 确定性 fake 原始结果，覆盖 m2t.asr.normalize_result 的形状 1（sentence_info 带说话人）
_FAKE_RAW_RESULT: list[dict] = [
    {
        "sentence_info": [
            {"text": "大家好，我们开始开会。", "start": 0, "end": 1200, "spk": 0},
            {"text": "好的，我先汇报一下进度。", "start": 1500, "end": 3000, "spk": 1},
        ]
    }
]


class _FakeModel:
    """确定性 fake 模型：实现 FunASR 的 generate 签名，返回固定形状。"""

    def generate(self, input: str, cache: dict | None = None, language: str = "auto", use_itn: bool = True, **kwargs):  # noqa: ANN001, ARG002
        # 忽略 input 路径，始终返回固定 FAKE_RAW_RESULT 的拷贝，避免调用方可变
        return [dict(item) for item in _FAKE_RAW_RESULT]


def _create_fake_model() -> _FakeModel:
    return _FakeModel()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="m2tc",
        description="m2tc — 读取音频文件，经 m2t.asr 转写，输出 txt/srt/md（教学 fake 模型离线可用）",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    transcribe_parser = subparsers.add_parser(
        "transcribe",
        help="转写单个音频文件（hermetic fake 模型，无需真实 ASR）",
        description="读取音频文件路径，经 m2t.asr 转写并用 m2t.export 导出；默认 txt",
    )
    transcribe_parser.add_argument("audio", help="输入音频文件路径（支持: %(choices)s 以外的扩展校验在运行时中文报错）")
    # 不用 choices，改为运行时中文校验，保证「非法 --format → 中文报错」门控
    transcribe_parser.add_argument(
        "--format",
        dest="format",
        default="txt",
        metavar="{txt,srt,md}",
        help="输出格式，可选 txt/srt/md（默认: txt）",
    )
    transcribe_parser.add_argument(
        "--out",
        dest="out",
        default=None,
        help="输出文件路径（默认: <stem>.<format>；父目录自动创建）",
    )
    transcribe_parser.add_argument(
        "--stub",
        action="store_true",
        default=False,
        help="强制使用内置 fake 模型（默认即 fake，显式传此开关亦可）",
    )
    return parser


def _cmd_transcribe(args: argparse.Namespace) -> None:
    audio: str = getattr(args, "audio", "")
    fmt: str = (getattr(args, "format", "txt") or "txt").strip().lower().lstrip(".")
    out: str | None = getattr(args, "out", None)

    # --format 手动校验，输出中文错误（满足「坏参数→中文报错」）
    if fmt not in ALLOWED_FORMATS:
        print(f"错误: 不支持的格式: {fmt}，支持: {', '.join(sorted(ALLOWED_FORMATS))}", file=sys.stderr)
        sys.exit(1)

    # 存在性与目录校验
    if not audio or not os.path.exists(audio) or os.path.isdir(audio):
        print(f"错误: 文件不存在或为目录: {audio}", file=sys.stderr)
        sys.exit(1)

    ext = os.path.splitext(audio)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        print(
            f"错误: 不支持的文件格式: {audio} (支持: {', '.join(sorted(ALLOWED_EXTENSIONS))})",
            file=sys.stderr,
        )
        sys.exit(1)

    # 解析输出路径
    if out is not None and out.strip() != "":
        output_path = out
    else:
        base = os.path.splitext(audio)[0]
        output_path = f"{base}.{fmt}"

    # hermetic 转写：注入确定性 fake 模型，复用 m2t.export
    # 懒导入，保证 import cli 不触发 funasr/torch
    try:
        from m2t.asr import transcribe as m2t_transcribe
        from m2t.export import export as m2t_export
    except ImportError as exc:
        print(f"错误: 无法导入 m2t 教学包: {exc}", file=sys.stderr)
        sys.exit(1)

    # 始终走 fake 模型；--stub 仅为显式声明，行为一致
    fake_model = _create_fake_model()
    try:
        segments = m2t_transcribe(audio, model=fake_model, language="auto")
    except Exception as exc:
        print(f"错误: 转写失败: {exc}", file=sys.stderr)
        sys.exit(1)

    if not segments:
        print("错误: 未能识别到语音内容，请检查音频是否有效", file=sys.stderr)
        sys.exit(1)

    # 构造 export 所需的 task 形态（兼容 m2t.export 的 dict 分支）
    # duration 取段末尾最大值，供 md 时长展示
    try:
        duration = max(float(s.get("end", 0) or 0) for s in segments)
    except (TypeError, ValueError):
        duration = 0.0

    task: dict = {
        "filename": os.path.basename(audio),
        "id": "m1-demo",
        "result": {"segments": segments, "duration": duration},
        "minutes": "",
    }

    try:
        content = m2t_export(task, fmt)
    except Exception as exc:
        print(f"错误: 导出失败: {exc}", file=sys.stderr)
        sys.exit(1)

    # 确保父目录存在
    parent = os.path.dirname(os.path.abspath(output_path))
    if parent and not os.path.exists(parent):
        try:
            os.makedirs(parent, exist_ok=True)
        except OSError as exc:
            print(f"错误: 无法创建输出目录 {parent}: {exc}", file=sys.stderr)
            sys.exit(1)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError as exc:
        print(f"错误: 无法写入输出文件 {output_path}: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"转录完成 → {output_path}")


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "command", None) == "transcribe":
        _cmd_transcribe(args)
        return
    # 未来可扩展其他子命令；当前仅 transcribe
    parser.error("未知子命令")


if __name__ == "__main__":
    main(sys.argv[1:])
