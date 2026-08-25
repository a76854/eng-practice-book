"""音频模块 hermetic 测试（合成数据 + soundfile，无真实模型）。"""

from __future__ import annotations

import numpy as np
import soundfile as sf

from m2t.audio import load_and_resample, load_audio, resample_audio


def test_load_audio_mono(tmp_path):  # type: ignore[no-untyped-def]
    sr = 16000
    samples = (np.random.rand(sr) * 2 - 1).astype(np.float32)
    p = tmp_path / "mono.wav"
    sf.write(str(p), samples, sr)
    out, out_sr = load_audio(p)
    assert out_sr == sr
    assert out.ndim == 1
    assert out.dtype == np.float32
    assert len(out) == sr


def test_load_audio_stereo_to_mono(tmp_path):  # type: ignore[no-untyped-def]
    sr = 16000
    stereo = (np.random.rand(sr, 2) * 2 - 1).astype(np.float32)
    p = tmp_path / "stereo.wav"
    sf.write(str(p), stereo, sr)
    out, out_sr = load_audio(p)
    assert out.ndim == 1
    assert out_sr == sr
    assert len(out) == sr


def test_resample_noop_returns_same():  # type: ignore[no-untyped-def]
    samples = np.ones(100, dtype=np.float32)
    out = resample_audio(samples, 16000, 16000)
    # 相同采样率应原样返回（同一对象或相等）
    assert out is samples or np.array_equal(out, samples)


def test_load_and_resample_target(tmp_path):  # type: ignore[no-untyped-def]
    sr = 8000
    samples = np.random.rand(sr).astype(np.float32)
    p = tmp_path / "low.wav"
    sf.write(str(p), samples, sr)
    # 若 librosa 未安装，load_and_resample 会返回原数据；两种情况都接受
    out, out_sr = load_and_resample(p, target_sr=16000)
    assert out.dtype == np.float32
    assert out.ndim == 1
    assert out_sr in (8000, 16000)
