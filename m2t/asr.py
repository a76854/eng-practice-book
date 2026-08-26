"""FunASR 调用封装与结果多形状归一化。

为什么：FunASR 的 ``AutoModel.generate`` 在不同模型/参数下会返回不同
形状的结果（有无 sentence_info、有无 timestamp、空结果），若让每章各自
解析，极易遗漏分支。本模块把「调用」与「归一」解耦，并对 funasr 做
懒导入，保证 ``import m2t`` 在未安装 torch/funasr 的教学环境中也能成功。
"""

from __future__ import annotations

import re
from typing import Any

MS_PER_S = 1000.0
SPEAKER_LABEL_TEMPLATE = "说话人{}"


def _clean_text(text: str) -> str:
    text = re.sub(r"<\|[^|>]+\|>", "", text)
    text = text.strip()
    text = re.sub(r"^[。，、；：！？,.!?:;]+", "", text)
    return text.strip()


def normalize_result(result: list[Any]) -> list[dict[str, Any]]:
    """将 FunASR 原始结果归一为 ``[{speaker, text, start, end}]``。

    为什么需要归一：下游 pipeline、store 与 export 都依赖统一的段结构
    （start/end 以秒为单位）。本函数把上游的不稳定性收敛在一处。

    处理的三种形状（对应 MeetingToText 的真实回包 + 空结果）：

    1. ``sentence_info`` 带说话人：``result[0]["sentence_info"]`` 为列表，
       每项含 ``text``/``sentence``、``start``/``end``（毫秒）、可选
       ``spk``（CAM++ 的 0 基 id，转为 1 基的「说话人N」）。
    2. ``raw_text + timestamp`` 回退：无 ``sentence_info`` 时，用
       ``result[0]["text"]`` 与 ``result[0]["timestamp"]``（``[[s,e],...]`` 毫
       秒对）逐段对齐；无说话人标签。
    3. 空结果：``[]``、``[{}]``、或 ``sentence_info`` 与 ``timestamp`` 皆空
       时返回 ``[]``，由调用方决定是否抛错。

    所有时间从毫秒转为秒。
    """

    segments: list[dict[str, Any]] = []
    if not isinstance(result, list) or len(result) == 0:
        return segments

    item = result[0]
    if not isinstance(item, dict):
        return segments

    # 形状 1：sentence_info
    sentence_info = item.get("sentence_info", [])
    if isinstance(sentence_info, list) and len(sentence_info) > 0:
        for sent in sentence_info:
            if not isinstance(sent, dict):
                continue
            text = sent.get("text") or sent.get("sentence") or ""
            text = _clean_text(str(text))
            if not text:
                continue
            start = sent.get("start") or 0
            end = sent.get("end") or 0
            spk = sent.get("spk", "")
            if spk is not None and spk != "":
                try:
                    spk_label = SPEAKER_LABEL_TEMPLATE.format(int(spk) + 1)
                except (ValueError, TypeError):
                    spk_label = str(spk)
            else:
                spk_label = ""
            segments.append(
                {
                    "speaker": spk_label,
                    "text": text,
                    "start": float(start) / MS_PER_S,
                    "end": float(end) / MS_PER_S,
                }
            )
        if segments:
            return segments

    # 形状 2：raw_text + timestamp 回退
    raw_text = item.get("text", "")
    timestamps = item.get("timestamp", [])
    if isinstance(raw_text, str):
        raw_text = _clean_text(raw_text)
    if raw_text and isinstance(timestamps, list) and len(timestamps) > 0:
        if isinstance(raw_text, list):
            texts: list[str] = [str(t) for t in raw_text]
        else:
            texts = [str(raw_text)]  # noqa: SIM108
        for idx, ts in enumerate(timestamps):
            if not isinstance(ts, list) or len(ts) != 2:
                continue
            txt = texts[idx] if idx < len(texts) else ""
            if not txt:
                # 单条 raw_text 对应多段 timestamp 时，复用同一文本不合适；
                # 若 texts 长度为 1 且 ts 多段，则仅首段有文本，其余跳过
                if len(texts) == 1 and idx == 0:
                    txt = texts[0]
                else:
                    continue
            txt = _clean_text(txt)
            if not txt:
                continue
            segments.append(
                {
                    "speaker": "",
                    "text": txt,
                    "start": float(ts[0] or 0) / MS_PER_S,
                    "end": float(ts[1] or 0) / MS_PER_S,
                }
            )
        return segments

    # 形状 3：空结果
    return segments


def transcribe(
    audio_path: str,
    model: Any | None = None,
    language: str = "auto",
) -> list[dict[str, Any]]:
    """调用 FunASR 模型并返回归一后的段列表。

    为什么 funasr 懒导入：教学环境默认不装 torch/funasr（decision ⑩），
    ``import m2t`` 必须成功；只有真正需要转写时才尝试导入，缺失时抛
    带中文提示的 ``RuntimeError``。

    参数:
        audio_path: 音频文件路径
        model: 已加载的 FunASR 模型实例；为 ``None`` 时懒导入并创建
            默认 ``AutoModel``。测试中可传入 fake model。
        language: 语言参数，透传给 ``model.generate``。
    """

    if model is None:
        try:
            from funasr import AutoModel
        except ImportError as exc:
            raise RuntimeError(
                "FunASR 未安装，请使用 pip install \"m2t[asr]\" 安装可选依赖"
            ) from exc
        model = AutoModel(
            model="iic/SenseVoiceSmall",
            vad_model="fsmn-vad",
            spk_model="cam++",
            device="cpu",
            disable_update=True,
        )
    raw_result = model.generate(
        input=audio_path,
        cache={},
        language=language,
        use_itn=True,
    )
    # funasr 返回可能是 list，直接归一；非 list 则包一层
    if isinstance(raw_result, list):
        return normalize_result(raw_result)
    return normalize_result([raw_result])
