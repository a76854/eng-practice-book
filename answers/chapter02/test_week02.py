"""week02 习题测试（≥5 例，全部 hermetic）。"""

import importlib.util
import os
import pathlib
import tempfile

_spec = importlib.util.spec_from_file_location(
    "week02_solution",
    pathlib.Path(__file__).with_name("solution.py"),
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

build_transcribe_commands = _mod.build_transcribe_commands  # type: ignore[attr-defined]
count_by_extension = _mod.count_by_extension  # type: ignore[attr-defined]
filter_by_ext = _mod.filter_by_ext  # type: ignore[attr-defined]
glob_audio_files = _mod.glob_audio_files  # type: ignore[attr-defined]
jq_extract = _mod.jq_extract  # type: ignore[attr-defined]
parse_find_output = _mod.parse_find_output  # type: ignore[attr-defined]


def test_glob_audio_files_basic():
    tmpdir = tempfile.mkdtemp()
    for name in ["a.wav", "b.wav", "c.mp3", "d.WAV"]:
        pathlib.Path(tmpdir, name).write_text("x")
    matched = glob_audio_files(tmpdir, "*.wav")
    basenames = [os.path.basename(p) for p in matched]
    # 默认大小写敏感（glob 在 Linux 区分大小写），故 d.WAV 不应命中 *.wav
    assert basenames == ["a.wav", "b.wav"]
    # 显式测大小写不敏感的场景由 filter_by_ext 覆盖


def test_glob_audio_files_nonexistent_dir():
    assert glob_audio_files("/tmp/__no_such_dir_week02__", "*.wav") == []


def test_glob_audio_files_sorted():
    tmpdir = tempfile.mkdtemp()
    for name in ["z.wav", "a.wav", "m.wav"]:
        pathlib.Path(tmpdir, name).write_text("x")
    matched = glob_audio_files(tmpdir, "*.wav")
    basenames = [os.path.basename(p) for p in matched]
    assert basenames == sorted(basenames)


def test_filter_by_ext_with_and_without_dot():
    paths = ["/a/b.wav", "/a/c.WAV", "/a/d.mp3", "/a/e.wav"]
    assert filter_by_ext(paths, ".wav") == ["/a/b.wav", "/a/c.WAV", "/a/e.wav"]
    assert filter_by_ext(paths, "wav") == ["/a/b.wav", "/a/c.WAV", "/a/e.wav"]
    assert filter_by_ext(paths, ".mp3") == ["/a/d.mp3"]


def test_filter_by_ext_case_insensitive():
    paths = ["a.WaV", "b.wav", "c.MP3"]
    assert filter_by_ext(paths, ".wav") == ["a.WaV", "b.wav"]
    assert filter_by_ext(paths, "mp3") == ["c.MP3"]


def test_parse_find_output_strip_dedup_sort():
    lines = ["  /a/b.wav  ", "", "/a/b.wav", "/a/c.wav ", "  ", "/a/a.wav"]
    assert parse_find_output(lines) == ["/a/a.wav", "/a/b.wav", "/a/c.wav"]


def test_parse_find_output_empty():
    assert parse_find_output([]) == []
    assert parse_find_output(["", "  "]) == []


def test_count_by_extension_basic():
    paths = ["a.wav", "b.wav", "c.mp3", "d", "e.WAV", "f.mp3"]
    c = count_by_extension(paths)
    assert c[".wav"] == 3  # a.wav + b.wav + e.WAV (小写归一)
    assert c[".mp3"] == 2
    assert c[""] == 1  # 无扩展名


def test_count_by_extension_empty():
    assert count_by_extension([]) == {}


def test_build_transcribe_commands_basic():
    cmds = build_transcribe_commands(["a.wav", "b.wav"])
    assert cmds == ["meetingtotext transcribe a.wav", "meetingtotext transcribe b.wav"]


def test_build_transcribe_commands_with_out_dir():
    cmds = build_transcribe_commands(["/data/a.wav"], out_dir="/tmp/out")
    assert len(cmds) == 1
    assert "meetingtotext transcribe" in cmds[0]
    assert "/tmp/out/a.txt" in cmds[0]
    assert ">" in cmds[0]


def test_build_transcribe_commands_quoting():
    # 含空格的文件名需被引号包裹
    cmds = build_transcribe_commands(["my talk (1).wav"])
    assert len(cmds) == 1
    # shlex.quote 会加单引号
    assert "'my talk (1).wav'" in cmds[0] or '"my talk' in cmds[0]


def test_build_transcribe_commands_empty():
    assert build_transcribe_commands([]) == []
    assert build_transcribe_commands([], out_dir="/tmp/out") == []


def test_jq_extract_simple():
    records = [{"id": 1, "status": "done"}, {"id": 2}, {"id": 3, "status": "todo"}]
    assert jq_extract(records, "status") == ["done", "todo"]
    assert jq_extract(records, "id") == [1, 2, 3]


def test_jq_extract_nested():
    records = [{"a": {"b": 10}}, {"a": {"b": 20}}, {"a": {}}]
    assert jq_extract(records, "a.b") == [10, 20]


def test_jq_extract_missing_key():
    assert jq_extract([{"x": 1}], "y") == []
    assert jq_extract([], "id") == []
