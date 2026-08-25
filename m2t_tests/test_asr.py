"""asr 归一化与 transcribe 的 hermetic 测试（fake model，无 torch/funasr）。"""

from __future__ import annotations

from m2t.asr import normalize_result, transcribe


def test_normalize_sentence_info_with_speaker():  # type: ignore[no-untyped-def]
    raw = [
        {
            "sentence_info": [
                {"text": "你好", "start": 0, "end": 1000, "spk": 0},
                {"text": "世界", "start": 1000, "end": 2000, "spk": 1},
            ]
        }
    ]
    segs = normalize_result(raw)
    assert len(segs) == 2
    assert segs[0]["speaker"] == "说话人1"
    assert segs[1]["speaker"] == "说话人2"
    assert segs[0]["start"] == 0.0
    assert segs[0]["end"] == 1.0
    assert segs[1]["text"] == "世界"


def test_normalize_raw_text_timestamp_fallback():  # type: ignore[no-untyped-def]
    raw = [
        {
            "text": "hello world",
            "timestamp": [[0, 1000]],
        }
    ]
    segs = normalize_result(raw)
    assert len(segs) == 1
    assert segs[0]["text"] == "hello world"
    assert segs[0]["speaker"] == ""
    assert segs[0]["start"] == 0.0
    assert segs[0]["end"] == 1.0


def test_normalize_raw_text_list_with_timestamps():  # type: ignore[no-untyped-def]
    raw = [
        {
            "text": ["第一段", "第二段"],
            "timestamp": [[0, 500], [500, 1000]],
        }
    ]
    segs = normalize_result(raw)
    assert len(segs) == 2
    assert segs[0]["text"] == "第一段"
    assert segs[1]["text"] == "第二段"


def test_normalize_empty_result():  # type: ignore[no-untyped-def]
    assert normalize_result([]) == []
    assert normalize_result([{}]) == []
    assert normalize_result([{"sentence_info": []}]) == []
    assert normalize_result([{"text": "", "timestamp": []}]) == []


def test_transcribe_with_fake_model_sentence_info():  # type: ignore[no-untyped-def]
    class FakeModel:
        def generate(self, **kwargs):  # type: ignore[no-untyped-def]
            return [
                {
                    "sentence_info": [
                        {"text": "测试", "start": 0, "end": 800, "spk": 0},
                    ]
                }
            ]

    segs = transcribe("dummy.wav", model=FakeModel(), language="auto")
    assert len(segs) == 1
    assert segs[0]["speaker"] == "说话人1"
    assert segs[0]["text"] == "测试"


def test_transcribe_with_fake_model_empty():  # type: ignore[no-untyped-def]
    class FakeModel:
        def generate(self, **kwargs):  # type: ignore[no-untyped-def]
            return []

    segs = transcribe("dummy.wav", model=FakeModel())
    assert segs == []
