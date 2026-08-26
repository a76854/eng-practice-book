"""M1 CLI 黑盒测试（hermetic，无 funasr/torch/网络/真实模型）。

只断言可观测行为：退出码、stderr/files 内容。fake 模型固定输出
覆盖 m2t.asr 归一化的形状 1（sentence_info）。
"""

from __future__ import annotations

import os
import pathlib

import pytest

import cli  # 由 conftest 或 grader 的 PYTHONPATH 注入

# 期望的 fake 输出（与 reference_solution/cli.py:_FAKE_RAW_RESULT 一致）
EXPECTED_TXT = "[说话人1] 大家好，我们开始开会。\n[说话人2] 好的，我先汇报一下进度。"
EXPECTED_SRT_FRAG_START = "00:00:00,000 --> 00:00:01,200"
EXPECTED_SRT_FRAG_END = "00:00:01,500 --> 00:00:03,000"


def _make_wav(path: pathlib.Path) -> pathlib.Path:
    # 仅需文件存在且扩展名合法；fake 模型不读内容
    path.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfake")
    return path


# ---------------------------------------------------------------------------
# 合法路径
# ---------------------------------------------------------------------------

def test_txt_default_writes_txt_with_expected_content(tmp_path, capsys):
    """Given 合法 wav，When transcribe（默认 txt），Then <stem>.txt 含固定 fake 文本且打印成功信息。"""
    wav = _make_wav(tmp_path / "a.wav")

    cli.main(["transcribe", str(wav)])

    out = tmp_path / "a.txt"
    assert out.exists(), "默认输出应为 <stem>.txt"
    content = out.read_text(encoding="utf-8")
    assert content == EXPECTED_TXT, f"txt 内容不符:\n{content!r}"
    captured = capsys.readouterr()
    assert "转录完成" in captured.out


def test_txt_explicit_format(tmp_path, capsys):
    """Given wav，When --format txt 显式，Then 同默认行为。"""
    wav = _make_wav(tmp_path / "b.wav")
    cli.main(["transcribe", str(wav), "--format", "txt"])
    out = tmp_path / "b.txt"
    assert out.exists()
    assert out.read_text(encoding="utf-8") == EXPECTED_TXT


def test_srt_format_writes_srt(tmp_path, capsys):
    """Given wav，When --format srt，Then .srt 含时间戳与说话人。"""
    wav = _make_wav(tmp_path / "c.wav")
    cli.main(["transcribe", str(wav), "--format", "srt"])
    out = tmp_path / "c.srt"
    assert out.exists(), "srt 格式应产出 .srt"
    content = out.read_text(encoding="utf-8")
    assert EXPECTED_SRT_FRAG_START in content
    assert EXPECTED_SRT_FRAG_END in content
    assert "[说话人1]" in content
    assert "[说话人2]" in content
    assert " --> " in content
    # srt 块间空行
    assert "\n\n" in content


def test_md_format_writes_md(tmp_path, capsys):
    """Given wav，When --format md，Then .md 含 Markdown 标题与段。"""
    wav = _make_wav(tmp_path / "d.wav")
    cli.main(["transcribe", str(wav), "--format", "md"])
    out = tmp_path / "d.md"
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "# 会议转录" in content
    assert "说话人1" in content or "大家好" in content
    assert "大家好，我们开始开会" in content


def test_out_option_honored(tmp_path, capsys):
    """Given --out 自定义路径，When transcribe，Then 该路径生效且父目录自动创建。"""
    wav = _make_wav(tmp_path / "e.wav")
    custom = tmp_path / "nested" / "out" / "custom.txt"
    cli.main(["transcribe", str(wav), "--format", "txt", "--out", str(custom)])
    assert custom.exists(), "--out 应写入指定路径"
    assert custom.read_text(encoding="utf-8") == EXPECTED_TXT
    # 默认路径不应再产生
    assert not (tmp_path / "e.txt").exists()
    # 父目录已创建
    assert custom.parent.exists()


def test_out_with_srt_format(tmp_path, capsys):
    """Given --format srt + --out，Then 指定路径内容为 srt。"""
    wav = _make_wav(tmp_path / "f.wav")
    custom = tmp_path / "my.srt"
    cli.main(["transcribe", str(wav), "--format", "srt", "--out", str(custom)])
    assert custom.exists()
    content = custom.read_text(encoding="utf-8")
    assert EXPECTED_SRT_FRAG_START in content


# ---------------------------------------------------------------------------
# 异常路径（malformed_input 探针）
# ---------------------------------------------------------------------------

def test_bad_extension_exits_nonzero_and_chinese(tmp_path, capsys):
    """Given 坏扩展文件，When transcribe，Then 非零退出 + 中文错误。"""
    bad = tmp_path / "bad.xyz"
    bad.write_bytes(b"fake")
    with pytest.raises(SystemExit) as exc:
        cli.main(["transcribe", str(bad)])
    assert exc.value.code != 0
    err = capsys.readouterr().err
    assert "错误" in err
    assert "不支持的文件格式" in err


def test_missing_file_exits_nonzero_and_chinese(tmp_path, capsys):
    """Given 缺失文件，When transcribe，Then 非零退出 + 中文错误。"""
    missing = str(tmp_path / "nope.wav")
    with pytest.raises(SystemExit) as exc:
        cli.main(["transcribe", missing])
    assert exc.value.code != 0
    err = capsys.readouterr().err
    assert "错误" in err
    assert "不存在" in err


def test_invalid_format_exits_nonzero_and_chinese(tmp_path, capsys):
    """Given 合法 wav 但 --format 非法值，When transcribe，Then 非零退出 + 中文错误。"""
    wav = _make_wav(tmp_path / "g.wav")
    with pytest.raises(SystemExit) as exc:
        cli.main(["transcribe", str(wav), "--format", "pdf"])
    assert exc.value.code != 0
    err = capsys.readouterr().err
    # 手动校验分支输出中文；若未来改回 argparse choices，err 含 'invalid choice' 亦非零但此处要求中文
    assert "错误" in err
    assert "不支持的格式" in err


def test_directory_instead_of_file_exits_nonzero(tmp_path, capsys):
    """Given 路径为目录而非文件，When transcribe，Then 非零退出。"""
    d = tmp_path / "adir.wav"
    d.mkdir()
    with pytest.raises(SystemExit) as exc:
        cli.main(["transcribe", str(d)])
    assert exc.value.code != 0
    assert "错误" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Hermetic 保障
# ---------------------------------------------------------------------------

def test_no_real_asr_import_at_runtime():
    """保证测试时未加载 funasr/torch（hermetic）。"""
    import sys

    assert "funasr" not in sys.modules, "不应在测试中导入 funasr"
    assert "torch" not in sys.modules, "不应在测试中导入 torch"
