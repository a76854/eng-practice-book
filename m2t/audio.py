"""音频读取与重采样。

为什么：MeetingToText 的 pipeline 需要把任意格式、任意采样率的音频统一
成单声道 float32，才能喂给 FunASR。教学中若每章都重复这段 I/O 与重采
样逻辑，读者注意力会被工程细节带偏；抽成两个小函数后，单元测试可用
纯 numpy 合成数据验证行为，而真实文件读取只在边界处发生一次。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf


def load_audio(path: str | Path) -> tuple[np.ndarray, int]:
    """读取音频文件，返回 ``(samples, sr)``。

    为什么返回单声道 float32：FunASR 与后续质量门都假设单通道；
    立体声在此时合并可避免下游对通道数的分支判断。

    参数:
        path: 音频文件路径（wav/mp3/m4a/flac/ogg 等，依赖 soundfile 解码）

    返回:
        ``(samples, sr)``，其中 ``samples`` 为一维 ``float32`` 数组，
        ``sr`` 为原始采样率。
    """
    p = Path(path)
    data, sr = sf.read(str(p), dtype="float32")
    # soundfile 读出可能是 (N,) 或 (N, C)；统一压成单声道
    if data.ndim == 2:
        data = data.mean(axis=1).astype(np.float32, copy=False)
    # 确保 dtype 为 float32
    if data.dtype != np.float32:
        data = data.astype(np.float32)
    return data, int(sr)


def resample_audio(
    samples: np.ndarray,
    orig_sr: int,
    target_sr: int,
) -> np.ndarray:
    """将 ``samples`` 从 ``orig_sr`` 重采样到 ``target_sr``。

    为什么单独抽出：重采样是 pipeline 中「输入归一」的一步，失败不应
    影响文件读取；单独函数便于用合成正弦波做 hermetic 测试，也便于
    在未安装 librosa 的环境中降级（返回原数据并由调用方决定）。

    若 ``orig_sr == target_sr`` 则原样返回，避免不必要的插值开销。
    """
    if orig_sr == target_sr:
        return samples
    try:
        import librosa
    except ImportError:
        # 无 librosa 时不做重采样，原样返回；调用方可用 sr 判断是否一致
        return samples
    resampled: np.ndarray = librosa.resample(
        samples.astype(np.float32, copy=False),
        orig_sr=orig_sr,
        target_sr=target_sr,
    )
    return resampled.astype(np.float32, copy=False)


def load_and_resample(
    path: str | Path,
    target_sr: int = 16000,
) -> tuple[np.ndarray, int]:
    """读取并按需重采样到 ``target_sr``。

    为什么提供组合函数：pipeline 的常见路径就是「读 + 重采样」两步；
    组合后调用方只需关心最终的 ``(samples, 16000)``，减少样板。
    """

    samples, sr = load_audio(path)
    if sr != target_sr:
        samples = resample_audio(samples, sr, target_sr)
        return samples, target_sr
    return samples, sr
